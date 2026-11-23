"""Add account-wide revocation counter.

Revision ID: 0007_session_version
Revises: 0006_funding_grants
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_session_version"
down_revision = "0006_funding_grants"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))

def downgrade():
    op.drop_column("users", "session_version")
