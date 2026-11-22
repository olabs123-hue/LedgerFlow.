"""Repeatable in-process FastAPI -> PostgreSQL transfer benchmark.

Simulation-only. This is NOT an internet load test or production throughput claim.
Run only against a disposable database. Produces JSON with timings and checks.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import (Account, Entry, FundingGrant, SessionLocal, Transfer,
                      User, app, password_hasher, SECRET)
from demo_operations import grant_fictional_credits, reconciliation_errors

def percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        raise ValueError("No samples")
    # Nearest-rank percentile for repeatability.
    return sorted_values[max(0, min(len(sorted_values)-1,
                     int((len(sorted_values)*fraction + 0.999999999)) - 1))]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", default="benchmark-results.json")
    args = parser.parse_args()
    if not 1 <= args.count <= 400 or not 1 <= args.workers <= 16:
        parser.error("Use 1-400 transfers and 1-16 worker threads")
    if not os.environ.get("BENCHMARK_DISPOSABLE_DB") == "I_ACKNOWLEDGE":
        raise SystemExit("Requires BENCHMARK_DISPOSABLE_DB=I_ACKNOWLEDGE")
    db_url = os.getenv("DATABASE_URL", "")
    if "localhost" not in db_url and "127.0.0.1" not in db_url:
        raise SystemExit("Refusing to benchmark a non-local database")
    if not db_url.startswith("postgresql"):
        raise SystemExit("Benchmark requires real local PostgreSQL")

    run_id = uuid.uuid4().hex[:12]
    sender_mail = f"bench-sender-{run_id}@example.org"
    receiver_mail = f"bench-receiver-{run_id}@example.org"
    with SessionLocal() as db:
        users = []
        for email in (sender_mail, receiver_mail):
            user = User(email=email, password_hash=password_hasher.hash("disposable-benchmark-only-123"))
            db.add(user)
            db.flush()
            db.add(Account(user_id=user.id, balance_cents=0))
            users.append(user.id)
        db.commit()
    with SessionLocal() as db:
        grant_fictional_credits(db, sender_mail, 100_000, f"benchmark-funding-{run_id}")

    token = jwt.encode({
        "sub":str(users[0]),"jti":uuid.uuid4().hex,
        "exp":datetime.now(timezone.utc).timestamp()+3600,
    }, SECRET,algorithm="HS256")
    payload = {"recipient_email":receiver_mail,"amount_cents":100}
    headers = {"Authorization":f"Bearer {token}"}
    latencies_ms = []
    failed = []
    def task(i:int):
        key = f"bench-{run_id}-{i:05d}"
        start = time.perf_counter()
        try:
            with TestClient(app) as client:
                r = client.post("/transfers",json=payload,headers={
                    **headers,"Idempotency-Key":key,
                })
            return i, (time.perf_counter()-start)*1000, r.status_code, r.json()
        except Exception as exc:
            return i,(time.perf_counter()-start)*1000,0,{"error":type(exc).__name__}

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        responses = list(pool.map(task, range(args.count)))
    elapsed = time.perf_counter()-started
    for index,latency,status,data in responses:
        latencies_ms.append(latency)
        if status != 200 or data.get("replayed") is not False:
            failed.append({"index":index,"status":status})
    if failed:
        raise SystemExit(f"Benchmark requests failed: {failed[:10]}")
    # Retry first 10 idempotency keys, verifying no duplicate transfers created.
    replay_success = 0
    with TestClient(app) as client:
        for i in range(min(10,args.count)):
            response = client.post("/transfers",json=payload,headers={
                **headers,"Idempotency-Key":f"bench-{run_id}-{i:05d}",
            })
            if response.status_code == 200 and response.json()["replayed"]:
                replay_success+=1
    if replay_success != min(10,args.count):
        raise SystemExit("Idempotent replay failed")

    with SessionLocal() as db:
        account_ids = db.scalars(select(Account.id).join(User).where(User.email.in_([
            sender_mail,receiver_mail,
        ]))).all()
        count = db.scalar(select(func.count()).select_from(Transfer).where(
            Transfer.sender_id==account_ids[0],
        ))
        entries = db.scalar(select(func.count()).select_from(Entry).join(Transfer).where(
            Transfer.sender_id==account_ids[0],
        ))
        assert count==args.count, (count,args.count)
        assert entries==2*args.count, entries
        assert reconciliation_errors(db)==[], "Reconciliation invariant failure"
        sender_balance = db.scalar(select(Account.balance_cents).join(User).where(
            User.email==sender_mail,
        ))
        receiver_balance = db.scalar(select(Account.balance_cents).join(User).where(
            User.email==receiver_mail,
        ))
        assert sender_balance == 100000-100*args.count
        assert receiver_balance == 100*args.count

    ordered=sorted(latencies_ms)
    result={
        "benchmark":"FastAPI TestClient -> disposable PostgreSQL row-lock transfer",
        "environment":"GitHub-hosted ubuntu-latest runner, local PostgreSQL 16; simulated funds",
        "run_id":run_id,
        "requests":args.count,
        "workers":args.workers,
        "errors":len(failed),
        "successful_replays":replay_success,
        "duration_seconds":round(elapsed,3),
        "throughput_requests_per_second":round(args.count/elapsed,2),
        "latency_ms":{
            "p50":round(percentile(ordered,.50),2),
            "p95":round(percentile(ordered,.95),2),
            "p99":round(percentile(ordered,.99),2),
            "mean":round(statistics.mean(ordered),2),
        },
        "transfer_rows":count,
        "journal_rows":entries,
        "balanced_reconciliation":True,
        "limitations":"Client and API share one CI process; TLS, network latency and sustained workload are NOT measured. Do not present as live production throughput.",
    }
    with open(args.output,"w",encoding="utf8") as fp:
        json.dump(result,fp,indent=2)
    print(json.dumps(result,indent=2))

if __name__ == "__main__":
    main()
