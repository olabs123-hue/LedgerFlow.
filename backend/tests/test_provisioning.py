"""Operator account creation without a public registration endpoint."""
import os
import pytest
from sqlalchemy import func, select

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./ledgerflow_test.sqlite"
os.environ["JWT_SECRET"] = "integration-test-secret-string-32-bytes-minimum-only"
os.environ["DEMO_MODE"] = "true"

from app.main import Account, Base, SessionLocal, User, engine, password_hasher
from provision_demo_account import provision_demo_user


def test_provisioned_user_starts_with_zero_balance_and_hashed_password():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    password = "Demo-test-password-12345"
    with SessionLocal() as db:
        result = provision_demo_user(db, "Provisioned@Example.org", password)
        assert result == "provisioned@example.org"
        user = db.scalar(select(User).where(User.email == result))
        assert user is not None
        assert user.password_hash != password
        assert password_hasher.verify(user.password_hash, password)
        account = db.scalar(select(Account).where(Account.user_id == user.id))
        assert account is not None
        assert account.balance_cents == 0
        assert db.scalar(select(func.count()).select_from(Account)) == 1
    Base.metadata.drop_all(engine)


def test_operator_provisioning_refuses_duplicates_invalid_email_or_weak_password():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for email, password in [
            ("not-an-email", "Demo-test-password-12345"),
            ("alice@example.org", "weak"),
        ]:
            with pytest.raises(ValueError):
                provision_demo_user(db, email, password)
        provision_demo_user(db, "alice@example.org", "Demo-test-password-12345")
        with pytest.raises(ValueError, match="already exists"):
            provision_demo_user(db, "ALICE@example.org", "Demo-test-password-12345")
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(Account)) == 1
    Base.metadata.drop_all(engine)
