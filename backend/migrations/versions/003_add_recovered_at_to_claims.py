"""003_add_recovered_at_to_claims

Revision ID: 003_claim_recovered_at
Revises: 002_recon_identity
Create Date: 2026-11-07 23:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_claim_recovered_at"
down_revision: Union[str, None] = "002_recon_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'claims' AND column_name = 'recovered_at'
            ) THEN
                ALTER TABLE claims ADD COLUMN recovered_at TIMESTAMP WITH TIME ZONE;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE claims DROP COLUMN IF EXISTS recovered_at;
    """)
