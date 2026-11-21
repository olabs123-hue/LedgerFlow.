# LedgerFlow Security Review — 22 November 2026

**Scope:** Repository source review, authenticated simulation API endpoints, Render staging configuration, and automated GitHub Actions dependency/static scans. Not an external penetration test, independent professional certification, or a production financial-services assessment.

## Deployment decision

The public portfolio frontend is browser-only. The real API remains undeployed. The proposed Render staging API is explicitly **read-only**: `APP_ENV=production`, `PUBLIC_API_READONLY=true`, `DEMO_MODE=false`, `ALLOW_REGISTRATION=false`. Only `GET /health` and `GET /ready` are reachable. Other operations return 404. All balances are fictional.

The staging Render PostgreSQL database `ledgerflow-api-staging-db` is on a free plan, provisioned in Oregon, with an expiry of **21 December 2026**. Treat all its data as disposable and do not use it for actual financial transactions.

## Implemented safeguards and evidence

- Password hashes via Argon2; JWT HS256 tokens with exp and unique jti values; token revocation entries checked on protected requests.
- Failed-login counters persisted in DB, locked out after five failed attempts per identifier in a 15-minute window.
- One-hour JWT expiry in production; separate CORS allowlist; restrictive response headers; no public API documentation in production.
- PostgreSQL row locks on accounts in canonical order, request idempotency, atomic transfers, balanced double-entry journal records.
- Versioned Alembic migrations, including authentication throttle and revoked-token tables.
- Protected staging API read-only guard and an explicit startup check required before enabling any write API.
- CI: Python tests, PostgreSQL integration and concurrency, React build, Docker API smoke, Chromium desktop/mobile UI checks. Security workflow: `pip-audit`, `bandit -r app -ll`, `npm audit --omit=dev --audit-level=high`.

Consult each latest workflow result; existence of a job does not establish a pass until GitHub reports success.

## Open findings

| Priority | Finding | Required remediation |
|---|---|---|
| High | A fully interactive public API would use JavaScript-accessible bearer tokens in sessionStorage, exposing tokens to XSS and browser extensions. | Design same-origin session handling with HttpOnly, Secure, SameSite cookies and CSRF prevention; test lifecycle and refresh/revocation. |
| High | Public login and account creation lack per-IP/network-level abuse controls. Per-email lockouts could be abused to deny users access. | Use a trusted reverse proxy or WAF for per-IP and per-route rate limits, plus detection and monitoring. |
| High | Free Render database expires on 21 December 2026. No durable backup/restore/retention plan is in place. | Choose persistent funded DB for any durable use, configure backups and test restoration. Never store actual funds or sensitive customer information. |
| Medium | No invitation, email verification, password recovery, MFA or user lifecycle policy. | Implement and test before enabling public registration. |
| Medium | No structured security audit trail and alerting for auth, transfers, privilege changes or anomalous traffic. | Add redacted logs, metrics, alerts and retention policy. |
| Medium | No database-level balance nonnegative constraints, amount bounds, or immutable/journal balancing enforcement beyond application logic. | Add DB constraints and reconciliation/invariant tests; consider append-only ledger and reconciliation transactions. |
| Medium | Input-size limits, request timeouts and protection from resource exhaustion rely on infrastructure defaults. | Configure explicit body limits, worker concurrency limits and trusted proxy timeouts. |
| Medium | Dependencies use version ranges rather than deterministic locked releases; audits may change when resolver selects new versions. | Generate reviewable Python and npm lock files and run update automation. |
| Low | Backend uses deprecated FastAPI startup event. | Migrate to lifespan management. |
| Low | No evidence of production recovery drills, load tests, third-party penetration tests or regulatory compliance review. | Add separate plans and external review if scope grows beyond a portfolio prototype. |

## Release gates

1. Security workflow and full CI/Docker/browser checks must pass on the intended commit.
2. Keep all production write endpoints disabled until the high-priority open findings are closed.
3. Use encrypted secrets stored in Render; never commit DB credentials or JWT secrets.
4. Staging must contain fictional disposable data only.
5. Verify public endpoints return 404 for registration, login, transfers and funding, and verify health/readiness independently.
6. A complete production security audit requires scoped threat modeling, manual code review, dependency and infrastructure inspection, penetration testing, monitoring/recovery validation and documented sign-off.

**Verdict:** The locked read-only staging API can be a safe first deployment milestone after validation. The interactive backend **is not approved for unrestricted public production use**.
