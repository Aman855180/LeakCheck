import uuid
import pytest
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal

from app.models.order_event import OrderEvent
from app.models.tracking_event import TrackingEvent
from app.models.warehouse_receipt import WarehouseReceipt
from app.models.order_recon import OrderRecon
from app.models.claim import Claim
from app.models.upload import Upload
from app.models.source import Source
from app.models.user import User
from app.services.recon_engine import ReconciliationEngine, DEFAULT_AS_OF_DATE
from app.services.claims_generator import ClaimsGenerator


def get_test_upload(db_session, partner_id="shopify", source_type="orders") -> Upload:
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


def create_order_event(
    db_session,
    order_id: str,
    partner_id: str,
    event_type: str,
    amount: Decimal,
    event_date: datetime,
    raw_data: dict = None,
    settlement_credit: Decimal = None,
    shipping_fee: Decimal = None
) -> OrderEvent:
    event_id = uuid.uuid4()
    ev = OrderEvent(
        id=event_id,
        lineage_root_id=event_id,
        external_order_id=order_id,
        source_partner_id=partner_id,
        event_type=event_type,
        amount=amount,
        settlement_credit=settlement_credit or (amount if "settlement" in event_type else Decimal("0.00")),
        shipping_fee=shipping_fee or Decimal("0.00"),
        event_date=event_date,
        idempotency_key=str(uuid.uuid4()),
        raw_data=raw_data or {}
    )
    db_session.add(ev)
    db_session.flush()
    return ev


def test_sample_1_unpaid_past_due(db_session):
    """
    Sample 1 — ORD-W-204118 (Website COD)
    Order Value: ₹1,499. Expected: ₹1,409. Received: ₹0.
    Status: unpaid_past_due, Money at Risk: ₹1,409.
    """
    test_upload = get_test_upload(db_session, "shopify")
    order_id = "ORD-W-204118"
    order_dt = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    delivery_dt = datetime(2026, 3, 4, 12, 0, tzinfo=timezone.utc)

    # 1. Order placed
    create_order_event(
        db_session, order_id, "shopify", "order_placed",
        Decimal("1499.00"), order_dt, raw_data={"Payment Method": "COD"}
    )
    # 2. Tracking delivered
    trk = TrackingEvent(
        order_id=order_id,
        tracking_number="DEL-AWB-204118",
        courier_code="delhivery",
        event_timestamp=delivery_dt,
        raw_status_code="DELIVERED",
        raw_telemetry={},
        verification_outcome="VALID_DELIVERY",
        upload_id=test_upload.id,
        source_row_number=1
    )
    db_session.add(trk)
    db_session.commit()

    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    recon = engine.reconcile_single_order(order_id)
    db_session.commit()

    assert recon is not None
    assert recon.status == "unpaid_past_due"
    assert recon.expected_amount == Decimal("1409.00")
    assert recon.received_amount == Decimal("0.00")
    assert recon.difference == Decimal("-1409.00")
    assert recon.money_at_risk == Decimal("1409.00")
    assert "cod_remittance_missing" in recon.reason_codes
    assert recon.age_days > 30
    assert recon.age_bucket == "31+"


def test_sample_2_short_paid(db_session):
    """
    Sample 2 — ORD-M-88120 (Amazon Marketplace)
    Order Value: ₹1,199. Expected: ₹899. Received: ₹862.
    Difference: -₹37. Status: short_paid, Money at Risk: ₹37.
    """
    order_id = "ORD-M-88120"
    order_dt = datetime(2026, 3, 2, 11, 0, tzinfo=timezone.utc)

    # Order placed
    create_order_event(
        db_session, order_id, "amazon", "order_placed",
        Decimal("1199.00"), order_dt, raw_data={"Payment Method": "PREPAID"}
    )
    # Settlement received with shortfall
    create_order_event(
        db_session, order_id, "amazon", "settlement_credit",
        Decimal("862.00"), order_dt + timedelta(days=5),
        settlement_credit=Decimal("862.00")
    )
    db_session.commit()

    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    recon = engine.reconcile_single_order(order_id)
    db_session.commit()

    assert recon is not None
    assert recon.status == "short_paid"
    assert recon.expected_amount == Decimal("899.00")
    assert recon.received_amount == Decimal("862.00")
    assert recon.difference == Decimal("-37.00")
    assert recon.money_at_risk == Decimal("37.00")
    assert "settlement_shortfall" in recon.reason_codes


