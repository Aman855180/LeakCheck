"""001_initial_foundation

Revision ID: 001_initial_foundation
Revises: 
Create Date: 2026-11-06 23:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_foundation"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Triggers and core tables are applied via db init and extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")


def downgrade() -> None:
    pass
