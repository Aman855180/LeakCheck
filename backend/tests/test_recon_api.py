import pytest
from datetime import datetime, timezone
from decimal import Decimal
from app.models.order_recon import OrderRecon


def test_trigger_recon_cofounder_blocked(client, cofounder_cookies, cofounder_headers):
    """Co-founder is read-only; cannot trigger reconciliation run (403 Forbidden)."""
    response = client.post(
        "/api/v1/recon/run",
        json={"as_of": "2026-11-01"},
        cookies=cofounder_cookies,
        headers=cofounder_headers
    )
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]


def test_trigger_recon_finance_exec_allowed(client, finance_exec_cookies, finance_exec_headers):
    """Finance Executive can trigger reconciliation runs."""
    response = client.post(
        "/api/v1/recon/run",
        json={"as_of": "2026-11-01"},
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_orders_reconciled" in data
    assert "status_counts" in data
    assert "total_money_at_risk" in data


def test_list_reconciled_orders_and_summary(client, finance_exec_cookies, finance_exec_headers, db_session):
    # Seed a sample recon record
    order_id = "ORD-API-TEST-01"
    recon = OrderRecon(
        order_id=order_id,
        partner_id="amazon",
        channel="marketplace",
        payment_mode="PREPAID",
        order_date=datetime(2026, 3, 2, tzinfo=timezone.utc),
        order_value=Decimal("1199.00"),
        expected_amount=Decimal("899.00"),
        received_amount=Decimal("850.00"),
        difference=Decimal("-49.00"),
        status="short_paid",
        reason_codes=["settlement_shortfall"],
        money_at_risk=Decimal("49.00"),
        age_days=15,
        age_bucket="8-15"
    )
    db_session.add(recon)
    db_session.commit()

    # 1. List all orders
    res_list = client.get(
        "/api/v1/recon/orders",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_list.status_code == 200
    orders = res_list.json()
    assert len(orders) >= 1
    found = next((o for o in orders if o["order_id"] == order_id), None)
    assert found is not None
    assert found["status"] == "short_paid"
    assert found["money_at_risk"] == "49.00"

    # 2. Filter by status
    res_filtered = client.get(
        "/api/v1/recon/orders?status=short_paid",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_filtered.status_code == 200
    for o in res_filtered.json():
        assert o["status"] == "short_paid"

    # 3. Get single detail
    res_detail = client.get(
        f"/api/v1/recon/orders/{order_id}",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_detail.status_code == 200
    assert res_detail.json()["order_id"] == order_id

    # 4. Get summary KPIs
    res_summary = client.get(
        "/api/v1/recon/summary",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_summary.status_code == 200
    summary = res_summary.json()
    assert summary["total_orders"] >= 1
    assert Decimal(summary["total_money_at_risk"]) >= Decimal("49.00")
