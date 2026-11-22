"""Isolated fault-recovery test: kill API, restart database, retry transfer.

No connection to Render. CI Docker Compose exposes only loopback ports.
"""
import json
import subprocess
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
COMPOSE = ["docker", "compose"]

def run(*cmd: str) -> str:
    return subprocess.check_output([*cmd], text=True, stderr=subprocess.STDOUT).strip()

def send(path, *, method="GET", data=None, token=None, key=None):
    headers={"Accept":"application/json"}
    if data is not None:
        headers["Content-Type"]="application/json"
    if token:
        headers["Authorization"]="Bearer "+token
    if key:
        headers["Idempotency-Key"]=key
    req=urllib.request.Request(
        BASE+path, data=json.dumps(data).encode() if data is not None else None,
        headers=headers,method=method,
    )
    try:
        with urllib.request.urlopen(req,timeout=10) as response:
            return response.status,json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code,json.loads(exc.read().decode())

def ready():
    for _ in range(60):
        try:
            if send("/ready")[0]==200:
                return
        except (OSError,ValueError):
            pass
        time.sleep(2)
    raise AssertionError("API failed to recover within test readiness window")

def sql(query):
    return run(*COMPOSE,"exec","-T","db","psql","-U","ledgerflow","-d","ledgerflow","-Atc",query)

def main():
    ready()
    alice="phase3-alice@example.org"
    bob="phase3-bob@example.org"
    credentials={"email":alice,"password":"disposable-phase3-only-password"}
    for email in (alice,bob):
        status,data=send("/auth/register",method="POST",data={
            "email":email,"password":credentials["password"],
        })
        assert status==201,(email,status,data)
    status,data=send("/auth/login",method="POST",data=credentials)
    assert status==200,(status,data)
    token=data["access_token"]
    status,data=send("/demo/credit",method="POST",token=token)
    assert status==200,(status,data)
    payload={"recipient_email":bob,"amount_cents":1234}
    key="recovery-idempotency-phase3"
    status,data=send("/transfers",method="POST",data=payload,token=token,key=key)
    assert status==200 and data["replayed"] is False,(status,data)
    transfer_id=data["transfer_id"]
    pre=sql("SELECT COUNT(*)||':'||COALESCE(SUM(amount_cents),0) FROM transfers")
    journal=sql("SELECT COUNT(*)||':'||COALESCE(SUM(delta_cents),0) FROM journal_entries")
    assert pre=="1:1234",pre
    assert journal=="2:0",journal
    assert send("/me",token=token)[1]["balance_cents"]==98766

    # Forcefully terminate API without a graceful shutdown and restart database.
    run(*COMPOSE,"kill","-s","SIGKILL","api")
    run(*COMPOSE,"restart","db")
    run(*COMPOSE,"up","-d","api")
    ready()

    # Replaying an in-flight client's previously committed request after restart
    # must return the same durable transfer and not deduct money again.
    status,data=send("/transfers",method="POST",data=payload,token=token,key=key)
    assert status==200 and data["replayed"] is True,(status,data)
    assert data["transfer_id"]==transfer_id
    assert send("/me",token=token)[1]["balance_cents"]==98766
    assert pre==sql("SELECT COUNT(*)||':'||COALESCE(SUM(amount_cents),0) FROM transfers")
    assert journal==sql("SELECT COUNT(*)||':'||COALESCE(SUM(delta_cents),0) FROM journal_entries")
    assert send("/health")[0]==200
    print(json.dumps({
        "test":"SIGKILL API + PostgreSQL restart and retry",
        "healthy_after_restart":True,
        "idempotent_replay_after_restart":True,
        "transfer_rows":1,
        "journal_rows":2,
        "journal_net_cents":0,
        "sender_balance_cents":98766,
        "real_money":False,
    },indent=2))

if __name__=="__main__":
    main()
