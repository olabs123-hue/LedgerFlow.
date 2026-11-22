# LedgerFlow Phase 2: controlled interactive demonstration

## Verified implementation

The production-style **same-origin** deployment artifact is `Dockerfile.interactive`. It builds the React cookie-only UI and FastAPI backend into one image. In the test topology, an Nginx HTTPS gateway enforces request body limits and rate limits before the app.

Automated acceptance workflows:
- `.github/workflows/ci.yml` exercises authentication, SQLite/real PostgreSQL migrations, idempotency, row locking, fictional credit grants, same-origin HTTPS-mode requests, and balance reconciliation.
- `.github/workflows/interactive-e2e.yml` builds the full isolated container stack, provisions fictional test accounts, tests actual Chromium cookie flows, verifies throttling under bursts and restores a PostgreSQL backup into a second test database.
- `.github/workflows/security.yml` performs dependency and static-code scans.
- `.github/workflows/verify-staging.yml` checks that the existing public Render staging service remains **read-only**.

A passing CI deployment-style test is **not** independent proof that Render's actual edge policy, backup retention, network trust or disaster recovery plan meets the same conditions.

## Operator-only invited users

For a controlled demonstration, a trusted operator with database write access creates fictional accounts offline:

```bash
cd backend
python provision_demo_account.py --email invited-tester@example.org
python -m demo_operations grant --email invited-tester@example.org --cents 100000 --reference opening-fixture-0001
python -m demo_operations reconcile
```

The account creation command requests a new password without displaying it, and stores only an Argon2 hash. The grant command creates **fictional** credit and a traceable funding record in the same database transaction; repeating a reference is refused. Reconciliation checks each account against opening grants plus journal movements, and checks that every transfer has two balanced entries.

Never use a real password or live banking details. The demo does not connect to banks or transfer actual funds. The public API has no registration or grant endpoint.

## Release gates before a publicly writable interactive URL

1. **Origin:** Host the React bundle and all `/browser` API operations under one HTTPS origin. Ensure `FRONTEND_ORIGIN` exactly matches it. Verify cookies carry `Secure; HttpOnly; SameSite=Strict` and the `__Host-` prefix.
2. **Edge abuse controls:** Configure a trusted ingress rate limit on live infrastructure; confirm HTTP 429 from that exact ingress and verify client-IP attribution and forwarded-header trust under the real hosting provider. The Nginx CI example alone is not proof that this works on Render.
3. **Private data:** Use only disposable fictional data. Keep public registration and bearer-token endpoints inaccessible. Provision and distribute invitation credentials out-of-band; never print credentials to a deployment log.
4. **Database durability:** Replace the expiring free staging PostgreSQL before relying on stable accounts. Enable encrypted provider-managed backups (or equivalent scheduled encrypted `pg_dump`), define retention, and perform a live-environment restore drill without touching the active database.
5. **Observability:** Configure audit-log retention, error alerts and throttling alerts. Validate session expiry and all-session revocation procedures.
6. **Safe enablement:** Only after verifying the above, deploy the interactive image behind the real edge. The production startup guard requires `PUBLIC_API_READONLY=false`, `AUTH_PEER_RATE_LIMIT=true`, `EDGE_RATE_LIMIT_VERIFIED=true`, `ALLOW_LIVE_API=I_UNDERSTAND_THE_RISK`, `ALLOW_REGISTRATION=false` and `DEMO_MODE=false`. `EDGE_RATE_LIMIT_VERIFIED` is **an operator assertion**, not an automatic verification.
7. **Rollback:** Keep the current read-only service available, test restricted routes following every rollout, and retain a known-good deployment to restore.

## Current release decision

**Interactive software and isolated end-to-end verification:** built.

**Public interactive service:** **not launched**. The existing free Render API remains intentionally read-only. The free PostgreSQL staging database is scheduled to expire on **21 December 2026**; it is not a long-term store. A public write-enabled URL must not be claimed until the real hosting ingress and persistence gates pass.
