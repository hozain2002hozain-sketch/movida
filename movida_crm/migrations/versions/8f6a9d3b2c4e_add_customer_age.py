"""add customer age

Revision ID: 8f6a9d3b2c4e
Revises: 5e8c9f4a1b2c
Create Date: 2026-07-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8f6a9d3b2c4e'
down_revision = '5e8c9f4a1b2c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('age', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.drop_column('age')
