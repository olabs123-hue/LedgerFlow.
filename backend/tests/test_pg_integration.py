"""PostgreSQL integration tests: real row locks, concurrent requests and journal integrity.

Run with DATABASE_URL pointing to a disposable PostgreSQL database.
This file must run in its own pytest process, separate from SQLite smoke tests.
"""
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

if not os.getenv("DATABASE_URL", "").startswith("postgresql"):
    pytest.skip("PostgreSQL DATABASE_URL required", allow_module_level=True)

from app.main import Account, Base, Entry, Transfer, User, app, engine, SessionLocal


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


def create_user(client, email):
    result = client.post("/auth/register", json={
        "email": email, "password": "secure-password-123"
    })
    assert result.status_code == 201, result.text
    result = client.post("/auth/login", json={
        "email": email, "password": "secure-password-123"
    })
    assert result.status_code == 200, result.text
    return result.json()["access_token"]


def auth(token, key=None):
    headers = {"Authorization": f"Bearer {token}"}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def test_concurrent_identical_retry_creates_only_one_transfer(client):
    alice = create_user(client, "alice@example.com")
    bob = create_user(client, "bob@example.com")
    assert client.post("/demo/credit", headers=auth(alice)).status_code == 200
    payload = {"recipient_email": "bob@example.com", "amount_cents": 5000}
    key = "identical-request-12345"
    with ThreadPoolExecutor(max_workers=8) as executor:
        responses = list(executor.map(
            lambda _: client.post("/transfers", json=payload, headers=auth(alice, key)),
            range(12),
        ))
    assert all(response.status_code == 200 for response in responses), [
        (r.status_code, r.text) for r in responses
    ]
    assert sum(not r.json()["replayed"] for r in responses) == 1
    assert client.get("/me", headers=auth(alice)).json()["balance_cents"] == 95000
    assert client.get("/me", headers=auth(bob)).json()["balance_cents"] == 5000
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Transfer)) == 1
        assert db.scalar(select(func.count()).select_from(Entry)) == 2
        assert db.scalar(select(func.sum(Entry.delta_cents))) == 0


def test_simultaneous_opposing_transfers_do_not_deadlock(client):
    alice = create_user(client, "alice@example.com")
    bob = create_user(client, "bob@example.com")
    for token in (alice, bob):
        assert client.post("/demo/credit", headers=auth(token)).status_code == 200

    tasks = [
        (alice, "bob@example.com", f"alice-to-bob-{i:04d}")
        if i % 2 == 0 else
        (bob, "alice@example.com", f"bob-to-alice-{i:04d}")
        for i in range(20)
    ]

    def send(item):
        token, email, key = item
        return client.post(
            "/transfers",
            json={"recipient_email": email, "amount_cents": 100},
            headers=auth(token, key),
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        responses = list(executor.map(send, tasks))
    assert all(r.status_code == 200 for r in responses), [
        (r.status_code, r.text) for r in responses
    ]
    assert client.get("/me", headers=auth(alice)).json()["balance_cents"] == 100000
    assert client.get("/me", headers=auth(bob)).json()["balance_cents"] == 100000
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Transfer)) == 20
        assert db.scalar(select(func.count()).select_from(Entry)) == 40
        assert db.scalar(select(func.sum(Entry.delta_cents))) == 0


def test_error_paths_preserve_account_balances(client):
    alice = create_user(client, "alice@example.com")
    bob = create_user(client, "bob@example.com")
    assert client.post("/demo/credit", headers=auth(alice)).status_code == 200
    request = {"recipient_email": "bob@example.com", "amount_cents": 150}
    result = client.post("/transfers", headers=auth(alice, "unique-request-one"), json=request)
    assert result.status_code == 200, result.text
    changed = client.post("/transfers", headers=auth(alice, "unique-request-one"), json={**request, "amount_cents": 200})
    assert changed.status_code == 409
    missing = client.post("/transfers", headers=auth(alice, "unique-request-two"), json={"recipient_email": "missing@example.com", "amount_cents": 100})
    assert missing.status_code == 404
    overdraft = client.post("/transfers", headers=auth(alice, "unique-request-three"), json={"recipient_email": "bob@example.com", "amount_cents": 500000})
    assert overdraft.status_code == 400
    assert client.get("/me", headers=auth(alice)).json()["balance_cents"] == 99850
    assert client.get("/me", headers=auth(bob)).json()["balance_cents"] == 150
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Transfer)) == 1
        assert db.scalar(select(func.sum(Entry.delta_cents))) == 0
