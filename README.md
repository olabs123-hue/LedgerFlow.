# LedgerFlow — Full-Stack Financial Operations (Portfolio Prototype)

**Simulation only.** LedgerFlow is a developer portfolio project, not a bank, payment processor, or regulated money service. All balances are fictional.

## Stack
React 18, TypeScript, Vite; FastAPI, SQLAlchemy, PostgreSQL; Docker Compose; JWT and Argon2.

## Local setup
1. Copy `.env.example` to `.env` and replace `JWT_SECRET` with a secure random secret of at least 32 characters.
2. Run `docker compose up --build`.
3. Open `http://localhost:5173` for the web interface and `http://localhost:8000/docs` for API documentation.
4. Register two demo accounts, add simulated credit to one account, and transfer fictional funds.

## Features
- Registration and login
- Transfer journal (debit and credit entries)
- Integer-cent balances and simulated transfers
- Sender locking and request idempotency
- Transaction history and demo funding
- Responsive React/TypeScript interface

## API
- POST /auth/register
- POST /auth/login
- GET /me
- GET /transfers
- POST /transfers (requires Idempotency-Key)
- POST /demo/credit (DEMO_MODE only)

## Testing
Run `cd backend && pip install -r requirements.txt && PYTHONPATH=. pytest -q`. Frontend build command: `cd frontend && npm install && npm run build`.

## Limitations and verification
This is a learning prototype and should not be deployed publicly as-is. DEMO_MODE provides unrestricted fictional credits and must remain off in public environments. Missing production controls include email verification, rate limiting, migrations, MFA, session revocation, and audit/security hardening. Account rows are now acquired in canonical ID order to mitigate opposing-transfer deadlocks; concurrency behavior must still be validated through PostgreSQL CI.

On 2026-11-21 Python compilation, two SQLite API smoke tests and the frontend production build passed in GitHub Actions. A separate PostgreSQL CI job now exercises concurrent idempotent retries, opposing transfers, and error-path balance preservation. Consult the latest [CI run](../../actions) for its actual result; do not claim PostgreSQL correctness if that job is failing. No hosted public demo is deployed; no production-readiness claims are made.


## PostgreSQL concurrency verification
The `postgres-integration` GitHub Actions job provisions a temporary PostgreSQL 16 service and runs `backend/tests/test_pg_integration.py` in an isolated Python process. It covers:
- 12 concurrent submissions using the **same** idempotency key (expect exactly one journaled transfer).
- 20 simultaneous transfers in opposite directions across two accounts (expect no deadlocks).
- Error cases that must not mutate balances or add journal entries.

These tests are reproducible integration checks, **not** a production load test or end-to-end deployment validation.

## Security and deployment note
This is a local-only demonstration. Do not publish the API with `DEMO_MODE=true` or a placeholder JWT secret. A public deployment will require rate limiting, proper secrets, API migrations, operations monitoring, secure cookies/token handling, and a separate security review.


## Public-facing portfolio showcase (frontend only)
The repository contains a **browser-only**, static React preview in `frontend/src/Showcase.tsx`. It uses fictional sample data, has no authentication or financial backend, and does not send transfer requests to an API. Its purpose is to let recruiters explore the interface without exposing an insecure development backend.

The `Public Showcase Build` workflow builds with `VITE_SHOWCASE_MODE=true` and prepares a GitHub Pages deployment. A successful workflow build does **not** necessarily mean GitHub Pages is enabled: the repository owner may need to enable **Settings → Pages → Build and deployment → GitHub Actions** and review the published URL.

## Production-mode restrictions
Set `APP_ENV=production` for a real API deployment. The backend refuses to start if:
- `DEMO_MODE=true`;
- `JWT_SECRET` has fewer than 48 characters;
- `FRONTEND_ORIGIN` does not start with `https://`;
- a non-PostgreSQL `DATABASE_URL` is configured.

Production disables API documentation, sets security-related response headers, issues shorter-lived JWTs, and rejects signups unless `ALLOW_REGISTRATION=true` is explicitly configured. Database auto-creation is disabled in production, so schema migrations must be built before a real API release. **These are limited guardrails, not a comprehensive security assessment.**

The backend is deliberately **not** deployed with GitHub Pages. Public API deployment remains blocked pending migration tooling, login rate limiting, session security review, error logging/monitoring, and hosting credentials.


## Versioned database migrations
Schema changes now live in `backend/migrations/versions/` and are managed by Alembic rather than by changing tables on application startup in production.

**Apply migrations before starting a production backend:**
```bash
cd backend
python -m pip install -r requirements.txt
alembic upgrade head
alembic current
```

Set `DATABASE_URL` and `JWT_SECRET` securely in the environment first. The initial revision creates the ledger tables, and the next revision adds the `login_attempts` table. The PostgreSQL CI job creates a fresh temporary database, executes all migrations, verifies the current revision, and exercises the ledger concurrency tests.

**Existing database caution:** These initial migrations are designed for a *new* database. An existing populated database created using `Base.metadata.create_all()` requires a carefully verified baseline/stamp strategy and backup. Do not run the initial `upgrade` blindly against an existing schema.

## Authentication defenses (limited scope)
- Failed password attempts are recorded in the database using a SHA-256 email identifier; this avoids storing email addresses in the counter table.
- Five unsuccessful attempts within 15 minutes cause subsequent attempts targeting that identifier to return HTTP 429 with a `Retry-After` header.
- Successful logins reset that identifier's failed-login counter.
- Production defaults to `ALLOW_REGISTRATION=false`; demonstration funding is rejected at production startup.
- JWTs expire after one hour in production; development tokens expire after eight hours.

**Not yet suitable for an exposed public API.** Additional controls still needed include independent IP-based abuse protection at the reverse proxy, registration/invitation flow, session revocation and secure token transport, secure credential recovery, audit logging, dependency security checks, and staging security tests. Do not deploy the live backend publicly until those are implemented and verified. The separately hosted browser-only showcase remains the recommended recruiter-facing URL.


## Session revocation (migration 0003)
Each successful sign-in now receives a unique JWT `jti` identifier. `POST /auth/logout` stores its identifier in the `revoked_tokens` table until the original token expiration. Every protected endpoint rejects tokens found in that table, including replays after logout. Other independently issued session tokens remain valid. The web client invokes the logout endpoint and immediately clears its local session.

Apply `alembic upgrade head` before running a production-mode API with the new schema. A housekeeping command `cd backend && python prune_revoked_tokens.py` can remove expired revocation entries from the current database; schedule this only with trusted operational credentials. Keep JWT signing secrets outside source control.

**Remaining limitations:** The browser client still uses JavaScript-accessible session storage for bearer tokens. For a hardened public deployment, use a security-reviewed same-origin session design, HttpOnly/Secure/SameSite cookies with CSRF defenses if appropriate, and a proper invitation/registration flow. Failed-login throttling is per email identifier, not a substitute for IP/routing abuse defenses or network access controls. The backend is intentionally not published as a public service yet.
