# LedgerFlow — Phase 3 Performance & Reliability Verification

**Verification date:** 22 November 2026

**Status:** Completed for the **isolated portfolio simulation and CI verification scope**. Not certified for public production use. Phase 1/2 deployment blockers remain.

## Scope and environment

Benchmark runs used a GitHub-hosted `ubuntu-latest` runner, Python/FastAPI `TestClient` inside the same process as the API, PostgreSQL 16 on runner-local Docker, JWT authentication, and real transactional transfers with PostgreSQL row locks and two journal rows per transfer.

Each worker configuration performs **100 distinct simulated transfers** from one funded account to one recipient, then verifies 10 repeated idempotency keys. Each run uses freshly generated fictional accounts. Source: `backend/benchmark_transfers.py`.

**This is *not* an HTTP network load test**: the in-process client bypasses TCP/TLS/network hops and does not represent deployed Render capacity or sustainable 24/7 throughput. Shared CI CPU, scheduling and database contention affect timings. No latency/throughput SLO or production capacity claim follows from these single samples.

## Reproduced measurements

| Concurrent workers | Transfers | Errors | Throughput (transfers/s) | p50 (ms) | p95 (ms) | p99 (ms) | Elapsed (s) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 100 | 0 | **62.15** | 11.49 | 41.93 | 116.22 | 1.609 |
| 4 | 100 | 0 | **82.29** | 44.49 | 68.17 | 83.93 | 1.215 |
| 8 | 100 | 0 | **49.81** | 102.34 | 431.99 | 516.98 | 2.008 |

All scenarios reported **10/10 successful idempotent retries**, **100 persisted transfers**, **200 journal rows**, correctly adjusted sender/recipient balances and **zero reconciliation errors**. The percentile method is nearest-rank based on elapsed time for each in-process request.

**Interpretation:** In this sample, 4 worker threads delivered the highest throughput of the three tested configurations; 8 workers experienced substantial contention and worse tail latency. This is consistent with serialized account-row locking under a single hot sender, but should not be treated as a generalized scaling curve without repeated runs, independent accounts and remote-network measurements.

**Evidence:** [GitHub Actions — Phase 3 benchmark and recovery](https://github.com/olabs123-hue/LedgerFlow./actions/runs/45073286344). Three machine-readable JSON artifacts (1, 4 and 8 workers) are uploaded to that run with 30-day retention.

A previous 4-worker run measured **66.80 transfers/s**, p50 **57.34 ms**, p95 **66.72 ms** and p99 **115.42 ms**. The difference illustrates runner-to-run variability. [Earlier run](https://github.com/olabs123-hue/LedgerFlow./actions/runs/45073138176).

## Fault injection and data recovery

`scripts/phase3_recovery.py` runs on a disposable local Docker Compose stack. It:

1. Creates two fictional users, grants 100,000 cents in fictional credit, and commits a 1,234-cent transfer.
2. Captures committed transfer count, total amount and double-entry journal totals.
3. Sends **SIGKILL** to the API container, restarts the PostgreSQL container and starts the API again.
4. Waits for the readiness endpoint and retries the **same idempotency key**.
5. Verifies the same transfer ID is returned with `replayed=true`, exactly one transfer persists, the journal contains two entries summing to zero, and the sender retains 98,766 fictional cents.

**Result:** Passed. The test does not simulate partial disk corruption, regional failover, simultaneous node loss, or data-center outage.

The separate [controlled interactive E2E workflow](https://github.com/olabs123-hue/LedgerFlow./actions/runs/45072376273) verifies a compressed PostgreSQL dump can be restored into a second disposable database, preserving account balances, recorded funding grants and balanced transfer journals. That does **not** establish an operational backup retention policy for the free Render database.

## Health monitoring

`.github/workflows/verify-staging.yml` is configured with a six-hour UTC schedule (`17 */6 * * *`) to run the staging probe. It verifies HTTP 200 readiness, security headers, and HTTP 404 on registration, authentication, transfers, browser sessions, static frontend assets and documentation paths.

GitHub Actions schedules are best-effort and can be delayed. A failing workflow is visible in GitHub Actions; a configured paging/on-call alert and independent external uptime SLA are **not** in place.

## Phase 3 acceptance checklist

- [x] Reproducible measurement code committed
- [x] Compare throughput and latency at 1, 4 and 8 workers
- [x] Record actual results and test conditions
- [x] Verify persistence, idempotency and journal conservation during load
- [x] API crash and database restart recovery test
- [x] Restore-check evidence from isolated PostgreSQL backup
- [x] Periodic live read-only health and route verification configured
- [x] Measured machine-readable CI artifacts and logs retained per Actions configuration

## Remaining production deployment gates (not Phase 3 CI failures)

1. **Phase 1:** Independently verify the actual public ingress edge rate-limit policy, secure client-IP attribution, alerting and session lifecycle under provider infrastructure.
2. **Phase 2:** Arrange durable database hosting/backups and a live restoration drill, provision invited demo accounts securely, then approve and verify an actual public interactive release.
3. **Future optimization:** Run repeated experiments across independent accounts and hot accounts, with external network clients, controlled host sizing, sustained load and regression baselines. Avoid claiming maximum sustainable throughput from the three small samples.

**Suggested defensible CV phrasing:** “Benchmarked PostgreSQL-backed simulated transfers at 1/4/8 concurrent workers (100 transfers per configuration), validated idempotent retries and balanced journals, and automated API-crash/database-restart recovery in CI.” Include a numeric throughput only with the explicit in-process CI environment and measurement caveat.
