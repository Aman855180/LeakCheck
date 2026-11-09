"""005_upload_mapping_suggestions

Revision ID: 005_upload_mapping_suggestions
Revises: 004_failed_upload_retry
Create Date: 2026-11-09 21:28:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005_upload_mapping_suggestions"
down_revision: Union[str, None] = "004_failed_upload_retry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS upload_mapping_suggestions (
            id UUID PRIMARY KEY,
            upload_id UUID NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
            source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            file_name VARCHAR(255) NOT NULL,
            source_type VARCHAR(32) NOT NULL,
            total_rows INTEGER NOT NULL DEFAULT 0,
            detected_columns JSONB NOT NULL,
            dropped_pii_columns JSONB NOT NULL DEFAULT '[]'::jsonb,
            preview_rows JSONB NOT NULL DEFAULT '[]'::jsonb,
            suggested_mapping JSONB NOT NULL,
            missing_required JSONB NOT NULL DEFAULT '[]'::jsonb,
            canonical_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
            is_mapping_compatible BOOLEAN NOT NULL DEFAULT FALSE,
            incompatibility_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
            active_mapping_version INTEGER NULL,
            generation_status VARCHAR(32) NOT NULL DEFAULT 'completed',
            generation_error VARCHAR(1000) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_upload_mapping_suggestions_upload_id UNIQUE (upload_id)
        );

        CREATE INDEX IF NOT EXISTS ix_upload_mapping_suggestions_upload_id ON upload_mapping_suggestions (upload_id);
        CREATE INDEX IF NOT EXISTS ix_upload_mapping_suggestions_source_id ON upload_mapping_suggestions (source_id);
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE IF EXISTS upload_mapping_suggestions;
    """)
