"""LedgerFlow: simulation-only ledger service. Never process actual money."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated

from app.audit import emit_request_event

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, case, create_engine, delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://ledgerflow:ledgerflow@localhost:5433/ledgerflow")
# Render connectionString uses postgresql://; SQLAlchemy should select installed psycopg3.
if DB_URL.startswith("postgresql://"):
    DB_URL = "postgresql+psycopg://" + DB_URL[len("postgresql://"):]
SECRET = os.getenv("JWT_SECRET", "")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
APP_ENV = os.getenv("APP_ENV", "development").lower()
PUBLIC_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "false").lower() == "true"
PUBLIC_API_READONLY = os.getenv("PUBLIC_API_READONLY", "true" if APP_ENV == "production" else "false").lower() == "true"
AUTH_PEER_RATE_LIMIT = os.getenv("AUTH_PEER_RATE_LIMIT", "false").lower() == "true"
if not SECRET or SECRET == "REPLACE_WITH_A_LONG_RANDOM_SECRET_BEFORE_DEPLOYING" or len(SECRET) < 32:
    raise RuntimeError("Set JWT_SECRET to a secure random string (32+ characters)")
if APP_ENV not in {"development", "test", "production"}:
    raise RuntimeError("APP_ENV must be development, test, or production")
if APP_ENV == "production":
    if DEMO_MODE:
        raise RuntimeError("DEMO_MODE cannot be enabled in production")
    if ALLOW_REGISTRATION:
        raise RuntimeError("Public registration is not supported in production: use offline account provisioning")
    if not PUBLIC_API_READONLY and os.getenv("ALLOW_LIVE_API") != "I_UNDERSTAND_THE_RISK":
        raise RuntimeError("Public write API requires explicit ALLOW_LIVE_API acknowledgement")
    if not PUBLIC_API_READONLY and (
        not AUTH_PEER_RATE_LIMIT or os.getenv("EDGE_RATE_LIMIT_VERIFIED") != "true"
    ):
        raise RuntimeError("Public interactive API requires peer throttling and independently verified edge rate limits")
    if len(SECRET) < 48:
        raise RuntimeError("Production JWT_SECRET must have 48+ characters")
    if not DB_URL.startswith("postgresql"):
        raise RuntimeError("Production requires PostgreSQL")
    if not PUBLIC_ORIGIN.startswith("https://"):
        raise RuntimeError("Production FRONTEND_ORIGIN must use HTTPS")
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
    __table_args__ = (CheckConstraint("balance_cents >= 0", name="ck_accounts_nonnegative_balance"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    balance_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    user: Mapped[User] = relationship(back_populates="account")

class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        UniqueConstraint("sender_id", "idempotency_key"),
        CheckConstraint("amount_cents > 0", name="ck_transfers_positive_amount"),
        CheckConstraint("sender_id <> recipient_id", name="ck_transfers_distinct_accounts"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    recipient_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Entry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = (CheckConstraint("delta_cents <> 0", name="ck_journal_nonzero_entry"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey("transfers.id"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    delta_cents: Mapped[int] = mapped_column(BigInteger)

class RevokedToken(Base):
    """Server-side revocation of individual signed access tokens."""
    __tablename__ = "revoked_tokens"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)

class AuthPeerBucket(Base):
    """Shared coarse-grained auth request limiter by verified socket peer.

    Does not use untrusted Forwarded/X-Forwarded-For request headers. Behind a
    reverse proxy the socket peer may be shared; confirm proxy topology first.
    """
    __tablename__ = "auth_peer_buckets"
    bucket_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(default=0)
    window_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)

class LoginAttempt(Base):
    """Database-backed failed-password counter, keyed by email digest."""
    __tablename__ = "login_attempts"
    email_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    failures: Mapped[int] = mapped_column(default=0)
    last_failure_epoch: Mapped[int] = mapped_column(BigInteger, default=0)

LOGIN_LIMIT = 5
LOGIN_WINDOW_SECONDS = 15 * 60

def _login_key(email: str) -> str:
    return hashlib.sha256(email.encode("utf-8")).hexdigest()

def _record_failed_login(db: Session, email_hash: str, now: int):
    """Atomic upsert works across multiple API processes sharing the same database."""
    insert_fn = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    statement = insert_fn(LoginAttempt).values(
        email_hash=email_hash, failures=1, last_failure_epoch=now
    )
    statement = statement.on_conflict_do_update(
        index_elements=["email_hash"],
        set_={
            "failures": case(
                (LoginAttempt.last_failure_epoch <= now - LOGIN_WINDOW_SECONDS, 1),
                else_=LoginAttempt.failures + 1,
            ),
            "last_failure_epoch": now,
        },
    )
    db.execute(statement)
    db.commit()

AUTH_PEER_LIMIT = 60
AUTH_PEER_WINDOW = 60
AUTH_PEER_PATHS = {
    "/auth/login", "/browser/session", "/auth/register",
}

def _limit_auth_peer(db: Session, peer: str, now: int):
    # Never trust client-supplied forwarding headers for a rate limit.
    key = hashlib.sha256(peer.encode("utf-8")).hexdigest()
    statement = (pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert)(
        AuthPeerBucket
    ).values(bucket_key=key, count=1, window_epoch=now)
    statement = statement.on_conflict_do_update(
        index_elements=["bucket_key"],
        set_={
            "count": case(
                (AuthPeerBucket.window_epoch <= now - AUTH_PEER_WINDOW, 1),
                else_=AuthPeerBucket.count + 1,
            ),
            "window_epoch": case(
                (AuthPeerBucket.window_epoch <= now - AUTH_PEER_WINDOW, now),
                else_=AuthPeerBucket.window_epoch,
            ),
        },
    )
    db.execute(statement)
    db.commit()
    bucket = db.get(AuthPeerBucket, key)
    if bucket.count > AUTH_PEER_LIMIT:
        seconds = max(1, AUTH_PEER_WINDOW - (now - bucket.window_epoch))
        raise HTTPException(429, "Too many authentication requests", headers={"Retry-After": str(seconds)})

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

app = FastAPI(title="LedgerFlow API", version="0.1.0", description="Simulation only — not a payment processor", docs_url=None if APP_ENV == "production" else "/docs", redoc_url=None if APP_ENV == "production" else "/redoc", openapi_url=None if APP_ENV == "production" else "/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=[PUBLIC_ORIGIN], allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-CSRF-Token"])

@app.middleware("http")
async def security_headers(request: Request, call_next):
    # Always generate the correlation ID ourselves; ignore untrusted input headers.
    request_id = secrets.token_hex(12)
    started = time.monotonic()
    status = 500
    try:
        # Public release first exposes ONLY liveness/readiness, not user or ledger APIs.
        if APP_ENV == "production" and PUBLIC_API_READONLY and (
            request.method != "GET" or request.url.path not in ("/health", "/ready")
        ):
            response = JSONResponse({"detail": "Not found"}, status_code=404)
        elif APP_ENV == "production" and not PUBLIC_API_READONLY and not (
            request.url.path in ("/health", "/ready") or
            request.url.path.startswith("/browser/")
        ):
            # Public interactive demo must use HttpOnly browser sessions only:
            # legacy bearer-token routes and demo funding remain inaccessible.
            response = JSONResponse({"detail": "Not found"}, status_code=404)
        elif AUTH_PEER_RATE_LIMIT and request.method == "POST" and request.url.path in AUTH_PEER_PATHS:
            # Always use ASGI socket peer, never spoofable X-Forwarded-For.
            # Render's proxy may present a shared address: deliberately opt-in.
            try:
                with SessionLocal() as db:
                    _limit_auth_peer(db, request.client.host if request.client else "unknown", int(time.time()))
            except HTTPException as exc:
                response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
        status = response.status_code
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Request-ID"] = request_id
        if APP_ENV == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
    finally:
        emit_request_event(
            request_id=request_id, method=request.method, path=request.url.path,
            status=status, elapsed_ms=round((time.monotonic() - started) * 1000),
        )

@app.on_event("startup")
def startup():
    if APP_ENV != "production":
        Base.metadata.create_all(engine)  # Development only; production requires migrations.

def get_db():
    with SessionLocal() as db:
        yield db

def get_user(token: Annotated[HTTPAuthorizationCredentials, Depends(auth_scheme)], db: Annotated[Session, Depends(get_db)]) -> User:
    try:
        payload = jwt.decode(
            token.credentials, SECRET, algorithms=["HS256"],
            options={"require": ["sub", "exp", "jti"]},
        )
        jti = str(payload["jti"])
        if not jti or db.get(RevokedToken, jti) is not None:
            raise HTTPException(401, "Invalid or revoked token")
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        user = None
    if user is None:
        raise HTTPException(401, "Invalid or expired token")
    return user

@app.get("/health")
def health():
    return {"status": "ok", "simulation": True}

@app.get("/ready")
def ready(db: Annotated[Session, Depends(get_db)]):
    """Database connectivity only. No user records or connection details returned."""
    try:
        db.execute(text("SELECT 1")).scalar_one()
    except Exception:
        raise HTTPException(503, "Database unavailable")
    return {"status": "ready", "simulation": True}

@app.post("/auth/register", status_code=201)
def register(body: Credentials, db: Annotated[Session, Depends(get_db)]):
    if APP_ENV == "production" and not ALLOW_REGISTRATION:
        raise HTTPException(403, "Public registration is disabled")
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
    email = str(body.email).lower()
    now = int(time.time())
    key = _login_key(email)
    attempts = db.get(LoginAttempt, key)
    if attempts and attempts.failures >= LOGIN_LIMIT and now - attempts.last_failure_epoch < LOGIN_WINDOW_SECONDS:
        retry = max(1, LOGIN_WINDOW_SECONDS - (now - attempts.last_failure_epoch))
        raise HTTPException(429, "Too many unsuccessful login attempts", headers={"Retry-After": str(retry)})
    user = db.scalar(select(User).where(User.email == email))
    valid = False
    if user is not None:
        try:
            valid = password_hasher.verify(user.password_hash, body.password)
        except (VerifyMismatchError, VerificationError):
            pass
    if not valid:
        _record_failed_login(db, key, now)
        raise HTTPException(401, "Invalid credentials")
    db.execute(delete(LoginAttempt).where(LoginAttempt.email_hash == key))
    db.commit()
    token = jwt.encode({
        "sub": str(user.id),
        "jti": secrets.token_urlsafe(24),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1 if APP_ENV == "production" else 8),
    }, SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}

@app.post("/auth/logout")
def logout(
    user: Annotated[User, Depends(get_user)],
    token: Annotated[HTTPAuthorizationCredentials, Depends(auth_scheme)],
    db: Annotated[Session, Depends(get_db)],
):
    """Revoke only this access token. Other devices can remain signed in."""
    payload = jwt.decode(token.credentials, SECRET, algorithms=["HS256"])
    db.add(RevokedToken(jti=str(payload["jti"]), expires_at_epoch=int(payload["exp"])))
    db.commit()
    return {"message": "Signed out"}

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
    # Cache scalar identifiers before rollback: ORM instances expire after rollback.
    sender_user_id = user.id
    recipient_id = db.scalar(
        select(Account.id).join(User).where(User.email == recipient_email)
    )
    if recipient_id is None:
        raise HTTPException(404, "Recipient not found")
    sender_id = db.scalar(select(Account.id).where(Account.user_id == sender_user_id))
    db.rollback()
    # Acquire locks in the same order for every transfer, preventing AB/BA deadlocks.
    with db.begin():
        locked = db.scalars(
            select(Account)
            .where(Account.id.in_([sender_id, recipient_id]))
            .order_by(Account.id)
            .with_for_update()
        ).all()
        accounts = {account.id: account for account in locked}
        sender = accounts[sender_id]
        recipient = accounts[recipient_id]
        previous = db.scalar(select(Transfer).where(
            Transfer.sender_id == sender.id,
            Transfer.idempotency_key == idempotency_key,
        ))
        if previous:
            if previous.request_hash != request_hash:
                raise HTTPException(409, "Idempotency key already used with different request")
            return TransferResult(
                transfer_id=previous.id,
                amount_cents=previous.amount_cents,
                recipient_email=recipient_email,
                replayed=True,
            )
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
    user_id = user.id
    db.rollback()
    with db.begin():
        account = db.scalar(select(Account).where(Account.user_id == user_id).with_for_update())
        account.balance_cents += 100_000
    return {"credited_cents": 100_000, "warning": "Simulation credits have no monetary value"}


# Opt-in browser session endpoints for the eventual same-origin interactive demo.
# The production public-readonly middleware still hides all these paths.
COOKIE_NAME = "__Host-lf_session" if APP_ENV == "production" else "lf_session"
SESSION_SECONDS = 3600 if APP_ENV == "production" else 8 * 3600


def _verify_browser_origin(request: Request):
    # Missing Origin is rejected for all browser state changes, not just mismatches.
    if request.headers.get("origin") != PUBLIC_ORIGIN:
        raise HTTPException(403, "Untrusted request origin")


def _browser_claims(request: Request) -> dict:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(401, "No browser session")
    try:
        return jwt.decode(raw, SECRET, algorithms=["HS256"], options={"require": ["sub", "exp", "jti"]})
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired browser session")


def _browser_csrf(jti: str) -> str:
    return hmac.new(SECRET.encode(), ("ledgerflow-csrf:" + jti).encode(), hashlib.sha256).hexdigest()


def _verify_browser_csrf(request: Request, claims: dict):
    _verify_browser_origin(request)
    supplied = request.headers.get("x-csrf-token", "")
    expected = _browser_csrf(str(claims["jti"]))
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(403, "Invalid CSRF token")


def get_browser_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    claims = _browser_claims(request)
    if db.get(RevokedToken, str(claims["jti"])) is not None:
        raise HTTPException(401, "Revoked browser session")
    try:
        user = db.get(User, int(claims["sub"]))
    except (ValueError, TypeError):
        user = None
    if user is None:
        raise HTTPException(401, "Invalid browser session")
    return user


@app.post("/browser/session")
def create_browser_session(
    body: Credentials, request: Request, response: Response,
    db: Annotated[Session, Depends(get_db)],
):
    _verify_browser_origin(request)
    # Reuse the existing credential verification and DB-backed failed-login counters.
    token = login(body, db)["access_token"]
    claims = jwt.decode(token, SECRET, algorithms=["HS256"])
    response.set_cookie(
        COOKIE_NAME, token,
        max_age=SESSION_SECONDS, httponly=True, secure=APP_ENV == "production",
        samesite="strict", path="/",
    )
    # Give JavaScript the CSRF proof only, never the bearer token.
    return {"authenticated": True, "csrf_token": _browser_csrf(str(claims["jti"]))}


@app.get("/browser/session")
def read_browser_session(
    request: Request, user: Annotated[User, Depends(get_browser_user)],
):
    # A CSRF proof must only be exposed to the configured frontend origin.
    origin = request.headers.get("origin")
    if origin is not None and origin != PUBLIC_ORIGIN:
        raise HTTPException(403, "Untrusted request origin")
    claims = _browser_claims(request)
    return {"authenticated": True, "csrf_token": _browser_csrf(str(claims["jti"]))}


@app.get("/browser/me")
def browser_me(
    user: Annotated[User, Depends(get_browser_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return me(user, db)


@app.get("/browser/transfers")
def browser_history(
    user: Annotated[User, Depends(get_browser_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return history(user, db)


@app.post("/browser/transfers", response_model=TransferResult)
def browser_transfer(
    body: TransferRequest, request: Request,
    user: Annotated[User, Depends(get_browser_user)],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Header(min_length=8, max_length=128)],
):
    _verify_browser_csrf(request, _browser_claims(request))
    return transfer(body, user, db, idempotency_key)


@app.post("/browser/logout")
def browser_logout(
    request: Request, response: Response,
    user: Annotated[User, Depends(get_browser_user)],
    db: Annotated[Session, Depends(get_db)],
):
    claims = _browser_claims(request)
    _verify_browser_csrf(request, claims)
    db.add(RevokedToken(jti=str(claims["jti"]), expires_at_epoch=int(claims["exp"])))
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/", samesite="strict", secure=APP_ENV == "production", httponly=True)
    return {"message": "Signed out"}
