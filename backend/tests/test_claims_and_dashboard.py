import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.order_recon import OrderRecon
from app.models.claim import Claim
from app.services.claims_generator import ClaimsGenerator


def test_claims_crud_and_lifecycle(client, db_session, finance_exec_cookies, finance_exec_headers, cofounder_cookies, cofounder_headers):
    suffix = uuid.uuid4().hex[:6]
    order_id = f"ORD-CLM-{suffix}"
    t0 = datetime(2026, 10, 15, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Create Order with Discrepancy
    recon = OrderRecon(
        external_order_id=order_id,
        order_id=order_id,
        partner_id="shopify",
        channel="d2c",
        payment_mode="COD",
        order_date=t0,
        order_value=Decimal("1500.00"),
        expected_amount=Decimal("1410.00"),
        received_amount=Decimal("0.00"),
        difference=Decimal("-1410.00"),
        status="unpaid_past_due",
        reason_codes=["cod_remittance_missing"],
        age_days=17,
        age_bucket="16-30",
        money_at_risk=Decimal("1410.00"),
        settlement_gap_component=Decimal("1410.00")
    )
    db_session.add(recon)
    db_session.commit()

    # 2. Generate Claims
    claims_gen = ClaimsGenerator(db_session)
    generated = claims_gen.generate_draft_claims(order_ids=[order_id])
    assert len(generated) == 1
    claim = generated[0]
    claim_id = str(claim.id)
    assert claim.claim_status == "draft"
    assert claim.claim_amount == Decimal("1410.00")
    assert claim.recovered_amount == Decimal("0.00")
    assert claim.recovered_at is None

    # 3. List Claims via API
    res = client.get(
        f"/api/v1/claims?search={order_id}",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 200
    claims_list = res.json()
    assert len(claims_list) == 1
    assert claims_list[0]["id"] == claim_id
    assert claims_list[0]["claim_status"] == "draft"

    # 4. View Claim Detail with linked order
    res_detail = client.get(
        f"/api/v1/claims/{claim_id}",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["id"] == claim_id
    assert detail["order"] is not None
    assert detail["order"]["order_id"] == order_id
    assert detail["order"]["money_at_risk"] == "1410.00"

    # 5. RBAC: Co-founder CANNOT update claim (returns 403)
    res_co_patch = client.patch(
        f"/api/v1/claims/{claim_id}",
        json={"claim_status": "submitted"},
        cookies=cofounder_cookies,
        headers=cofounder_headers
    )
    assert res_co_patch.status_code == 403

    # 6. Finance Exec updates status to "submitted" and adds notes
    res_patch = client.patch(
        f"/api/v1/claims/{claim_id}",
        json={"claim_status": "submitted", "notes": "Docket filed with courier team"},
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_patch.status_code == 200
    updated = res_patch.json()
    assert updated["claim_status"] == "submitted"
    assert updated["notes"] == "Docket filed with courier team"

    # 7. Validation: Recovered amount cannot exceed claim amount
    res_over_recover = client.patch(
        f"/api/v1/claims/{claim_id}",
        json={"recovered_amount": 2000.00},
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_over_recover.status_code == 400

    # 8. Partial Recovery update
    res_partial = client.patch(
        f"/api/v1/claims/{claim_id}",
        json={"recovered_amount": 500.00, "claim_status": "in_review"},
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_partial.status_code == 200
    part_json = res_partial.json()
    assert part_json["recovered_amount"] == "500.00"
    assert part_json["claim_status"] == "in_review"
    assert part_json["recovered_at"] is not None

    # 9. Full Recovery auto-advances to "recovered"
    res_full = client.patch(
        f"/api/v1/claims/{claim_id}",
        json={"recovered_amount": 1410.00},
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_full.status_code == 200
    full_json = res_full.json()
    assert full_json["recovered_amount"] == "1410.00"
    assert full_json["claim_status"] == "recovered"


def test_claims_duplicate_prevention(db_session):
    suffix = uuid.uuid4().hex[:6]
    order_id = f"ORD-DUP-{suffix}"

    recon = OrderRecon(
        external_order_id=order_id,
        order_id=order_id,
        partner_id="amazon",
        channel="marketplace",
        payment_mode="PREPAID",
        order_date=datetime(2026, 10, 20, tzinfo=timezone.utc),
        order_value=Decimal("1000.00"),
        expected_amount=Decimal("850.00"),
        received_amount=Decimal("800.00"),
        difference=Decimal("-50.00"),
        status="short_paid",
        reason_codes=["excess_commission"],
        money_at_risk=Decimal("50.00")
    )
    db_session.add(recon)
    db_session.commit()

    # Claim 1
    c1 = Claim(
        order_recon_id=recon.id,
        external_order_id=order_id,
        partner_id="amazon",
        claim_amount=Decimal("50.00"),
        claim_reason="excess_commission",
        claim_status="draft"
    )
    db_session.add(c1)
    db_session.commit()

    # Claim 2 with same order_recon_id and claim_reason must violate unique constraint
    c2 = Claim(
        order_recon_id=recon.id,
        external_order_id=order_id,
        partner_id="amazon",
        claim_amount=Decimal("50.00"),
        claim_reason="excess_commission",
        claim_status="draft"
    )
    db_session.add(c2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_claims_export_csv_and_summary(client, db_session, finance_exec_cookies, finance_exec_headers, cofounder_cookies, cofounder_headers):
    # Both roles can download CSV export
    res_csv_fin = client.get(
        "/api/v1/claims/export/csv",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_csv_fin.status_code == 200
    assert "text/csv" in res_csv_fin.headers["Content-Type"]
    assert "Claim ID,Order ID,Partner,Claim Reason" in res_csv_fin.text

    res_csv_co = client.get(
        "/api/v1/claims/export/csv",
        cookies=cofounder_cookies,
        headers=cofounder_headers
    )
    assert res_csv_co.status_code == 200

    # Claims summary endpoint
    res_summary = client.get(
        "/api/v1/claims/summary",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_summary.status_code == 200
    summary = res_summary.json()
    assert "total_claims" in summary
    assert "total_claim_amount" in summary
    assert "total_recovered_amount" in summary
    assert "recovery_rate_pct" in summary


def test_dashboard_metrics_aggregation(client, db_session, finance_exec_cookies, finance_exec_headers, cofounder_cookies, cofounder_headers):
    suffix = uuid.uuid4().hex[:6]
    base_date = datetime(2026, 10, 10, tzinfo=timezone.utc)

    # 1. Clean order with money_at_risk = 0
    clean_recon = OrderRecon(
        external_order_id=f"ORD-DASH-CLEAN-{suffix}",
        order_id=f"ORD-DASH-CLEAN-{suffix}",
        partner_id="shopify",
        channel="d2c",
        payment_mode="PREPAID",
        order_date=base_date,
        order_value=Decimal("1000.00"),
        expected_amount=Decimal("940.00"),
        received_amount=Decimal("940.00"),
        difference=Decimal("0.00"),
        status="settled",
        money_at_risk=Decimal("0.00")
    )

    # 2. Discrepant order with non-overlapping components
    risk_recon = OrderRecon(
        external_order_id=f"ORD-DASH-RISK-{suffix}",
        order_id=f"ORD-DASH-RISK-{suffix}",
        partner_id="amazon",
        channel="marketplace",
        payment_mode="PREPAID",
        order_date=base_date + timedelta(days=2),
        order_value=Decimal("2000.00"),
        expected_amount=Decimal("1700.00"),
        received_amount=Decimal("1500.00"),
        difference=Decimal("-200.00"),
        status="short_paid",
        reason_codes=["settlement_shortfall", "freight_overcharge"],
        age_days=14,
        age_bucket="8-15",
        money_at_risk=Decimal("200.00"),
        settlement_gap_component=Decimal("150.00"),
        freight_excess_component=Decimal("50.00"),
        return_loss_component=Decimal("0.00")
    )

    db_session.add_all([clean_recon, risk_recon])
    db_session.commit()

    # Query Dashboard Metrics
    res = client.get(
        "/api/v1/dashboard/metrics",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 200
    data = res.json()

    assert data["total_orders"] >= 2
    assert Decimal(data["total_money_at_risk"]) >= Decimal("200.00")
    assert Decimal(data["total_settlement_gap"]) >= Decimal("150.00")
    assert Decimal(data["total_freight_excess"]) >= Decimal("50.00")
    assert "8-15" in data["age_bucket_counts"]
    assert "amazon" in data["partner_risk_breakdown"]
    assert "claims_summary" in data

    # Co-founder can also read dashboard metrics
    res_co = client.get(
        "/api/v1/dashboard/metrics",
        cookies=cofounder_cookies,
        headers=cofounder_headers
    )
    assert res_co.status_code == 200


def test_claims_export_csv_sanitization_and_negative_numbers():
    from app.api.v1.claims import sanitize_csv_cell
    # 1. Legitimate negative and positive numeric values must NOT be escaped
    assert sanitize_csv_cell(-150.00) == "-150.0"
    assert sanitize_csv_cell(Decimal("-250.75")) == "-250.75"
    assert sanitize_csv_cell("-123.45") == "-123.45"
    assert sanitize_csv_cell("+456.78") == "+456.78"
    assert sanitize_csv_cell(0) == "0"
    assert sanitize_csv_cell(Decimal("0.00")) == "0.00"

    # 2. Formula injection triggers must be escaped with a single quote
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert sanitize_csv_cell("@SUM(1,2)") == "'@SUM(1,2)"
    assert sanitize_csv_cell("+cmd|calc") == "'+cmd|calc"
    assert sanitize_csv_cell("-cmd|calc") == "'-cmd|calc"
    assert sanitize_csv_cell("\tmalicious_tab") == "'\tmalicious_tab"
    assert sanitize_csv_cell("\rmalicious_cr") == "'\rmalicious_cr"

    # 3. Safe text remains unescaped
    assert sanitize_csv_cell("ORD-12345") == "ORD-12345"
    assert sanitize_csv_cell("amazon") == "amazon"
    assert sanitize_csv_cell("") == ""
    assert sanitize_csv_cell(None) == ""


def test_recovery_lifecycle_corrections_and_recovered_at(client, db_session, finance_exec_cookies, finance_exec_headers):
    suffix = uuid.uuid4().hex[:6]
    order_id = f"ORD-REC-{suffix}"

    recon = OrderRecon(
        external_order_id=order_id,
        order_id=order_id,
        partner_id="myntra",
        channel="marketplace",
        payment_mode="PREPAID",
        order_date=datetime(2026, 10, 18, tzinfo=timezone.utc),
        order_value=Decimal("800.00"),
        expected_amount=Decimal("700.00"),
        received_amount=Decimal("500.00"),
        difference=Decimal("-200.00"),
        status="short_paid",
        reason_codes=["settlement_shortfall"],
        money_at_risk=Decimal("200.00"),
        settlement_gap_component=Decimal("200.00")
    )
    db_session.add(recon)
    db_session.commit()

    claims_gen = ClaimsGenerator(db_session)
    generated = claims_gen.generate_draft_claims(order_ids=[order_id])
    assert len(generated) == 1
    claim = generated[0]
    claim_id = str(claim.id)

    # 1. Record Partial Recovery (₹100) -> status in_review, recovered_at set
    res1 = client.patch(
        f"/api/v1/claims/{claim_id}",
        json={"recovered_amount": 100.00, "claim_status": "in_review"},
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res1.status_code == 200
    c1 = res1.json()
    assert c1["recovered_amount"] == "100.00"
    assert c1["recovered_at"] is not None
    original_recovered_at = c1["recovered_at"]

    # 2. Correction: Finance executive corrects recovered amount down to 0 (erroneous entry)
    res2 = client.patch(
        f"/api/v1/claims/{claim_id}",
        json={"recovered_amount": 0.00, "claim_status": "submitted"},
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res2.status_code == 200
    c2 = res2.json()
    assert c2["recovered_amount"] == "0.00"
    assert c2["recovered_at"] is None  # cleared on 0 recovery
    assert c2["claim_status"] == "submitted"

    # 3. Explicit recovery timestamp with full recovery
    explicit_date = "2026-11-05T14:30:00Z"
    res3 = client.patch(
        f"/api/v1/claims/{claim_id}",
        json={"recovered_amount": 200.00, "recovered_at": explicit_date},
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res3.status_code == 200
    c3 = res3.json()
    assert c3["recovered_amount"] == "200.00"
    assert c3["claim_status"] == "recovered"
    assert "2026-11-05" in c3["recovered_at"]


def test_csv_formula_injection_sanitization():
    """
    SEC-03: Regression tests for spreadsheet formula injection (CWE-1236).
    Verifies that formula triggers preceded by leading spaces, tabs, newlines,
    or carriage returns are safely escaped, while valid numeric financials are preserved.
    """
    from app.api.v1.claims import sanitize_csv_cell

    required_cases = [
        ("=1+2", "'=1+2"),
        (" =1+2", "' =1+2"),
        ("   =1+2", "'   =1+2"),
        ("\n=1+2", "'\n=1+2"),
        ("\r=1+2", "'\r=1+2"),
        ("\t=1+2", "'\t=1+2"),
        (" @SUM(1,2)", "' @SUM(1,2)"),
        (" +cmd", "' +cmd"),
        ("-5+2", "'-5+2"),
        ("-125.50", "-125.50"),
        ("+500.00", "+500.00"),
        ("0", "0"),
        ("125.50", "125.50"),
        ("Standard Text Value", "Standard Text Value"),
    ]

    for raw, expected in required_cases:
        assert sanitize_csv_cell(raw) == expected, f"Failed for {repr(raw)}: expected {repr(expected)}"


def test_claims_export_csv_neutralizes_injection(client, finance_exec_cookies, finance_exec_headers, db_session):
    """
    SEC-03: Verifies that exported CSV output directly from /api/v1/claims/export/csv
    safely escapes formula triggers in claim notes and identifiers.
    """
    from app.models.claim import Claim
    from app.models.order_recon import OrderRecon
    from decimal import Decimal
    from datetime import datetime, timezone
    import csv
    import io

    # Insert a Recon record first to satisfy foreign key constraint
    recon = OrderRecon(
        external_order_id=" =1+2",
        order_id=" =1+2",
        partner_id="shopify",
        channel="courier",
        payment_mode="COD",
        order_date=datetime(2026, 11, 1, tzinfo=timezone.utc),
        order_value=Decimal("500.00"),
        expected_amount=Decimal("500.00"),
        received_amount=Decimal("350.00"),
        difference=Decimal("-150.00"),
        status="freight_overcharge",
        reason_codes=["freight_overcharge"],
        money_at_risk=Decimal("150.00")
    )
    db_session.add(recon)
    db_session.commit()

    # Insert a test claim with formula payload in notes and external_order_id
    test_claim = Claim(
        order_recon_id=recon.id,
        external_order_id=" =1+2",
        partner_id="shopify",
        claim_reason="freight_overcharge",
        claim_status="draft",
        claim_amount=Decimal("150.00"),
        recovered_amount=Decimal("0.00"),
        notes=" @SUM(1,2)",
        evidence_json={"settlement_gap": "0.00", "freight_excess": "150.00", "return_loss": "0.00"},
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(test_claim)
    db_session.commit()

    res = client.get(
        "/api/v1/claims/export/csv",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    csv_text = res.text

    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    header = rows[0]
    assert "Order ID" in header
    assert "Notes" in header
    order_id_idx = header.index("Order ID")
    notes_idx = header.index("Notes")

    found_row = None
    for r in rows[1:]:
        if r[order_id_idx] == "' =1+2":
            found_row = r
            break

    assert found_row is not None, "Injected order ID was not found or not escaped"
    assert found_row[order_id_idx] == "' =1+2"
    assert found_row[notes_idx] == "' @SUM(1,2)"
