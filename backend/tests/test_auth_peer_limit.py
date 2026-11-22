"""Rate limiter uses the socket peer and a shared SQL counter, not spoofable headers."""
import os
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./ledgerflow_test.sqlite"
os.environ["JWT_SECRET"] = "integration-test-secret-string-32-bytes-minimum-only"
os.environ["DEMO_MODE"] = "true"

from fastapi.testclient import TestClient
from sqlalchemy import update
import app.main as service


def test_shared_auth_bucket_spoof_resistance_and_window_reset(monkeypatch):
    monkeypatch.setattr(service, "AUTH_PEER_RATE_LIMIT", True)
    monkeypatch.setattr(service, "AUTH_PEER_LIMIT", 4)
    service.Base.metadata.drop_all(service.engine)
    with TestClient(service.app) as client:
        for i in range(4):
            response = client.post(
                "/auth/login",
                json={"email": f"missing-{i}@example.org", "password": "guess-password-123"},
                headers={"X-Forwarded-For": f"203.0.113.{i+1}"},
            )
            assert response.status_code == 401, response.text
        blocked = client.post(
            "/auth/login", json={"email": "other@example.org", "password": "guess-password-123"},
            headers={"X-Forwarded-For": "198.51.100.18"},
        )
        assert blocked.status_code == 429, blocked.text
        assert blocked.json()["detail"] == "Too many authentication requests"
        assert int(blocked.headers["Retry-After"]) >= 1
        with service.SessionLocal() as db:
            db.execute(update(service.AuthPeerBucket).values(window_epoch=0))
            db.commit()
        recovered = client.post(
            "/auth/login", json={"email": "new@example.org", "password": "guess-password-123"},
        )
        assert recovered.status_code == 401
    service.Base.metadata.drop_all(service.engine)


def test_disabled_rate_limit_does_not_touch_request_bucket(monkeypatch):
    monkeypatch.setattr(service, "AUTH_PEER_RATE_LIMIT", False)
    service.Base.metadata.drop_all(service.engine)
    with TestClient(service.app) as client:
        assert client.post(
            "/auth/login", json={"email": "none@example.org", "password": "guess-password-123"},
        ).status_code == 401
    with service.SessionLocal() as db:
        from sqlalchemy import func, select
        assert db.scalar(select(func.count()).select_from(service.AuthPeerBucket)) == 0
    service.Base.metadata.drop_all(service.engine)
