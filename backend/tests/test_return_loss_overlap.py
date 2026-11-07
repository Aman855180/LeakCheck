import uuid
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.models.order_event import OrderEvent
from app.models.tracking_event import TrackingEvent
from app.models.warehouse_receipt import WarehouseReceipt
from app.models.order_recon import OrderRecon
from app.models.upload import Upload
from app.models.source import Source
from app.models.user import User
from app.services.recon_engine import ReconciliationEngine, DEFAULT_AS_OF_DATE


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


def create_missing_return_base(db_session, order_id: str, order_value: Decimal, order_dt: datetime):
    upload = get_test_upload(db_session, "shopify")
    delivery_dt = order_dt + timedelta(days=3)

    # 1. Order placed
    ev_order = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="order_placed",
        amount=order_value,
        event_date=order_dt,
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id,
        raw_data={"Payment Method": "Prepaid"}
    )
    db_session.add(ev_order)

    # 2. Return tracking scan (RTO verified dock delivery)
    trk = TrackingEvent(
        order_id=order_id,
        tracking_number=f"DEL-{order_id}",
        courier_code="delhivery",
        event_timestamp=delivery_dt,
        raw_status_code="RTO_DELIVERED_TO_DOCK",
        raw_telemetry={"status": "returned"},
        verification_outcome="verified_dock_delivery",
        upload_id=upload.id,
        source_row_number=1
    )
    db_session.add(trk)
    # No warehouse receipt scan is inserted -> return is missing at warehouse
    db_session.commit()
    return upload


def test_full_return_with_full_refund_exposure(db_session):
    """
    Scenario 1: Full return with full refund exposure.
    Order value: ₹1,000. Customer refunded ₹1,000 via settlement reversal.
    Warehouse scan missing.
    Expected: return_loss = ₹1,000, Money at Risk = ₹1,000.
    """
    order_id = f"ORD-RET-FULL-01-{uuid.uuid4().hex[:6]}"
    order_dt = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    upload = create_missing_return_base(db_session, order_id, Decimal("1000.00"), order_dt)

    # Settlement reversal of ₹1,000
    ev_refund = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="settlement_reversal",
        amount=Decimal("-1000.00"),
        settlement_credit=Decimal("-1000.00"),
        event_date=order_dt + timedelta(days=5),
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id,
        raw_data={}
    )
    db_session.add(ev_refund)
    db_session.commit()

    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    recon = engine.reconcile_single_order(external_order_id=order_id, partner_id="shopify")

    assert recon.status == "return_not_received"
    assert recon.return_loss_component == Decimal("1000.00")
    assert recon.money_at_risk == Decimal("1000.00")
    # Verify audit details
    audit = recon.breakdown_json["return_loss_breakdown"]
    assert audit["is_return_missing"] is True
    assert audit["evidenced_refund_exposure"] == "1000.00"
    assert audit["gross_return_loss"] == "1000.00"
    assert audit["cap_applied"] is False


def test_partial_refund_exposure(db_session):
    """
    Scenario 2: Partial refund exposure.
    Order value: ₹1,000. Only ₹400 refunded.
    Expected: return_loss = ₹400, Money at Risk = ₹400.
    """
    order_id = f"ORD-RET-PARTIAL-02-{uuid.uuid4().hex[:6]}"
    order_dt = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    upload = create_missing_return_base(db_session, order_id, Decimal("1000.00"), order_dt)

    # Partial refund of ₹400
    ev_refund = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="settlement_reversal",
        amount=Decimal("-400.00"),
        settlement_credit=Decimal("-400.00"),
        event_date=order_dt + timedelta(days=5),
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id,
        raw_data={}
    )
    db_session.add(ev_refund)
    db_session.commit()

    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    recon = engine.reconcile_single_order(external_order_id=order_id, partner_id="shopify")

    assert recon.status == "return_not_received"
    assert recon.return_loss_component == Decimal("400.00")
    assert recon.money_at_risk == Decimal("400.00")
    audit = recon.breakdown_json["return_loss_breakdown"]
    assert audit["evidenced_refund_exposure"] == "400.00"
    assert audit["gross_return_loss"] == "400.00"


def test_return_without_sufficient_financial_evidence(db_session):
    """
    Scenario 3: Return without sufficient financial evidence.
    Warehouse receipt is missing, but no refund/reversal has been deducted by partner yet.
    Expected: return_loss = ₹0.00 (no speculative leakage).
    """
    order_id = f"ORD-RET-NO-REFUND-03-{uuid.uuid4().hex[:6]}"
    order_dt = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    # Only base order and RTO scan, NO refund event
    create_missing_return_base(db_session, order_id, Decimal("1000.00"), order_dt)

    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    recon = engine.reconcile_single_order(external_order_id=order_id, partner_id="shopify")

    assert recon.status == "return_not_received"
    assert recon.return_loss_component == Decimal("0.00")
    assert recon.money_at_risk == Decimal("0.00")
    audit = recon.breakdown_json["return_loss_breakdown"]
    assert audit["evidenced_refund_exposure"] == "0.00"
    assert audit["gross_return_loss"] == "0.00"


