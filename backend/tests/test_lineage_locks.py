import uuid
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from app.models.order_event import OrderEvent, EventLineageLock


def test_append_only_trigger_blocks_update(db_session):
    """Verify order_events update operations are forbidden by trigger."""
    event = OrderEvent(
        idempotency_key="test_immut_001",
        external_order_id="ORD-TEST-001",
        source_partner_id="shopify",
        event_type="settlement_credit",
        event_date=datetime.now(timezone.utc),
        amount=Decimal("1000.00"),
        settlement_credit=Decimal("1000.00"),
        lineage_root_id=uuid.uuid4()
    )
    db_session.add(event)
    db_session.flush()

    with pytest.raises(DBAPIError) as exc_info:
        with db_session.begin_nested():
            db_session.execute(
                text("UPDATE order_events SET amount = 999.00 WHERE id = :id"),
                {"id": event.id}
            )
            db_session.flush()

    assert "strictly append-only" in str(exc_info.value)


def test_append_only_trigger_blocks_delete(db_session):
    """Verify order_events delete operations are forbidden by trigger."""
    event = OrderEvent(
        idempotency_key="test_immut_002",
        external_order_id="ORD-TEST-002",
        source_partner_id="shopify",
        event_type="settlement_credit",
        event_date=datetime.now(timezone.utc),
        amount=Decimal("500.00"),
        settlement_credit=Decimal("500.00"),
        lineage_root_id=uuid.uuid4()
    )
    db_session.add(event)
    db_session.flush()

    with pytest.raises(DBAPIError) as exc_info:
        with db_session.begin_nested():
            db_session.execute(
                text("DELETE FROM order_events WHERE id = :id"),
                {"id": event.id}
            )
            db_session.flush()

    assert "strictly append-only" in str(exc_info.value)


def test_lineage_lock_creation_and_inheritance(db_session):
    """Verify original event creates lineage lock in same transaction and correction inherits it."""
    orig_id = uuid.uuid4()
    orig_event = OrderEvent(
        id=orig_id,
        idempotency_key="test_lin_001",
        external_order_id="ORD-LIN-001",
        source_partner_id="shopify",
        event_type="settlement_credit",
        event_date=datetime.now(timezone.utc),
        amount=Decimal("1000.00"),
        settlement_credit=Decimal("1000.00"),
        lineage_root_id=orig_id
    )
    db_session.add(orig_event)
    db_session.flush()

    # Verify lock row was created by AFTER INSERT trigger
    lock = db_session.query(EventLineageLock).filter(
        EventLineageLock.lineage_root_id == orig_id
    ).first()
    assert lock is not None

    # Insert correction E2 superseding E1
    corr_id = uuid.uuid4()
    corr_event = OrderEvent(
        id=corr_id,
        idempotency_key="test_lin_002",
        external_order_id="ORD-LIN-001",
        source_partner_id="shopify",
        event_type="settlement_credit",
        amendment_reference="REV-01",
        event_date=datetime.now(timezone.utc),
        amount=Decimal("950.00"),
        settlement_credit=Decimal("950.00"),
        lineage_root_id=orig_id,
        supersedes_event_id=orig_id
    )
    db_session.add(corr_event)
    db_session.flush()

    assert corr_event.lineage_root_id == orig_id


