# LedgerFlow — Portfolio Walkthrough and CV Evidence

**Project:** LedgerFlow — Transactional Ledger & Financial Operations Simulator  
**Type:** Full-stack software engineering portfolio prototype (fictional values only)  
**Repository:** https://github.com/olabs123-hue/LedgerFlow.  
**Public UI showcase:** https://ledgerflow-showcase-olabs123.onrender.com  
**Read-only API health:** https://ledgerflow-api-staging-t1yt.onrender.com/ready

## 60-second recruiter tour

1. **Open the public showcase.** It displays sample financial balances, a fictional activity list and an interactive form. All actions change browser state; no payment or login API is called. Reloading resets the sample data.
2. **Review the system architecture.** [Architecture diagrams](../docs/ARCHITECTURE.md) explain the separate public-safe view, test-only interactive deployment, PostgreSQL schema and transfer sequence.
3. **Inspect the backend.** [`backend/app/main.py`](../backend/app/main.py) implements atomic transfers with deterministic PostgreSQL row locking, sender-scoped idempotency keys and paired ledger entries.
4. **View tests.** [PostgreSQL concurrency tests](../backend/tests/test_pg_integration.py) cover identical retries, opposing transfers and insufficient balance. [Interactive Chromium tests](../frontend/interactive-tests/cookie.spec.ts) cover cookie sessions, simulated transfers and logout. [Security audit](../SECURITY_AUDIT.md) lists remaining risks.
5. **Read measured results.** [Phase 3 report](../PHASE3_REPORT.md) documents bounded local PostgreSQL benchmarks and the SIGKILL/restart recovery scenario. Do not confuse CI throughput with deployed service throughput.

## Example CV entry (four bullets)

**LedgerFlow | Transactional Ledger & Financial Operations Simulator**  
*Python · FastAPI · PostgreSQL · React · TypeScript · Docker · GitHub Actions · Render*  
GitHub: https://github.com/olabs123-hue/LedgerFlow. · Demo: https://ledgerflow-showcase-olabs123.onrender.com

- Built a full-stack financial ledger **simulation** using FastAPI, PostgreSQL, React and TypeScript, with account management, fictional transfers and double-entry journal records.
- Implemented **atomic, idempotent transfers** using PostgreSQL row-level locking and deterministic lock ordering; tested competing requests, retries and balance invariants.
- Added security and release controls including Argon2 hashing, revocable JWT sessions, an opt-in HttpOnly cookie/CSRF flow, database-backed throttling, schema checks and CI security scans.
- Automated PostgreSQL integration, real-browser tests, database restoration and process-restart recovery; benchmarked **100 simulated transfers per concurrency setting** across 1/4/8 workers in isolated CI and published the measurements.

## Concise CV entry (two bullets)

- Engineered a PostgreSQL-backed **transactional ledger simulator** with atomic double-entry transfers, idempotency keys and deadlock-aware row locking; verified correctness under concurrent retries.
- Built React/FastAPI interfaces and automated security, database and recovery tests; measured up to **82.29 simulated transfers/s** in a **100-transfer, 4-worker in-process CI run** (not production throughput).

Use the four-bullet version for a systems/backend-focused CV when space permits, or the two-bullet version when Sharp Technologies and distributed event processing already take priority.

## What to avoid claiming

- **Do not claim real payments, bank connectivity, regulated financial processing or actual customer usage.** All value is fictional.
- **Do not claim the publicly hosted API supports live sign-in or transfers.** It is intentionally read-only.
- **Do not claim a complete penetration test or production security certification.** The security review is scoped to tests/scanners and documented checks.
- **Do not quote 82.29 transfers/s as a production benchmark or a guaranteed capacity.** It is a single in-process GitHub Actions result using local PostgreSQL.
- **Do not claim zero downtime or recovery-time SLAs.** Recovery CI verifies a specific restart/retry scenario only.

## Interview discussion points

**Why row locking?** Concurrent transfer handlers can otherwise read the same starting balance and overwrite each other's updates. Sorting locks by account ID avoids AB/BA lock-order deadlocks.

**Why idempotency?** A client can lose the response after the transfer commits. Retrying with the same key should return the original result rather than making a second debit. A changed request body with the same key is rejected.

**What did the benchmark show?** Four workers had the highest throughput among 1, 4 and 8 on one hot sender. More concurrency can increase waiting time on a locked account rather than scaling linearly.

**How is resilience checked?** A disposable CI process commits a transfer, forcefully kills the API, restarts PostgreSQL and retries the exact same request. It checks unchanged balance, one transfer and two balanced entries.

**Why keep the hosted API read-only?** Real ingress limits, secure operational onboarding, monitoring and long-lived database backups require verification before publicly enabling the simulation's write endpoints.

## Screenshots

The [Portfolio Screenshots workflow](https://github.com/olabs123-hue/LedgerFlow./actions/workflows/portfolio-screenshots.yml) generates real desktop and mobile screenshots of the **browser-only showcase** using Chromium; its downloadable CI artifact is time-limited. Do not substitute generated mockups for screenshots when describing the actual shipped UI.
