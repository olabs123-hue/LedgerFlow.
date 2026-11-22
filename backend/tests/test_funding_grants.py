"""Offline fictional grants must reconcile with double-entry journals."""
import os
import pytest
from sqlalchemy import func, select

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./ledgerflow_test.sqlite"
os.environ["JWT_SECRET"] = "integration-test-secret-string-32-bytes-minimum-only"
os.environ["DEMO_MODE"] = "true"

from app.main import Account, Base, FundingGrant, SessionLocal, User, engine
from demo_operations import grant_fictional_credits, reconciliation_errors
from provision_demo_account import provision_demo_user


def test_fictional_grant_is_atomic_idempotent_and_reconcilable():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        provision_demo_user(db, "funded@example.org", "separate-test-password-only-123")
    with SessionLocal() as db:
        assert grant_fictional_credits(
            db, "funded@example.org", 50_000, "unit-test-funding-0001"
        ) == 50_000
    with SessionLocal() as db:
        assert reconciliation_errors(db) == []
        account = db.scalar(select(Account).join(User).where(User.email == "funded@example.org"))
        assert account.balance_cents == 50_000
        assert db.scalar(select(func.count()).select_from(FundingGrant)) == 1

    with SessionLocal() as db:
        with pytest.raises(ValueError, match="reference"):
            grant_fictional_credits(db, "funded@example.org", 50_000, "unit-test-funding-0001")
    with SessionLocal() as db:
        for value in (0, -1, 100_001, 1.5):
            with pytest.raises(ValueError, match="Fictional grant"):
                grant_fictional_credits(db, "funded@example.org", value, "unit-test-funding-0002")
        assert reconciliation_errors(db) == []
        account = db.scalar(select(Account).join(User).where(User.email == "funded@example.org"))
        account.balance_cents += 1  # deliberate corruption to prove reconciliation detection
        db.commit()
    with SessionLocal() as db:
        errors = reconciliation_errors(db)
        assert any("balance disagrees" in message for message in errors)
    Base.metadata.drop_all(engine)
