import uuid
import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.models.order_event import OrderEvent
from app.models.order_recon import OrderRecon
from app.models.claim import Claim
from app.models.tracking_event import TrackingEvent
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
        file_name="test_partner.csv",
        file_hash=str(uuid.uuid4()).replace("-", "") + str(uuid.uuid4()).replace("-", ""),
        file_size_bytes=100,
        row_count=5,
        processing_status="completed",
        uploaded_by=user.id
    )
    db_session.add(upload)
    db_session.flush()
    return upload


def test_two_partners_same_external_order_id_reconcile_independently(db_session):
    """
    Test that two different partners (e.g. shopify and amazon) can have the exact same external_order_id.
    Both must reconcile independently without overwriting or merging records,
    producing distinct internal canonical UUIDs and distinct claims.
    """
    shared_external_order_id = "ORD-DUAL-9999"
    order_dt = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    upload_shopify = get_test_upload(db_session, "shopify")
    upload_amazon = get_test_upload(db_session, "amazon")

    # 1. Insert order for Shopify
    ev_shopify = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=shared_external_order_id,
        source_partner_id="shopify",
        event_type="order_placed",
        amount=Decimal("1499.00"),
        event_date=order_dt,
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload_shopify.id,
        raw_data={"Payment Method": "COD"}
    )
    db_session.add(ev_shopify)

    # 2. Insert order for Amazon with same external order ID but different value and terms
    ev_amazon = OrderEvent(
        id=uuid.uuid4(),
        lineage_root_id=uuid.uuid4(),
        external_order_id=shared_external_order_id,
        source_partner_id="amazon",
        event_type="orders",
        amount=Decimal("999.00"),
        event_date=order_dt,
        idempotency_key=str(uuid.uuid4()),
        upload_id=upload_amazon.id,
        raw_data={"Payment Method": "Prepaid"}
    )
    db_session.add(ev_amazon)
    db_session.commit()

    # 3. Run reconciliation
    engine = ReconciliationEngine(db_session, as_of=DEFAULT_AS_OF_DATE)
    result = engine.run_reconciliation(order_ids=[shared_external_order_id])

    # 4. Verify both order_recon records exist
    recons = (
        db_session.query(OrderRecon)
        .filter(OrderRecon.external_order_id == shared_external_order_id)
        .all()
    )
    assert len(recons) == 2, f"Expected 2 distinct recon entries, got {len(recons)}"

    shopify_recon = next(r for r in recons if r.partner_id == "shopify")
    amazon_recon = next(r for r in recons if r.partner_id == "amazon")

    # Distinct canonical UUIDs
    assert shopify_recon.id != amazon_recon.id
    assert shopify_recon.external_order_id == shared_external_order_id
    assert amazon_recon.external_order_id == shared_external_order_id

    # Independent order values
    assert shopify_recon.order_value == Decimal("1499.00")
    assert amazon_recon.order_value == Decimal("999.00")

    # 5. Generate claims and verify independence
    claims_gen = ClaimsGenerator(db_session)
    claims = claims_gen.generate_draft_claims(order_ids=[shared_external_order_id])

    # Query claims by order_recon_id
    shopify_claims = db_session.query(Claim).filter(Claim.order_recon_id == shopify_recon.id).all()
    amazon_claims = db_session.query(Claim).filter(Claim.order_recon_id == amazon_recon.id).all()

    # Both have independent claims linked to their canonical order_recon_id
    assert len(shopify_claims) >= 1
    assert len(amazon_claims) >= 1
    assert shopify_claims[0].id != amazon_claims[0].id
    assert shopify_claims[0].partner_id == "shopify"
    assert amazon_claims[0].partner_id == "amazon"
