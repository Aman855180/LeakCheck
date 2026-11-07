import uuid
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.models.order_event import OrderEvent
from app.models.tracking_event import TrackingEvent
from app.models.order_recon import OrderRecon
from app.models.claim import Claim
from app.models.upload import Upload
from app.models.source import Source
from app.models.user import User
from app.services.recon_engine import ReconciliationEngine, DEFAULT_AS_OF_DATE
from app.services.claims_generator import ClaimsGenerator


def get_test_upload(db_session, partner_id="shopify"):
    source = db_session.query(Source).filter(Source.partner_id == partner_id).first()
    if not source:
        source = db_session.query(Source).first()
    user = db_session.query(User).first()
    upload = Upload(
        source_id=source.id,
        partner_id=source.partner_id,
        source_type=source.source_type,
        file_name="test_feed.csv",
        file_hash=str(uuid.uuid4()).replace("-", "") + str(uuid.uuid4()).replace("-", ""),
        file_size_bytes=100,
        row_count=10,
        processing_status="completed",
        uploaded_by=user.id
    )
    db_session.add(upload)
    db_session.flush()
    return upload


def test_status_precedence_hierarchy(db_session):
    """
    Test Section 24.9 status precedence hierarchy:
    return_not_received > unpaid_past_due > freight_overcharged > short_paid > settled.
    When multiple conditions co-exist (e.g. return missing AND freight overcharged AND short paid),
    the higher precedence status MUST win, while preserving all reason codes.
    """
    upload = get_test_upload(db_session, "shopify")
    order_id = "ORD-PRECEDENCE-01"
    order_dt = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    delivery_dt = order_dt + timedelta(days=3)

    # Order placed: ₹1,500
    ev_order = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="order_placed",
        amount=Decimal("1500.00"),
        event_date=order_dt,
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id,
        raw_data={"Payment Method": "Prepaid"}
    )
    # Tracking RTO (missing at warehouse -> return_not_received candidate)
    trk = TrackingEvent(
        order_id=order_id,
        tracking_number=f"DEL-{order_id}",
        courier_code="delhivery",
        event_timestamp=delivery_dt,
        raw_status_code="RTO_DELIVERED_TO_DOCK",
        raw_telemetry={},
        verification_outcome="verified_dock_delivery",
        upload_id=upload.id,
        source_row_number=1
    )
    # Freight overcharge: expected is ~₹60-96, charged ₹300 -> freight_overcharged candidate
    ev_freight = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="freight_charge",
        amount=Decimal("300.00"),
        shipping_fee=Decimal("300.00"),
        event_date=order_dt + timedelta(days=2),
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id
    )
    # Reversal of ₹1,500
    ev_refund = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="settlement_reversal",
        amount=Decimal("-1500.00"),
        settlement_credit=Decimal("-1500.00"),
        event_date=order_dt + timedelta(days=4),
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id
    )
    db_session.add(ev_order)
    db_session.add(trk)
    db_session.add(ev_freight)
    db_session.add(ev_refund)
    db_session.commit()

    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    recon = engine.reconcile_single_order(external_order_id=order_id, partner_id="shopify")

    # return_not_received MUST win over freight_overcharged and short_paid
    assert recon.status == "return_not_received"
    # Multiple reason codes must be preserved
    assert "return_receipt_missing" in recon.reason_codes
    assert "freight_overcharge" in recon.reason_codes


def test_cod_overdue_only_after_configured_due_date(db_session):
    """
    Test COD overdue only triggers after order_date + delivery + due_days (e.g. 7 days SLA).
    Before due date: status MUST be pending (₹0 risk).
    After due date: status becomes unpaid_past_due with cod_remittance_missing.
    """
    upload = get_test_upload(db_session, "shopify")
    order_id = "ORD-COD-SLA-01"
    # Order placed on Oct 25, 2026, delivered on Oct 27
    order_dt = datetime(2026, 10, 25, 10, 0, tzinfo=timezone.utc)
    delivery_dt = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)

    ev_order = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="order_placed",
        amount=Decimal("1200.00"),
        event_date=order_dt,
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id,
        raw_data={"Payment Method": "COD"}
    )
    trk = TrackingEvent(
        order_id=order_id,
        tracking_number=f"DEL-{order_id}",
        courier_code="delhivery",
        event_timestamp=delivery_dt,
        raw_status_code="DELIVERED",
        raw_telemetry={},
        verification_outcome="VALID_DELIVERY",
        upload_id=upload.id,
        source_row_number=1
    )
    db_session.add(ev_order)
    db_session.add(trk)
    db_session.commit()

    # Case A: Evaluate on Oct 29 (only 2 days post delivery, SLA is 7 days)
    early_as_of = datetime(2026, 10, 29, 0, 0, tzinfo=timezone.utc).date()
    engine_early = ReconciliationEngine(db_session, as_of=early_as_of)
    recon_early = engine_early.reconcile_single_order(external_order_id=order_id, partner_id="shopify")

    assert recon_early.status == "pending"
    assert recon_early.money_at_risk == Decimal("0.00")

    # Case B: Evaluate on Nov 10 (14 days post delivery, past 7 days SLA)
    late_as_of = datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc).date()
    engine_late = ReconciliationEngine(db_session, as_of=late_as_of)
    recon_late = engine_late.reconcile_single_order(external_order_id=order_id, partner_id="shopify")

    assert recon_late.status == "unpaid_past_due"
    assert "cod_remittance_missing" in recon_late.reason_codes
    assert recon_late.money_at_risk > Decimal("0.00")


