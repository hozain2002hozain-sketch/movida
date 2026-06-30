"""add customer interview columns

Revision ID: 48f1a7ac2f34
Revises: 39fb02d8ecaa
Create Date: 2026-06-30 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '48f1a7ac2f34'
down_revision = '39fb02d8ecaa'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS interview_status VARCHAR(20)")
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS interview_result VARCHAR(20)")


def downgrade():
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS interview_result")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS interview_status")
