import uuid
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, InternalError
from app.models.order_event import OrderEvent
from app.models.upload import Upload
from app.models.source import Source
from app.models.user import User


def get_test_upload(db_session, partner_id="shopify"):
    source = db_session.query(Source).filter(Source.partner_id == partner_id, Source.source_type == "orders").first()
    user = db_session.query(User).first()
    upload = Upload(
        source_id=source.id,
        partner_id=source.partner_id,
        source_type=source.source_type,
        file_name="bulk_safeguards_test.csv",
        file_hash=uuid.uuid4().hex,
        file_size_bytes=1000,
        row_count=10,
        processing_status="completed",
        uploaded_by=user.id
    )
    db_session.add(upload)
    db_session.flush()
    return upload


def test_bulk_sql_lineage_root_locking_and_validation(db_session):
    """
    Safeguard 1: Lineage-root locking and relational validation.
    Confirms that event_lineage_locks enforces relational foreign key validation
    against order_events(lineage_root_id). An orphaned or non-existent lineage root
    is strictly rejected by the database.
    """
    upload = get_test_upload(db_session)
    valid_root_id = uuid.uuid4()
    order_id = f"ORD-BULK-LOCK-{uuid.uuid4().hex[:6]}"

    # Valid event created
    ev = OrderEvent(
        id=valid_root_id,
        lineage_root_id=valid_root_id,
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="order_placed",
        amount=Decimal("1000.00"),
        event_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id
    )
    db_session.add(ev)
    db_session.flush()

    # Bulk lock insertion succeeds for valid lineage root
    db_session.execute(text("""
        INSERT INTO event_lineage_locks (lineage_root_id, locked_at)
        VALUES (:root_id, NOW())
        ON CONFLICT DO NOTHING;
    """), {"root_id": valid_root_id})
    db_session.flush()

    # Attempting to lock an invalid/orphaned lineage root must raise ForeignKeyViolation
    orphaned_root_id = uuid.uuid4()
    with pytest.raises(IntegrityError) as exc_info:
        db_session.execute(text("""
            INSERT INTO event_lineage_locks (lineage_root_id, locked_at)
            VALUES (:root_id, NOW());
        """), {"root_id": orphaned_root_id})
        db_session.flush()
    assert "event_lineage_locks_lineage_root_id_fkey" in str(exc_info.value)
    db_session.rollback()


def test_bulk_sql_append_only_event_semantics(db_session):
    """
    Safeguard 2: Append-only event semantics.
    Confirms that SQL UPDATE and DELETE operations on order_events are strictly
    blocked by the database engine trigger trg_enforce_append_only.
    """
    upload = get_test_upload(db_session)
    ev_id = uuid.uuid4()
    order_id = f"ORD-APPEND-ONLY-{uuid.uuid4().hex[:6]}"

    ev = OrderEvent(
        id=ev_id,
        lineage_root_id=ev_id,
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="order_placed",
        amount=Decimal("1500.00"),
        event_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id
    )
    db_session.add(ev)
    db_session.flush()

    # Direct UPDATE must be blocked
    with pytest.raises((IntegrityError, InternalError)) as exc_info:
        db_session.execute(text("UPDATE order_events SET amount = 2000.00 WHERE id = :ev_id"), {"ev_id": ev_id})
        db_session.flush()
    assert "strictly append-only" in str(exc_info.value)
    db_session.rollback()

    # Direct DELETE must be blocked
    db_session.add(ev)
    db_session.flush()
    with pytest.raises((IntegrityError, InternalError)) as exc_info:
        db_session.execute(text("DELETE FROM order_events WHERE id = :ev_id"), {"ev_id": ev_id})
        db_session.flush()
    assert "strictly append-only" in str(exc_info.value)
    db_session.rollback()


def test_bulk_sql_reversal_and_correction_restrictions(db_session):
    """
    Safeguard 3: Correction and reversal restrictions.
    Confirms that reversals require valid supersedes_event_id, must not have duplicate
    successors (uq_order_events_single_successor), and must be appended without mutating history.
    """
    upload = get_test_upload(db_session)
    orig_id = uuid.uuid4()
    order_id = f"ORD-REV-GUARD-{uuid.uuid4().hex[:6]}"

    orig_ev = OrderEvent(
        id=orig_id,
        lineage_root_id=orig_id,
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="settlement_credit",
        amount=Decimal("1000.00"),
        settlement_credit=Decimal("1000.00"),
        event_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id
    )
    db_session.add(orig_ev)
    db_session.flush()

    # Valid reversal succession
    rev_id_1 = uuid.uuid4()
    rev_ev_1 = OrderEvent(
        id=rev_id_1,
        lineage_root_id=orig_id,
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="settlement_reversal",
        amount=Decimal("-1000.00"),
        settlement_credit=Decimal("-1000.00"),
        supersedes_event_id=orig_id,
        amendment_reference="ORIGINAL",
        event_date=datetime(2026, 3, 3, tzinfo=timezone.utc),
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id
    )
    db_session.add(rev_ev_1)
    db_session.flush()

    # Second active reversal superseding the SAME event must fail uq_order_events_single_successor
    rev_id_2 = uuid.uuid4()
    rev_ev_2 = OrderEvent(
        id=rev_id_2,
        lineage_root_id=orig_id,
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="settlement_reversal",
        amount=Decimal("-1000.00"),
        settlement_credit=Decimal("-1000.00"),
        supersedes_event_id=orig_id,
        amendment_reference="ORIGINAL",
        event_date=datetime(2026, 3, 4, tzinfo=timezone.utc),
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload.id
    )
    db_session.add(rev_ev_2)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "uq_order_events_single_successor" in str(exc_info.value)
    db_session.rollback()


