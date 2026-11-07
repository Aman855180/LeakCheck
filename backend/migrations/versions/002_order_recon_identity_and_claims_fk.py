"""002_order_recon_identity_and_claims_fk

Revision ID: 002_recon_identity
Revises: 001_initial_foundation
Create Date: 2026-11-07 14:18:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002_recon_identity"
down_revision: Union[str, None] = "001_initial_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update order_recon table
    # Add external_order_id if missing
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'order_recon' AND column_name = 'external_order_id'
            ) THEN
                ALTER TABLE order_recon ADD COLUMN external_order_id VARCHAR(128);
                UPDATE order_recon SET external_order_id = order_id WHERE external_order_id IS NULL;
                ALTER TABLE order_recon ALTER COLUMN external_order_id SET NOT NULL;
            END IF;
        END $$;
    """)

    # Drop old global unique constraint on order_id if present
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'order_recon_order_id_key'
            ) THEN
                ALTER TABLE order_recon DROP CONSTRAINT order_recon_order_id_key;
            END IF;
            IF EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'ix_order_recon_order_id'
            ) THEN
                DROP INDEX IF EXISTS ix_order_recon_order_id;
                CREATE INDEX ix_order_recon_order_id ON order_recon (order_id);
            END IF;
        END $$;
    """)

    # Add composite unique constraint on (partner_id, external_order_id)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_order_recon_partner_external'
            ) THEN
                ALTER TABLE order_recon ADD CONSTRAINT uq_order_recon_partner_external UNIQUE (partner_id, external_order_id);
            END IF;
        END $$;
    """)

    # 2. Update claims table
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'claims' AND column_name = 'external_order_id'
            ) THEN
                ALTER TABLE claims ADD COLUMN external_order_id VARCHAR(128);
                UPDATE claims SET external_order_id = order_id WHERE external_order_id IS NULL;
                ALTER TABLE claims ALTER COLUMN external_order_id SET NOT NULL;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'claims' AND column_name = 'order_recon_id'
            ) THEN
                ALTER TABLE claims ADD COLUMN order_recon_id UUID;
                -- Safely link existing claims to order_recon records if any exist
                UPDATE claims c 
                SET order_recon_id = r.id 
                FROM order_recon r 
                WHERE c.partner_id = r.partner_id AND (c.order_id = r.order_id OR c.external_order_id = r.external_order_id)
                  AND c.order_recon_id IS NULL;
                
                -- Delete any orphaned test claims without matching order_recon
                DELETE FROM claims WHERE order_recon_id IS NULL;
                
                ALTER TABLE claims ALTER COLUMN order_recon_id SET NOT NULL;
                ALTER TABLE claims ADD CONSTRAINT fk_claims_order_recon FOREIGN KEY (order_recon_id) REFERENCES order_recon(id) ON DELETE CASCADE;
            END IF;

            -- Drop old uq_order_claim_reason constraint
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_order_claim_reason'
            ) THEN
                ALTER TABLE claims DROP CONSTRAINT uq_order_claim_reason;
            END IF;

            -- Add new uq_claim_recon_reason constraint
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_claim_recon_reason'
            ) THEN
                ALTER TABLE claims ADD CONSTRAINT uq_claim_recon_reason UNIQUE (order_recon_id, claim_reason);
            END IF;
        END $$;
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_claims_order_recon_id ON claims(order_recon_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_claims_partner_external ON claims(partner_id, external_order_id);")


def downgrade() -> None:
    pass
