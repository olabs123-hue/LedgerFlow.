"""Verify ledger CHECK constraints on the migrated PostgreSQL schema itself.

Runs BEFORE the concurrency fixture suite, which reconstructs disposable tables.
"""
import os
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

if not os.environ.get("DATABASE_URL", "").startswith("postgresql"):
    pytest.skip("PostgreSQL database required", allow_module_level=True)

engine = create_engine(os.environ["DATABASE_URL"])


def test_migrated_constraints_reject_invalid_ledger_rows():
    expected = {
        "accounts": "ck_accounts_nonnegative_balance",
        "transfers": "ck_transfers_positive_amount",
        "transfers_2": "ck_transfers_distinct_accounts",
        "journal_entries": "ck_journal_nonzero_entry",
    }
    inspector = inspect(engine)
    for table, constraint in expected.items():
        table = table.removesuffix("_2")
        checks = {row["name"] for row in inspector.get_check_constraints(table)}
        assert constraint in checks, (table, constraint, checks)

    with engine.connect() as conn:
        with conn.begin():
            # Savepoint failures do not abort the surrounding PostgreSQL transaction.
            def expect_rejected(sql, values):
                nested = conn.begin_nested()
                try:
                    with pytest.raises(IntegrityError):
                        conn.execute(text(sql), values)
                finally:
                    nested.rollback()

            a = conn.execute(text(
                "INSERT INTO users (email,password_hash) VALUES (:email,'TEST_ONLY') RETURNING id"
            ), {"email": "schema-a@example.invalid"}).scalar_one()
            b = conn.execute(text(
                "INSERT INTO users (email,password_hash) VALUES (:email,'TEST_ONLY') RETURNING id"
            ), {"email": "schema-b@example.invalid"}).scalar_one()

            expect_rejected(
                "INSERT INTO accounts (user_id,balance_cents) VALUES (:uid,-1)",
                {"uid": a},
            )
            aid = conn.execute(text(
                "INSERT INTO accounts (user_id,balance_cents) VALUES (:uid,1000) RETURNING id"
            ), {"uid": a}).scalar_one()
            bid = conn.execute(text(
                "INSERT INTO accounts (user_id,balance_cents) VALUES (:uid,0) RETURNING id"
            ), {"uid": b}).scalar_one()

            template = """INSERT INTO transfers
            (sender_id,recipient_id,amount_cents,idempotency_key,request_hash,created_at)
            VALUES (:sender,:recipient,:amount,:key,'abc',CURRENT_TIMESTAMP)
            RETURNING id"""
            expect_rejected(template, {"sender": aid, "recipient": bid, "amount": -50, "key": "badnegative"})
            expect_rejected(template, {"sender": aid, "recipient": aid, "amount": 50, "key": "badself"})
            transfer_id = conn.execute(text(template), {
                "sender": aid, "recipient": bid, "amount": 50, "key": "valid-transfer"
            }).scalar_one()
            expect_rejected(
                "INSERT INTO journal_entries (transfer_id,account_id,delta_cents) VALUES (:tid,:aid,0)",
                {"tid": transfer_id, "aid": aid},
            )
            # Roll back this entire setup; the test database remains empty.
            conn.rollback()
