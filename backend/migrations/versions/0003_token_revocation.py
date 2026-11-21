"""Store revoked access-token identifiers.

Revision ID: 0003_token_revocation
Revises: 0002_login_throttle
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_token_revocation"
down_revision = "0002_login_throttle"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(length=64), primary_key=True),
        sa.Column("expires_at_epoch", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_revoked_tokens_expiry", "revoked_tokens", ["expires_at_epoch"])

def downgrade():
    op.drop_index("ix_revoked_tokens_expiry", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