def test_reversal_validation_rules(db_session):
    """Verify reversals must have opposite sign and cannot exceed parent amount."""
    e_id = uuid.uuid4()
    base_event = OrderEvent(
        id=e_id,
        idempotency_key="test_rev_base_001",
        external_order_id="ORD-REV-001",
        source_partner_id="amazon",
        event_type="settlement_credit",
        event_date=datetime.now(timezone.utc),
        amount=Decimal("1000.00"),
        settlement_credit=Decimal("1000.00"),
        lineage_root_id=e_id
    )
    db_session.add(base_event)
    db_session.flush()

    # Reversal with same positive sign must fail
    bad_rev = OrderEvent(
        idempotency_key="test_rev_bad_sign",
        external_order_id="ORD-REV-001",
        source_partner_id="amazon",
        event_type="settlement_reversal",
        event_date=datetime.now(timezone.utc),
        amount=Decimal("200.00"),  # Positive is invalid
        lineage_root_id=e_id,
        reverses_event_id=e_id
    )
    with pytest.raises(DBAPIError) as exc_info:
        with db_session.begin_nested():
            db_session.add(bad_rev)
            db_session.flush()
    assert "opposite sign" in str(exc_info.value)

    # Valid partial reversal R1 = -200
    r1 = OrderEvent(
        idempotency_key="test_rev_r1",
        external_order_id="ORD-REV-001",
        source_partner_id="amazon",
        event_type="settlement_reversal",
        event_date=datetime.now(timezone.utc),
        amount=Decimal("-200.00"),
        lineage_root_id=e_id,
        reverses_event_id=e_id
    )
    db_session.add(r1)
    db_session.flush()

    # Reversal exceeding remaining cap (-900 on 1000 where 200 is already reversed) must fail
    excess_rev = OrderEvent(
        idempotency_key="test_rev_excess",
        external_order_id="ORD-REV-001",
        source_partner_id="amazon",
        event_type="settlement_reversal",
        event_date=datetime.now(timezone.utc),
        amount=Decimal("-900.00"),  # 200 + 900 = 1100 > 1000
        lineage_root_id=e_id,
        reverses_event_id=e_id
    )
    with pytest.raises(DBAPIError) as exc_info:
        with db_session.begin_nested():
            db_session.add(excess_rev)
            db_session.flush()
    assert "exceed" in str(exc_info.value)


def test_correction_with_existing_reversals_numerical(db_session):
    """Verify E1=1000, R1=-200, E2=900 succeeds, but E3=150 fails (200 > 150)."""
    e1_id = uuid.uuid4()
    e1 = OrderEvent(
        id=e1_id,
        idempotency_key="test_num_e1",
        external_order_id="ORD-NUM-001",
        source_partner_id="shopify",
        event_type="settlement_credit",
        event_date=datetime.now(timezone.utc),
        amount=Decimal("1000.00"),
        settlement_credit=Decimal("1000.00"),
        lineage_root_id=e1_id
    )
    db_session.add(e1)
    db_session.flush()

    # Partial reversal R1 = -200
    r1_id = uuid.uuid4()
    r1 = OrderEvent(
        id=r1_id,
        idempotency_key="test_num_r1",
        external_order_id="ORD-NUM-001",
        source_partner_id="shopify",
        event_type="settlement_reversal",
        event_date=datetime.now(timezone.utc),
        amount=Decimal("-200.00"),
        lineage_root_id=e1_id,
        reverses_event_id=e1_id
    )
    db_session.add(r1)
    db_session.flush()

    # E2 = 900 supersedes E1 (900 >= 200 active reversals -> SUCCESS)
    e2_id = uuid.uuid4()
    e2 = OrderEvent(
        id=e2_id,
        idempotency_key="test_num_e2",
        external_order_id="ORD-NUM-001",
        source_partner_id="shopify",
        event_type="settlement_credit",
        amendment_reference="REV-01",
        event_date=datetime.now(timezone.utc),
        amount=Decimal("900.00"),
        settlement_credit=Decimal("900.00"),
        lineage_root_id=e1_id,
        supersedes_event_id=e1_id
    )
    db_session.add(e2)
    db_session.flush()

    # E3 = 150 supersedes E2 (150 < 200 active reversals -> MUST BE REJECTED)
    e3_id = uuid.uuid4()
    e3 = OrderEvent(
        id=e3_id,
        idempotency_key="test_num_e3",
        external_order_id="ORD-NUM-001",
        source_partner_id="shopify",
        event_type="settlement_credit",
        amendment_reference="REV-02",
        event_date=datetime.now(timezone.utc),
        amount=Decimal("150.00"),
        settlement_credit=Decimal("150.00"),
        lineage_root_id=e1_id,
        supersedes_event_id=e2_id
    )
    with pytest.raises(DBAPIError) as exc_info:
        with db_session.begin_nested():
            db_session.add(e3)
            db_session.flush()
    assert "less than active reversals" in str(exc_info.value)
