"""Production-style same-origin simulation journey with disposable PostgreSQL.

This suite must run with an intentionally isolated CI database. It does NOT
approve public interactive deployment or imply real edge rate limits exist.
"""
import os
from pathlib import Path

assert os.getenv("APP_ENV") == "production"
assert os.getenv("PUBLIC_API_READONLY") == "false"
assert os.getenv("ALLOW_REGISTRATION") == "false"
assert os.getenv("FRONTEND_ORIGIN") == "https://example.org"
assert os.getenv("INTERACTIVE_SITE_DIR")
assert Path(os.getenv("INTERACTIVE_SITE_DIR"), "index.html").is_file()

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import Account, Entry, SessionLocal, User, app
from provision_demo_account import provision_demo_user
from demo_operations import grant_fictional_credits, reconciliation_errors


def test_https_same_origin_login_transfer_logout_and_server_rendered_ui():
    with SessionLocal() as db:
        alice = provision_demo_user(db, "interactive-alice@example.org", "only-for-isolated-ci-123")
        bob = provision_demo_user(db, "interactive-bob@example.org", "only-for-isolated-ci-123")
    with SessionLocal() as db:
        grant_fictional_credits(db, alice, 100_000, "same-origin-initial-1")
    with SessionLocal() as db:
        grant_fictional_credits(db, alice, 50_000, "same-origin-initial-2")

    with TestClient(app, base_url="https://example.org") as client:
        index = client.get("/")
        assert index.status_code == 200, index.text
        assert "text/html" in index.headers["content-type"]
        assert "LedgerFlow" in index.text
        assert "script-src 'self'" in index.headers["content-security-policy"]
        assert "/assets/" in index.text
        assert client.get("/docs").status_code == 404
        assert client.post("/auth/register").status_code == 404
        assert client.post("/auth/login").status_code == 404
        assert client.post("/demo/credit").status_code == 404
        assert client.post("/transfers").status_code == 404
        assert client.get("/me").status_code == 404

        credentials = {"email": alice, "password": "only-for-isolated-ci-123"}
        assert client.post("/browser/session", json=credentials).status_code == 403
        assert client.post("/browser/session", json=credentials, headers={
            "Origin": "https://attacker.example"
        }).status_code == 403

        login = client.post("/browser/session", json=credentials, headers={
            "Origin": "https://example.org"
        })
        assert login.status_code == 200, login.text
        assert "access_token" not in login.json()
        assert "__Host-lf_session" in login.headers["set-cookie"]
        assert "secure" in login.headers["set-cookie"].lower()
        assert "httponly" in login.headers["set-cookie"].lower()
        assert "samesite=strict" in login.headers["set-cookie"].lower()
        csrf = login.json()["csrf_token"]
        assert len(csrf) == 64

        assert client.get("/browser/me").json()["balance_cents"] == 150_000
        assert client.get("/browser/session").json()["csrf_token"] == csrf
        assert client.post("/browser/transfers", json={
            "recipient_email": bob, "amount_cents": 1_250,
        }, headers={"Origin": "https://example.org", "Idempotency-Key": "test-transfer-123"}).status_code == 403

        request = {"recipient_email": bob, "amount_cents": 1_250}
        headers = {
            "Origin": "https://example.org", "X-CSRF-Token": csrf,
            "Idempotency-Key": "test-transfer-123",
        }
        transfer = client.post("/browser/transfers", json=request, headers=headers)
        assert transfer.status_code == 200, transfer.text
        assert not transfer.json()["replayed"]
        replay = client.post("/browser/transfers", json=request, headers=headers)
        assert replay.status_code == 200
        assert replay.json()["replayed"]
        assert client.get("/browser/me").json()["balance_cents"] == 148_750
        assert len(client.get("/browser/transfers").json()) == 1
        with SessionLocal() as db:
            assert db.scalar(select(func.sum(Entry.delta_cents))) == 0

        assert client.post("/browser/logout", headers={"Origin": "https://example.org"}).status_code == 403
        result = client.post("/browser/logout", headers={
            "Origin": "https://example.org", "X-CSRF-Token": csrf,
        })
        assert result.status_code == 200
        assert "__Host-lf_session" in result.headers["set-cookie"]
        assert client.get("/browser/me").status_code == 401

    # Database is disposable and the next test suite owns cleanup.