def test_return_loss_overlapping_settlement_shortfall(db_session):
    """
    Scenario 4: Return loss overlapping settlement shortfall.
    Order value: ₹1,000. Refund: ₹1,000.
    The refund caused raw settlement gap of ₹1,000.
    Overlap must be deducted from settlement gap so total risk is strictly ₹1,000 (not double counted as ₹2,000).
    """
    order_id = f"ORD-RET-OVERLAP-04-{uuid.uuid4().hex[:6]}"
    order_dt = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    upload = create_missing_return_base(db_session, order_id, Decimal("1000.00"), order_dt)

    # Initial settlement credit +1000, then refund -1000
    ev_credit = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="settlement_credit",
        amount=Decimal("1000.00"),
        settlement_credit=Decimal("1000.00"),
        event_date=order_dt + timedelta(days=2),
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id
    )
    ev_refund = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="settlement_reversal",
        amount=Decimal("-1000.00"),
        settlement_credit=Decimal("-1000.00"),
        event_date=order_dt + timedelta(days=5),
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id
    )
    db_session.add(ev_credit)
    db_session.add(ev_refund)
    db_session.commit()

    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    recon = engine.reconcile_single_order(external_order_id=order_id, partner_id="shopify")

    # Net received is 0, expected is around 900+ (or return tariff)
    # The return loss owns the refund exposure
    assert recon.status == "return_not_received"
    assert recon.return_loss_component == Decimal("1000.00")
    # Total risk must NOT double count to 2,000
    assert recon.settlement_gap_component == Decimal("0.00")
    assert recon.money_at_risk == Decimal("1000.00")


def test_return_exposure_exceeding_order_value(db_session):
    """
    Scenario 5: Return exposure exceeding order value (e.g. erroneous partner chargeback).
    Order value: ₹1,000. Errant reversal: ₹1,200.
    Expected: return_loss capped at ₹1,000, cap_applied = True.
    """
    order_id = f"ORD-RET-EXCEED-05-{uuid.uuid4().hex[:6]}"
    order_dt = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    upload = create_missing_return_base(db_session, order_id, Decimal("1000.00"), order_dt)

    # Errant reversal of ₹1,200
    ev_refund = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="settlement_reversal",
        amount=Decimal("-1200.00"),
        settlement_credit=Decimal("-1200.00"),
        event_date=order_dt + timedelta(days=5),
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id
    )
    db_session.add(ev_refund)
    db_session.commit()

    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    recon = engine.reconcile_single_order(external_order_id=order_id, partner_id="shopify")

    assert recon.status == "return_not_received"
    assert recon.return_loss_component == Decimal("1000.00")
    assert recon.money_at_risk == Decimal("1000.00")
    audit = recon.breakdown_json["return_loss_breakdown"]
    assert audit["cap_applied"] is True
    assert audit["evidenced_refund_exposure"] == "1200.00"
    assert audit["gross_return_loss"] == "1000.00"


def test_return_loss_with_unrelated_settlement_shortfall(db_session):
    """
    Scenario 6: Return loss with unrelated settlement shortfall.
    Subtract only the settlement gap amount attributable to the same refund exposure.
    Do NOT subtract unrelated settlement shortfalls.
    Order value: ₹1,000.
    Unrelated settlement shortfall: ₹100.
    Refund exposure: ₹400.
    Total Money at Risk must equal ₹100 (unrelated shortfall) + ₹400 (return loss) = ₹500.
    """
    order_id = f"ORD-RET-UNRELATED-06-{uuid.uuid4().hex[:6]}"
    order_dt = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    upload = create_missing_return_base(db_session, order_id, Decimal("1000.00"), order_dt)

    # Initial settlement had a shortfall of ₹100
    # Expected was ~₹904. Received forward was only ₹804. Shortfall = ₹100.
    # Then refund reversal of ₹400 took place.
    ev_forward = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="settlement_credit",
        amount=Decimal("404.00"), # 804 - 400 net = 404
        settlement_credit=Decimal("404.00"),
        event_date=order_dt + timedelta(days=2),
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id
    )
    ev_refund = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="settlement_reversal",
        amount=Decimal("-400.00"),
        settlement_credit=Decimal("-400.00"),
        event_date=order_dt + timedelta(days=5),
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id
    )
    db_session.add(ev_forward)
    db_session.add(ev_refund)
    db_session.commit()

    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    recon = engine.reconcile_single_order(external_order_id=order_id, partner_id="shopify")

    assert recon.status == "return_not_received"
    assert recon.return_loss_component == Decimal("400.00")
    audit = recon.breakdown_json["return_loss_breakdown"]
    assert audit["net_return_loss"] == "400.00"