def test_sample_3_returned_excess_deduction(db_session):
    """
    Sample 3 — ORD-W-204377 (Website Prepaid Return)
    Order Value: ₹2,398. Expected Net: -₹96. Received: -₹142.
    Difference: -₹46. Status: short_paid, reason: excess_return_deduction, Money at Risk: ₹46.
    """
    test_upload = get_test_upload(db_session, "shopify")
    order_id = "ORD-W-204377"
    order_dt = datetime(2026, 3, 3, 14, 0, tzinfo=timezone.utc)

    # Order placed
    create_order_event(
        db_session, order_id, "shopify", "order_placed",
        Decimal("2398.00"), order_dt, raw_data={"Payment Method": "PREPAID"}
    )
    # Tracking status RTO
    trk = TrackingEvent(
        order_id=order_id,
        tracking_number="BD-WB-204377",
        courier_code="bluedart",
        event_timestamp=order_dt + timedelta(days=2),
        raw_status_code="RTO",
        raw_telemetry={},
        verification_outcome="RTO",
        upload_id=test_upload.id,
        source_row_number=1
    )
    db_session.add(trk)

    # Warehouse receipt delivered
    wh_receipt = WarehouseReceipt(
        order_id=order_id,
        tracking_number="BD-WB-204377",
        warehouse_id="WH-BLR-01",
        received_at=order_dt + timedelta(days=5),
        receipt_status="delivered",
        upload_id=test_upload.id,
        source_row_number=1
    )
    db_session.add(wh_receipt)

    # Settlement deduction was -₹142 (actual freight was ₹142 instead of expected ₹96)
    create_order_event(
        db_session, order_id, "shopify", "settlement_credit",
        Decimal("-142.00"), order_dt + timedelta(days=6),
        settlement_credit=Decimal("-142.00"),
        shipping_fee=Decimal("142.00")
    )
    db_session.commit()

    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    recon = engine.reconcile_single_order(order_id)
    db_session.commit()

    assert recon is not None
    assert recon.status == "short_paid"
    assert recon.expected_amount == Decimal("-96.00")
    assert recon.received_amount == Decimal("-142.00")
    assert recon.difference == Decimal("-46.00")
    assert recon.money_at_risk == Decimal("46.00")
    assert "excess_return_deduction" in recon.reason_codes


def test_materiality_threshold_10_rupees(db_session):
    """
    Materiality: differences <= ₹10 are classified as settled.
    Difference of -₹10.00 is settled (₹0 risk).
    Difference of -₹10.01 is short_paid (₹10.01 risk).
    """
    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)

    # Case A: exactly ₹10 difference
    order_a = "ORD-TEST-MAT-10"
    create_order_event(db_session, order_a, "shopify", "order_placed", Decimal("1499.00"), datetime(2026, 3, 1, tzinfo=timezone.utc), raw_data={"Payment Method": "COD"})
    create_order_event(db_session, order_a, "shopify", "cod_remittance", Decimal("1399.00"), datetime(2026, 3, 5, tzinfo=timezone.utc)) # Expected 1409 - Received 1399 = -10.00
    recon_a = engine.reconcile_single_order(order_a)

    assert recon_a.difference == Decimal("-10.00")
    assert recon_a.status == "settled"
    assert recon_a.money_at_risk == Decimal("0.00")

    # Case B: ₹10.01 difference
    order_b = "ORD-TEST-MAT-10-01"
    create_order_event(db_session, order_b, "shopify", "order_placed", Decimal("1499.00"), datetime(2026, 3, 1, tzinfo=timezone.utc), raw_data={"Payment Method": "COD"})
    create_order_event(db_session, order_b, "shopify", "cod_remittance", Decimal("1398.99"), datetime(2026, 3, 5, tzinfo=timezone.utc)) # Expected 1409 - Received 1398.99 = -10.01
    recon_b = engine.reconcile_single_order(order_b)

    assert recon_b.difference == Decimal("-10.01")
    assert recon_b.status == "short_paid"
    assert recon_b.money_at_risk == Decimal("10.01")


def test_overpayment_policy_zero_risk(db_session):
    """
    Overpayment: received > expected by > ₹10.
    Status remains 'settled', tagged with 'overpaid_review', Money at Risk is ₹0.00.
    """
    order_id = "ORD-TEST-OVERPAY"
    create_order_event(db_session, order_id, "shopify", "order_placed", Decimal("1499.00"), datetime(2026, 3, 1, tzinfo=timezone.utc), raw_data={"Payment Method": "COD"})
    create_order_event(db_session, order_id, "shopify", "cod_remittance", Decimal("1509.00"), datetime(2026, 3, 5, tzinfo=timezone.utc)) # Expected 1409 -> +₹100 overpaid

    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    recon = engine.reconcile_single_order(order_id)

    assert recon.difference == Decimal("100.00")
    assert recon.status == "settled"
    assert "overpaid_review" in recon.reason_codes
    assert recon.money_at_risk == Decimal("0.00")


def test_claims_generation_and_preservation(db_session):
    """
    Claims generation: generates draft claims with UNIQUE(order_id, claim_reason),
    and does NOT overwrite executive notes or recovered amount.
    """
    order_id = "ORD-CLAIM-TEST"
    create_order_event(db_session, order_id, "amazon", "order_placed", Decimal("1199.00"), datetime(2026, 3, 2, tzinfo=timezone.utc), raw_data={"Payment Method": "PREPAID"})
    create_order_event(db_session, order_id, "amazon", "settlement_credit", Decimal("800.00"), datetime(2026, 3, 7, tzinfo=timezone.utc)) # Expected 899 -> Short by 99

    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    engine.run_reconciliation(order_ids=[order_id])

    claims_gen = ClaimsGenerator(db_session)
    claims = claims_gen.generate_draft_claims(order_ids=[order_id])
    assert len(claims) == 1
    claim = claims[0]
    assert claim.claim_amount == Decimal("99.00")
    assert claim.claim_status == "draft"

    # Simulate executive adding notes and partial recovery
    claim.notes = "Contacted Amazon seller support case #98124"
    claim.claim_status = "submitted"
    claim.recovered_amount = Decimal("50.00")
    db_session.add(claim)
    db_session.commit()

    # Re-run claim generation
    claims_re = claims_gen.generate_draft_claims(order_ids=[order_id])
    assert len(claims_re) == 1
    re_claim = claims_re[0]
    # Assert manual modifications are strictly preserved
    assert re_claim.notes == "Contacted Amazon seller support case #98124"
    assert re_claim.claim_status == "submitted"
    assert re_claim.recovered_amount == Decimal("50.00")
