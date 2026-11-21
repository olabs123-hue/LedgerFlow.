"""Persist failed-login counters to share throttling across API replicas.

Revision ID: 0002_login_throttle
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_login_throttle"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "login_attempts",
        sa.Column("email_hash", sa.String(length=64), primary_key=True),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("last_failure_epoch", sa.BigInteger(), nullable=False),
    )

def downgrade():
    op.drop_table("login_attempts")
