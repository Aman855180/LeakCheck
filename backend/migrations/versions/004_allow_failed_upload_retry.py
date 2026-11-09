"""004_allow_failed_upload_retry

Revision ID: 004_failed_upload_retry
Revises: 003_claim_recovered_at
Create Date: 2026-11-08 18:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004_failed_upload_retry"
down_revision: Union[str, None] = "003_claim_recovered_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add retry_of_upload_id column if not exists
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'uploads' AND column_name = 'retry_of_upload_id'
            ) THEN
                ALTER TABLE uploads ADD COLUMN retry_of_upload_id UUID REFERENCES uploads(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)

    # 2. Drop table-wide unique constraint/index on file_hash and replace with partial unique index
    op.execute("""
        DROP INDEX IF EXISTS ix_uploads_file_hash;
        
        -- Non-unique index for fast lookups by file_hash
        CREATE INDEX IF NOT EXISTS ix_uploads_file_hash ON uploads (file_hash);
        
        -- Partial unique index: only prevents duplicates for completed or in-flight processing uploads
        CREATE UNIQUE INDEX IF NOT EXISTS uq_uploads_active_completed_hash 
        ON uploads (file_hash) 
        WHERE processing_status IN ('completed', 'processing');
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS uq_uploads_active_completed_hash;
        DROP INDEX IF EXISTS ix_uploads_file_hash;
        CREATE UNIQUE INDEX ix_uploads_file_hash ON uploads (file_hash);
        ALTER TABLE uploads DROP COLUMN IF EXISTS retry_of_upload_id;
    """)
