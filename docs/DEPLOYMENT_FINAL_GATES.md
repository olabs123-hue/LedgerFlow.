# LedgerFlow — Final Public Interactive Release Gate

**Date:** 23 November 2026  
**Current public mode:** React showcase is browser-local. Render FastAPI staging is read-only.  
**Policy:** Do not turn on public authentication, funding or transfers until each actual-provider gate passes. All currency amounts remain fictional.

## Provider inventory verified on 23 November 2026

- Render web service: `ledgerflow-api-staging-t1yt`, **Free Python**, Oregon, single instance, manual deployment, public health/readiness only.
- Render PostgreSQL: `ledgerflow-api-staging-db`, **Free PostgreSQL 16**, Oregon, expiry **21 December 2026 23:38 UTC**; no managed backups, zero external DB IP allowlist.
- React showcase: `ledgerflow-showcase-olabs123`, separate public static site.
- Existing public API and database have **not** been converted to paid plans, and production financial write routes have **not** been enabled.

## Deployment preconditions and acceptance

| Gate | Verified evidence required | Status |
| --- | --- | --- |
| Data durability | Provider-managed backups/PITR on a non-expiring database, and restoration into a separate instance with account-grant/journal reconciliation | **BLOCKED: Free Render PostgreSQL has no backups and expires** |
| Trusted edge rate limiting | HTTP 429 enforced by the **real** public ingress; verified client identity and anti-spoofing, plus error/abuse monitoring | **BLOCKED: only isolated Nginx CI ingress has been verified** |
| Operational account setup | An authorized operator can run `provision_demo_account.py` and `demo_operations grant/reconcile` without printing passwords or opening public signup | **BLOCKED on Free web service: no SSH/one-off jobs** |
| Cookie session and CSRF | Exact same-origin HTTPS, Secure/HttpOnly/SameSite cookies; Origin/CSRF rejection; sign-out current session and all sessions; invalid tokens rejected | **IMPLEMENTED AND TESTED IN CI; provider-specific test pending** |
| Encrypted secrets | Real random JWT secret, private database URLs and TLS; never expose them in repository, logs or CI artifacts | **Staging secrets set; verify new interactive deployment independently** |
| Environment startup guard | `APP_ENV=production`, `PUBLIC_API_READONLY=false`, `ALLOW_LIVE_API=I_UNDERSTAND_THE_RISK`, `AUTH_PEER_RATE_LIMIT=true`, `EDGE_RATE_LIMIT_VERIFIED=true`, `ALLOW_REGISTRATION=false`, `DEMO_MODE=false` | **Not authorized for activation until above evidence exists** |
| Recovery & observability | Actual Render database recovery drill, checks for auth / transfer errors, audit log retention and alerting | **PROVIDER-SPECIFIC WORK OUTSTANDING** |

`EDGE_RATE_LIMIT_VERIFIED=true` is a human assertion in configuration, not independent evidence. Do **not** set it simply to bypass startup validation.

## Hosting cost decision

According to Render's November 2026 public pricing, a baseline persistent **Postgres instance starts near US$6/month** and a **paid Starter web service near US$7/month**, approximately **US$13/month combined** before any added storage/bandwidth and other charges. Always verify current checkout pricing and workspace plan before ordering; no paid resources have been provisioned by this project workflow.

- [Render pricing](https://render.com/pricing)
- [Database](https://dashboard.render.com/d/dpg-dc12mn7f3r2c73bdpmkg-a)
- [Read-only staging web service](https://dashboard.render.com/web/srv-dc12p0nf3r2c73be0fgg)

A cheaper **database-only upgrade** may be useful for durable *read-only* staging, but the free web service does **not** support the trusted shell/one-off-job access needed for the current CLI invitation workflow. A separate securely implemented invitation mechanism would be needed if the service stays Free.

## Safe release sequence after explicit billing approval

1. Select and authorize the provider upgrade with its actual checkout price. **Do not upgrade or create billable resources automatically.**
2. Keep the original read-only staging deployment online. Set up a persistent Postgres service in the same region with managed PITR. Migrate the **schema** and only fictional disposable records. Verify the new database is at Alembic `0007_session_version`.
3. Run a **real** backup and restore drill into an isolated database, then `python -m demo_operations reconcile`. Record who owns retention, expiry and incident response.
4. Deploy `Dockerfile.interactive` on a controlled single-origin HTTPS service. Configure actual provider ingress rate-limit rules and validate attribution and spoof-resistance. Nginx settings in `ci/nginx-interactive.conf` are a test template, **not an active Render policy**.
5. Provision two demo-only identities using an authorized, private execution channel. Give each fictional opening credits with unique source references; never send passwords to public logs.
6. Verify real-browser secure cookies, cross-origin denial, CSRF denial, both logout modes, retry idempotency, duplicate prevention, 429 throttling, transfer reconciliation, health and error monitoring.
7. Enable the controlled demo for invited reviewers only. No public registration and no funding HTTP endpoint. Retain the current read-only API as the rollback option.
8. Rerun live verification after every release, and disable writes immediately upon any auth, backup, reconciliation or edge-control regression.

## Current release decision

**NO-GO for public interactive writes** on 23 November 2026. Provider-level protection and durable storage are not verified and recurring charges are not authorized.

**GO for portfolio use:** public browser-only showcase, live read-only API and isolated automated CI evidence remain usable.
