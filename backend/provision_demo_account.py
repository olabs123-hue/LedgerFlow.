"""Trusted operator-only demo account provisioning. No public signup endpoint.

Run from a trusted shell with access to the chosen DATABASE_URL and JWT_SECRET.
The password is read interactively and NEVER accepted as a CLI argument.
Only fictional zero-balance accounts are created.
"""
from __future__ import annotations

import argparse
from getpass import getpass

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.main import Account, SessionLocal, User, password_hasher


def provision_demo_user(db: Session, email: str, password: str) -> str:
    normalized = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    if not (12 <= len(password) <= 256):
        raise ValueError("Demo password must be 12 to 256 characters.")
    if db.scalar(select(User.id).where(User.email == normalized)) is not None:
        raise ValueError("Account already exists.")
    try:
        user = User(email=normalized, password_hash=password_hasher.hash(password))
        db.add(user)
        db.flush()
        db.add(Account(user_id=user.id, balance_cents=0))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Account already exists or database constraint failed.") from exc
    except Exception:
        db.rollback()
        raise
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a zero-balance LedgerFlow fictional demo account")
    parser.add_argument("--email", required=True, help="Email address of invited test user")
    args = parser.parse_args()
    password = getpass("Set a strong demo-only password (not an existing password): ")
    confirmation = getpass("Confirm demo-only password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match; no account created.")
    with SessionLocal() as db:
        try:
            email = provision_demo_user(db, args.email, password)
        except ValueError as exc:
            raise SystemExit(f"Provisioning stopped: {exc}") from exc
    print(f"Created fictional zero-balance demo account for {email}.")
    print("No transfers or real funds were created. Send credentials through a secure channel.")


if __name__ == "__main__":
    main()
