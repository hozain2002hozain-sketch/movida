"""add interview_action_at column

Revision ID: 5e8c9f4a1b2c
Revises: 48f1a7ac2f34
Create Date: 2026-06-30 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '5e8c9f4a1b2c'
down_revision = '48f1a7ac2f34'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS interview_action_at TIMESTAMP NULL")


def downgrade():
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS interview_action_at")
