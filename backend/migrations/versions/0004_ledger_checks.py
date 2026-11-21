"""Database-level ledger integrity constraints.

Revision ID: 0004_ledger_checks
Revises: 0003_token_revocation
"""
from alembic import op

revision = "0004_ledger_checks"
down_revision = "0003_token_revocation"
branch_labels = None
depends_on = None

def upgrade():
    op.create_check_constraint("ck_accounts_nonnegative_balance", "accounts", "balance_cents >= 0")
    op.create_check_constraint("ck_transfers_positive_amount", "transfers", "amount_cents > 0")
    op.create_check_constraint("ck_transfers_distinct_accounts", "transfers", "sender_id <> recipient_id")
    op.create_check_constraint("ck_journal_nonzero_entry", "journal_entries", "delta_cents <> 0")

def downgrade():
    op.drop_constraint("ck_journal_nonzero_entry", "journal_entries", type_="check")
    op.drop_constraint("ck_transfers_distinct_accounts", "transfers", type_="check")
    op.drop_constraint("ck_transfers_positive_amount", "transfers", type_="check")
    op.drop_constraint("ck_accounts_nonnegative_balance", "accounts", type_="check")
