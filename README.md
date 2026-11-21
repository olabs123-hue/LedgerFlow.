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
This is a learning prototype and should not be deployed publicly as-is. DEMO_MODE provides unrestricted fictional credits and must remain off in public environments. Missing production controls include email verification, rate limiting, migrations, MFA, session revocation, and audit/security hardening. Concurrent cross-transfers may deadlock because locks are not acquired in canonical account order.

On 2026-11-21 Python compilation and two SQLite API smoke tests passed. Frontend dependency installation/build and Docker/PostgreSQL integration and concurrency tests were **not verified** in the available runtime. Do not claim production readiness or PostgreSQL concurrency correctness until independently tested.
