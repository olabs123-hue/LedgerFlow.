"""Track fictional funding sources for reconciliation.

Revision ID: 0006_funding_grants
Revises: 0005_auth_peer_rate
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_funding_grants"
down_revision = "0005_auth_peer_rate"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "funding_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("reference", sa.String(length=128), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_cents > 0", name="ck_funding_grants_positive"),
    )

def downgrade():
    op.drop_table("funding_grants")
