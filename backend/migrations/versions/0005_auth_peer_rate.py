"""Shared authentication request limiter.

Revision ID: 0005_auth_peer_rate
Revises: 0004_ledger_checks
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_auth_peer_rate"
down_revision = "0004_ledger_checks"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "auth_peer_buckets",
        sa.Column("bucket_key", sa.String(length=64), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("window_epoch", sa.BigInteger(), nullable=False),
    )

def downgrade():
    op.drop_table("auth_peer_buckets")
