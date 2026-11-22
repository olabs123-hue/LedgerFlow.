"""Operator-only fictional credit grants and ledger reconciliation.

Never exposed as HTTP endpoints. Use only for trusted invitation-only demos.
"""
from __future__ import annotations

import argparse
import re
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.main import Account, Entry, FundingGrant, SessionLocal, Transfer, User

MAX_GRANT_CENTS = 100_000
REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{8,128}$")


def grant_fictional_credits(db: Session, email: str, amount_cents: int, reference: str) -> int:
    """Record a grant and update its recipient atomically; never handles real value."""
    if type(amount_cents) is not int or not 1 <= amount_cents <= MAX_GRANT_CENTS:
        raise ValueError("Fictional grant must be an integer between 1 and 100000 cents")
    if not REFERENCE_PATTERN.fullmatch(reference):
        raise ValueError("Grant reference must be 8-128 safe ASCII characters")
    try:
        with db.begin():
            account = db.scalar(
                select(Account).join(User).where(User.email == email.lower())
                .with_for_update()
            )
            if account is None:
                raise ValueError("Provision the invited demo account first")
            if db.scalar(select(FundingGrant.id).where(FundingGrant.reference == reference)):
                raise ValueError("Grant reference already used")
            db.add(FundingGrant(
                account_id=account.id,
                amount_cents=amount_cents,
                reference=reference,
            ))
            account.balance_cents += amount_cents
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Grant reference already used or invalid") from exc
    return amount_cents


def reconciliation_errors(db: Session) -> list[str]:
    """Return invariant failures without printing user emails, account IDs or tokens."""
    problems = []
    accounts = db.scalars(select(Account)).all()
    for account in accounts:
        grants = db.scalar(select(func.sum(FundingGrant.amount_cents)).where(
            FundingGrant.account_id == account.id
        )) or 0
        movements = db.scalar(select(func.sum(Entry.delta_cents)).where(
            Entry.account_id == account.id
        )) or 0
        if account.balance_cents != grants + movements:
            problems.append("Account balance disagrees with grants and journal")
    transfers = db.scalars(select(Transfer)).all()
    for transfer in transfers:
        entries = db.scalars(select(Entry).where(Entry.transfer_id == transfer.id)).all()
        if (len(entries) != 2
            or sum(entry.delta_cents for entry in entries) != 0
            or {(entry.account_id, entry.delta_cents) for entry in entries} != {
                (transfer.sender_id, -transfer.amount_cents),
                (transfer.recipient_id, transfer.amount_cents),
            }):
            problems.append("Transfer has an unbalanced or incomplete double-entry journal")
    return problems


def main():
    parser = argparse.ArgumentParser(description="LedgerFlow fictional demo operations")
    sub = parser.add_subparsers(dest="command", required=True)
    grant = sub.add_parser("grant", help="Create an auditable fictional credit grant")
    grant.add_argument("--email", required=True)
    grant.add_argument("--cents", type=int, required=True)
    grant.add_argument("--reference", required=True)
    sub.add_parser("reconcile", help="Verify demo balances and transfer journals")
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.command == "grant":
            try:
                grant_fictional_credits(db, args.email, args.cents, args.reference)
            except ValueError as exc:
                raise SystemExit(f"Grant refused: {exc}") from exc
            print("Fictional credit grant recorded; no real monetary value")
        else:
            problems = reconciliation_errors(db)
            if problems:
                raise SystemExit("Reconciliation FAILED: " + "; ".join(set(problems)))
            print("Reconciliation passed: balances match grants and balanced journals")


if __name__ == "__main__":
    main()
