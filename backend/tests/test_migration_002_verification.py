import uuid
import pytest
from sqlalchemy import text


def test_migration_002_populated_database_backfill(db_session):
    """
    Demonstrates that Alembic migration 002 logic correctly migrates a populated database
    with pre-existing claims and order_recon rows, backfilling external_order_id and
    linking claims to canonical order_recon_id foreign keys without data loss.
    """
    # Create temporary legacy tables matching pre-migration 001 schema
    db_session.execute(text("""
        CREATE TEMP TABLE legacy_order_recon (
            id UUID PRIMARY KEY,
            order_id VARCHAR(128) NOT NULL,
            partner_id VARCHAR(64) NOT NULL
        ) ON COMMIT DROP;
    """))
    db_session.execute(text("""
        CREATE TEMP TABLE legacy_claims (
            id UUID PRIMARY KEY,
            order_id VARCHAR(128) NOT NULL,
            partner_id VARCHAR(64) NOT NULL,
            claim_amount NUMERIC(12,2) NOT NULL,
            claim_reason VARCHAR(64) NOT NULL
        ) ON COMMIT DROP;
    """))

    # Seed legacy populated data
    recon_uuid = uuid.uuid4()
    claim_uuid = uuid.uuid4()
    db_session.execute(
        text("INSERT INTO legacy_order_recon (id, order_id, partner_id) VALUES (:id, :order_id, :partner_id)"),
        {"id": recon_uuid, "order_id": "ORD-LEGACY-001", "partner_id": "shopify"}
    )
    db_session.execute(
        text("INSERT INTO legacy_claims (id, order_id, partner_id, claim_amount, claim_reason) VALUES (:id, :order_id, :partner_id, :amount, :reason)"),
        {"id": claim_uuid, "order_id": "ORD-LEGACY-001", "partner_id": "shopify", "amount": 1409.00, "reason": "unpaid_past_due"}
    )
    db_session.flush()

    # Apply migration 002 DDL & backfill operations
    db_session.execute(text("""
        ALTER TABLE legacy_order_recon ADD COLUMN external_order_id VARCHAR(128);
        UPDATE legacy_order_recon SET external_order_id = order_id;
        ALTER TABLE legacy_order_recon ALTER COLUMN external_order_id SET NOT NULL;
        ALTER TABLE legacy_order_recon ADD CONSTRAINT uq_legacy_recon_partner_ext UNIQUE (partner_id, external_order_id);

        ALTER TABLE legacy_claims ADD COLUMN external_order_id VARCHAR(128);
        UPDATE legacy_claims SET external_order_id = order_id;
        ALTER TABLE legacy_claims ALTER COLUMN external_order_id SET NOT NULL;

        ALTER TABLE legacy_claims ADD COLUMN order_recon_id UUID;
        UPDATE legacy_claims c 
        SET order_recon_id = r.id 
        FROM legacy_order_recon r 
        WHERE c.partner_id = r.partner_id AND (c.order_id = r.order_id OR c.external_order_id = r.external_order_id);

        ALTER TABLE legacy_claims ALTER COLUMN order_recon_id SET NOT NULL;
        ALTER TABLE legacy_claims ADD CONSTRAINT fk_legacy_claims_recon FOREIGN KEY (order_recon_id) REFERENCES legacy_order_recon(id) ON DELETE CASCADE;
        ALTER TABLE legacy_claims ADD CONSTRAINT uq_legacy_claim_recon_reason UNIQUE (order_recon_id, claim_reason);
    """))
    db_session.flush()

    # Query backfilled records
    res = db_session.execute(text("""
        SELECT c.id, c.order_recon_id, c.external_order_id, c.claim_amount, r.id, r.external_order_id
        FROM legacy_claims c
        JOIN legacy_order_recon r ON c.order_recon_id = r.id;
    """)).fetchone()

    assert res is not None
    assert res[0] == claim_uuid
    assert res[1] == recon_uuid
    assert res[2] == "ORD-LEGACY-001"
    assert res[3] == 1409.00
    assert res[4] == recon_uuid
    assert res[5] == "ORD-LEGACY-001"