def test_missing_rate_card_handling(db_session):
    """
    Test missing rate card returns expected_amount=None, reason_code='missing_rate_card', status='pending'.
    """
    upload = get_test_upload(db_session, "shopify")
    order_id = "ORD-NO-RC-99"
    # Ancient date outside any rate card validity window
    order_dt = datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc)

    ev_order = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="order_placed",
        amount=Decimal("1500.00"),
        event_date=order_dt,
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id
    )
    db_session.add(ev_order)
    db_session.commit()

    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    recon = engine.reconcile_single_order(external_order_id=order_id, partner_id="shopify")

    assert recon.status == "pending"
    assert recon.expected_amount is None
    assert "missing_rate_card" in recon.reason_codes
    assert recon.money_at_risk == Decimal("0.00")


def test_tcs_tds_statutory_isolation(db_session):
    """
    Test TCS and TDS statutory deductions are isolated 100% and never treated as leakage.
    """
    upload = get_test_upload(db_session, "amazon")
    order_id = "ORD-TAX-ISOLATION-01"
    order_dt = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)

    # Order ₹999 on Amazon
    ev_order = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="amazon",
        event_type="orders",
        amount=Decimal("999.00"),
        event_date=order_dt,
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id
    )
    # Settlement with standard deductions + TCS ₹5 + TDS ₹1
    ev_settlement = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="amazon",
        event_type="settlement_credit",
        amount=Decimal("899.00"),
        settlement_credit=Decimal("899.00"),
        commission=Decimal("100.00"),
        tcs=Decimal("5.00"),
        tds=Decimal("1.00"),
        event_date=order_dt + timedelta(days=2),
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id
    )
    db_session.add(ev_order)
    db_session.add(ev_settlement)
    db_session.commit()

    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    recon = engine.reconcile_single_order(external_order_id=order_id, partner_id="amazon")

    assert recon.status == "settled"
    assert recon.tcs_amount == Decimal("5.00")
    assert recon.tds_amount == Decimal("1.00")
    assert recon.money_at_risk == Decimal("0.00")


def test_claims_preservation_on_rerun(db_session):
    """
    Test that re-running reconciliation and claims generation preserves manually edited notes,
    recovered amounts, and non-draft claim statuses (e.g. submitted, approved).
    """
    upload = get_test_upload(db_session, "shopify")
    order_id = "ORD-CLAIM-PRESERVE-01"
    order_dt = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)

    # Unpaid COD order -> ₹1,409 risk
    ev_order = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="order_placed",
        amount=Decimal("1499.00"),
        event_date=order_dt,
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id,
        raw_data={"Payment Method": "COD"}
    )
    db_session.add(ev_order)
    db_session.commit()

    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    engine.run_reconciliation(order_ids=[order_id])

    claims_gen = ClaimsGenerator(db_session)
    claims_gen.generate_draft_claims(order_ids=[order_id])

    # Find the generated claim
    claim = db_session.query(Claim).filter(Claim.external_order_id == order_id).first()
    assert claim is not None
    assert claim.claim_status == "draft"

    # Simulate manual user edit: update status to 'submitted', add executive notes and recovered amount
    claim.claim_status = "submitted"
    claim.notes = "Courier ticket #89412 filed with Delhivery ops team."
    claim.recovered_amount = Decimal("500.00")
    db_session.commit()

    # Re-run reconciliation and claims generation
    engine.run_reconciliation(order_ids=[order_id])
    claims_gen.generate_draft_claims(order_ids=[order_id])

    # Refresh claim from database
    refreshed_claim = db_session.query(Claim).filter(Claim.external_order_id == order_id).first()
    assert refreshed_claim.claim_status == "submitted"
    assert refreshed_claim.notes == "Courier ticket #89412 filed with Delhivery ops team."
    assert refreshed_claim.recovered_amount == Decimal("500.00")
