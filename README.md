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
