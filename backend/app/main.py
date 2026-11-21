"""LedgerFlow: simulation-only ledger service. Never process actual money."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://ledgerflow:ledgerflow@localhost:5433/ledgerflow")
SECRET = os.getenv("JWT_SECRET", "")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
if not SECRET or SECRET == "REPLACE_WITH_A_LONG_RANDOM_SECRET_BEFORE_DEPLOYING" or len(SECRET) < 32:
    raise RuntimeError("Set JWT_SECRET to a secure random string (32+ characters)")
engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
password_hasher = PasswordHasher()
auth_scheme = HTTPBearer()

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    account: Mapped["Account"] = relationship(back_populates="user", uselist=False)

class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    balance_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    user: Mapped[User] = relationship(back_populates="account")

class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (UniqueConstraint("sender_id", "idempotency_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    recipient_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Entry(Base):
    __tablename__ = "journal_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey("transfers.id"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    delta_cents: Mapped[int] = mapped_column(BigInteger)

class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)

class TransferRequest(BaseModel):
    recipient_email: EmailStr
    amount_cents: int = Field(gt=0, le=10_000_000)

class TransferResult(BaseModel):
    transfer_id: int
    amount_cents: int
    recipient_email: str
    replayed: bool

app = FastAPI(title="LedgerFlow API", version="0.1.0", description="Simulation only — not a payment processor")
app.add_middleware(CORSMiddleware, allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key"])

@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)  # Development only. Production should use migrations.

def get_db():
    with SessionLocal() as db:
        yield db

def get_user(token: Annotated[HTTPAuthorizationCredentials, Depends(auth_scheme)], db: Annotated[Session, Depends(get_db)]) -> User:
    try:
        payload = jwt.decode(token.credentials, SECRET, algorithms=["HS256"], options={"require": ["sub", "exp"]})
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, ValueError, TypeError):
        user = None
    if user is None:
        raise HTTPException(401, "Invalid or expired token")
    return user

@app.get("/health")
def health():
    return {"status": "ok", "simulation": True}

@app.post("/auth/register", status_code=201)
def register(body: Credentials, db: Annotated[Session, Depends(get_db)]):
    email = str(body.email).lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(409, "Email already registered")
    try:
        user = User(email=email, password_hash=password_hasher.hash(body.password))
        db.add(user)
        db.flush()
        db.add(Account(user_id=user.id, balance_cents=0))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"message": "Account created", "email": email}

@app.post("/auth/login")
def login(body: Credentials, db: Annotated[Session, Depends(get_db)]):
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    if user is None:
        raise HTTPException(401, "Invalid credentials")
    try:
        password_hasher.verify(user.password_hash, body.password)
    except (VerifyMismatchError, VerificationError):
        raise HTTPException(401, "Invalid credentials")
    token = jwt.encode({"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(hours=8)}, SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me")
def me(user: Annotated[User, Depends(get_user)], db: Annotated[Session, Depends(get_db)]):
    account = db.scalar(select(Account).where(Account.user_id == user.id))
    return {"email": user.email, "balance_cents": account.balance_cents, "account_id": account.id, "simulation": True}

@app.get("/transfers")
def history(user: Annotated[User, Depends(get_user)], db: Annotated[Session, Depends(get_db)]):
    account = db.scalar(select(Account).where(Account.user_id == user.id))
    transfers = db.scalars(select(Transfer).where((Transfer.sender_id == account.id) | (Transfer.recipient_id == account.id)).order_by(Transfer.id.desc()).limit(50)).all()
    return [{"id": t.id, "direction": "sent" if t.sender_id == account.id else "received", "amount_cents": t.amount_cents, "created_at": t.created_at.isoformat()} for t in transfers]

@app.post("/transfers", response_model=TransferResult)
def transfer(body: TransferRequest, user: Annotated[User, Depends(get_user)], db: Annotated[Session, Depends(get_db)], idempotency_key: Annotated[str, Header(min_length=8, max_length=128)]):
    recipient_email = str(body.recipient_email).lower()
    if recipient_email == user.email:
        raise HTTPException(400, "Cannot transfer to yourself")
    request_hash = hashlib.sha256(json.dumps({"email": recipient_email, "amount": body.amount_cents}, sort_keys=True).encode()).hexdigest()
    # End the read transaction opened by authentication before acquiring write locks.
    db.rollback()
    # Lock the sender's account first: concurrent requests from the same sender serialize,
    # ensuring that a retry cannot race ahead of its original request.
    with db.begin():
        sender = db.scalar(select(Account).where(Account.user_id == user.id).with_for_update())
        previous = db.scalar(select(Transfer).where(Transfer.sender_id == sender.id, Transfer.idempotency_key == idempotency_key))
        if previous:
            if previous.request_hash != request_hash:
                raise HTTPException(409, "Idempotency key already used with different request")
            return TransferResult(transfer_id=previous.id, amount_cents=previous.amount_cents, recipient_email=recipient_email, replayed=True)
        recipient = db.scalar(select(Account).join(User).where(User.email == recipient_email).with_for_update(of=Account))
        if not recipient:
            raise HTTPException(404, "Recipient not found")
        if sender.balance_cents < body.amount_cents:
            raise HTTPException(400, "Insufficient demo funds")
        sender.balance_cents -= body.amount_cents
        recipient.balance_cents += body.amount_cents
        new_transfer = Transfer(sender_id=sender.id, recipient_id=recipient.id, amount_cents=body.amount_cents, idempotency_key=idempotency_key, request_hash=request_hash)
        db.add(new_transfer)
        db.flush()
        db.add_all([Entry(transfer_id=new_transfer.id, account_id=sender.id, delta_cents=-body.amount_cents), Entry(transfer_id=new_transfer.id, account_id=recipient.id, delta_cents=body.amount_cents)])
        return TransferResult(transfer_id=new_transfer.id, amount_cents=body.amount_cents, recipient_email=recipient_email, replayed=False)

@app.post("/demo/credit")
def demo_credit(user: Annotated[User, Depends(get_user)], db: Annotated[Session, Depends(get_db)]):
    # Local development feature: disabled by default. Do not enable in public deployment.
    if not DEMO_MODE:
        raise HTTPException(404, "Not found")
    db.rollback()
    with db.begin():
        account = db.scalar(select(Account).where(Account.user_id == user.id).with_for_update())
        account.balance_cents += 100_000
    return {"credited_cents": 100_000, "warning": "Simulation credits have no monetary value"}
