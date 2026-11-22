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
| Medium | Nonnegative balances, positive transfer amounts, distinct sender/recipient accounts, and nonzero journal entries now have database-level CHECK constraints (revision 0004). However, immutability and aggregate double-entry balancing are still only enforced through application logic and tests. | Add controlled append-only journals, restricted database roles and automated reconciliation checks. |
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


## Deployment verification (22 November 2026)

- A dedicated remote GitHub Actions probe checks the **actual deployed** Render API with `GET /health` and `GET /ready` returning HTTP 200, and verifies that authentication, registration, account, transfer, demo-credit and documentation routes return HTTP 404.
- The latest passing probe: https://github.com/olabs123-hue/LedgerFlow./actions/runs/44963630729
- Migration `0004_ledger_checks` adds DB-enforced CHECK constraints and is validated against disposable PostgreSQL in CI. These changes must be deployed separately to Render; a GitHub commit alone does not apply migrations to staging.
- Neither the live API probe nor automated security scanner is a complete professional penetration test or formal sign-off.


## Phase 1 security-hardening update (22 November 2026)

- Introduced `backend/app/audit.py`: allowlisted, structured JSON security events covering authentication and ledger endpoints, response status, latency, a fresh server-generated request ID and event timestamp. Sensitive input fields, passwords, access tokens, email addresses, query strings and client IPs are never intentionally included in **these audit events**.
- Added `X-Request-ID`, API-only restrictive `Content-Security-Policy`, and `Permissions-Policy` headers.
- Added `backend/tests/test_audit.py`, asserting correlation ID uniqueness, rejection of user-provided request identifiers, appropriate event types, and absence of secret strings and personally identifying inputs from the structured audit event output.
- Included the audit regression suite in backend CI. Confirm latest passing run before treating the updated code as validated.
- **Current limitations:** These are application-level structured events, not a complete audit trail with persistent, tamper-evident storage and retention. Standard server/proxy access and error logs can have separate logging rules; audit their configuration before enabling real interactive public use. IP-based rate limiting/WAF, secure same-origin browser sessions, backups, recovery drills, comprehensive threat modeling and manual penetration tests remain outstanding.
- **Rollout control:** The Render staging API has automatic Git deployments disabled, so these source commits are **not** yet applied to the live staging service. Keep `PUBLIC_API_READONLY=true`; do not enable `ALLOW_LIVE_API`.


## Cookie-session prototype (Phase 1, November 2026)

Cookie authentication is available in local/test mode through the new routes: `POST /browser/session`, `GET /browser/session`, `GET /browser/me`, `GET /browser/transfers`, `POST /browser/transfers`, and `POST /browser/logout`.

- The server sets the signed access token in an **HttpOnly, SameSite=Strict** cookie; production mode additionally sets **Secure**. The browser-session login response exposes a session-bound HMAC CSRF proof, but **never the JWT**.
- State-changing browser routes require the exact configured `Origin` and the session-bound `X-CSRF-Token` proof. Logout persists token revocation using the existing database table. Browser transfers retain the original transaction locks and idempotency handling.
- Dedicated tests verify invalid origins/CSRF, cookie properties, sign-in, transfer, sign-out, revoked cookie reuse, and bearer-session independence.
- The existing public staging API is **read-only** and blocks all these new routes. It has not been turned into an interactive public service.
- **Next release gates:** provide a true same-origin frontend/API topology and in-memory CSRF handling; carefully review proxy and CORS deployment settings; implement a trusted per-client IP rate limit at the edge; harden session renewal, lifetime/rotation and logout-all behavior; implement invitation-only account provisioning; complete ongoing audit monitoring, backups and recovery; and verify everything against staging before opening the financial endpoints.

Cookie authentication is an engineering prototype, **not a certification of complete production session security**. Keep `PUBLIC_API_READONLY=true` in Render.


## Shared auth throttling and same-origin client (November 2026)

- **Migration 0005** adds `auth_peer_buckets`: an atomic database-backed, rolling 60-second window with an adjustable test limit and 60 authentication requests per window by default. The rate limiter is **opt-in** (`AUTH_PEER_RATE_LIMIT=true`) and covers `POST /auth/login`, `POST /browser/session`, and `POST /auth/register`. It uses the ASGI connection peer rather than reading untrusted forwarding headers.
- This is **not a verified per-end-user IP/WAF limit**. Render may forward requests from a shared proxy address, and ASGI scope behavior can depend on proxy trust configuration. A shared proxy address can cause legitimate users to share a limiter bucket; do not turn this on publicly until proxy topology and edge abuse controls are verified.
- The production startup gate rejects a write-enabled interactive deployment unless `AUTH_PEER_RATE_LIMIT=true` **and** `EDGE_RATE_LIMIT_VERIFIED=true`, in addition to the existing explicit `ALLOW_LIVE_API=I_UNDERSTAND_THE_RISK`. The latter flag is an operator assertion, not evidence of edge enforcement; production review remains mandatory.
- The browser session cookie uses the `__Host-` prefix under production HTTPS so that browsers require a Secure, host-only cookie with path `/`.
- `frontend/src/CookieApp.tsx` is an **opt-in** browser client enabled with `VITE_COOKIE_AUTH_MODE=true` (only when `VITE_SHOWCASE_MODE` is not enabled). It calls relative `/browser` endpoints with `credentials: same-origin`, holds the CSRF proof only in memory and does not store the JWT in JavaScript-accessible storage. Vite proxies `/browser` to the local FastAPI development server.
- The current public Render showcase remains browser-only and the public API remains read-only. Do not deploy the cookie client on a different origin from the API and assume `SameSite=Strict` works for cross-site authentication. A future interactive deployment requires a same-origin reverse proxy and independently tested network policy.
- The same-origin client currently does **not** support invitation provisioning, funded fixture setup, all-session revocation, tested token refresh or comprehensive user-management lifecycle. These remain unresolved, as do external WAF/rate-limit setup and durable database recovery.