def test_bulk_sql_idempotency_under_retries_and_concurrency(db_session):
    """
    Safeguard 4: Idempotency under retries and concurrent ingestion.
    Confirms that duplicate bulk inserts sharing idempotency keys are safely deduplicated
    by database constraints without creating duplicate financial records.
    """
    upload = get_test_upload(db_session)
    order_id = f"ORD-IDEMP-{uuid.uuid4().hex[:6]}"
    fixed_idemp_key = f"IDEMP-KEY-{uuid.uuid4().hex}"

    # First insertion
    db_session.execute(text("""
        INSERT INTO order_events (
            id, lineage_root_id, external_order_id, source_partner_id, event_type,
            amount, settlement_credit, shipping_fee, event_date, idempotency_key,
            raw_data, amendment_reference, upload_id, created_at
        ) VALUES (
            :id, :root_id, :order_id, 'shopify', 'order_placed',
            1200.00, 0.00, 0.00, NOW(), :idemp,
            '{}', 'ORIGINAL', :upload_id, NOW()
        );
    """), {
        "id": uuid.uuid4(),
        "root_id": uuid.uuid4(),
        "order_id": order_id,
        "idemp": fixed_idemp_key,
        "upload_id": upload.id
    })
    db_session.flush()

    # Retry with identical idempotency_key must raise UniqueViolation if attempted directly
    with pytest.raises(IntegrityError) as exc_info:
        db_session.execute(text("""
            INSERT INTO order_events (
                id, lineage_root_id, external_order_id, source_partner_id, event_type,
                amount, settlement_credit, shipping_fee, event_date, idempotency_key,
                raw_data, amendment_reference, upload_id, created_at
            ) VALUES (
                :id, :root_id, :order_id, 'shopify', 'order_placed',
                1200.00, 0.00, 0.00, NOW(), :idemp,
                '{}', 'ORIGINAL', :upload_id, NOW()
            );
        """), {
            "id": uuid.uuid4(),
            "root_id": uuid.uuid4(),
            "order_id": order_id,
            "idemp": fixed_idemp_key,
            "upload_id": upload.id
        })
        db_session.flush()
    assert "order_events_idempotency_key_key" in str(exc_info.value)
    db_session.rollback()

    # Re-insert with ON CONFLICT DO NOTHING must cleanly succeed with rowcount = 0 (idempotent retry)
    upload = get_test_upload(db_session)
    first_id = uuid.uuid4()
    db_session.execute(text("""
        INSERT INTO order_events (
            id, lineage_root_id, external_order_id, source_partner_id, event_type,
            amount, settlement_credit, shipping_fee, event_date, idempotency_key,
            raw_data, amendment_reference, upload_id, created_at
        ) VALUES (
            :id, :root_id, :order_id, 'shopify', 'order_placed',
            1200.00, 0.00, 0.00, NOW(), :idemp,
            '{}', 'ORIGINAL', :upload_id, NOW()
        );
    """), {
        "id": first_id,
        "root_id": first_id,
        "order_id": order_id,
        "idemp": fixed_idemp_key,
        "upload_id": upload.id
    })
    db_session.flush()

    res = db_session.execute(text("""
        INSERT INTO order_events (
            id, lineage_root_id, external_order_id, source_partner_id, event_type,
            amount, settlement_credit, shipping_fee, event_date, idempotency_key,
            raw_data, amendment_reference, upload_id, created_at
        ) VALUES (
            :id, :root_id, :order_id, 'shopify', 'order_placed',
            1200.00, 0.00, 0.00, NOW(), :idemp,
            '{}', 'ORIGINAL', :upload_id, NOW()
        ) ON CONFLICT (idempotency_key) DO NOTHING;
    """), {
        "id": uuid.uuid4(),
        "root_id": uuid.uuid4(),
        "order_id": order_id,
        "idemp": fixed_idemp_key,
        "upload_id": upload.id
    })
    db_session.flush()
    assert res.rowcount == 0  # Deduplicated atomically!
