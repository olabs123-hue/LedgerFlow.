"""Production-mode HTTP checks against migrated disposable PostgreSQL.

Do not run against a database containing important data.
"""
import os

assert os.getenv("APP_ENV") == "production", "Run only with production mode in CI"
assert os.getenv("DEMO_MODE", "").lower() == "false"

from fastapi.testclient import TestClient
from app.main import app


def test_production_disables_public_registration_funding_and_docs():
    with TestClient(app) as client:
        registration = client.post(
            "/auth/register",
            json={"email": "not-registered@example.com", "password": "secure-password-123"},
        )
        assert registration.status_code == 404, registration.text
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        # Funding endpoint stays unavailable even when a request supplies a token.
        assert client.post("/demo/credit").status_code in (401, 403, 404)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["cache-control"] == "no-store"
        assert "strict-transport-security" in response.headers
        # Public API mode allows only health checks, and blocks all financial routes.
        assert client.get("/ready").status_code == 200
        assert client.get("/me").status_code == 404
        assert client.get("/transfers").status_code == 404
        assert client.post("/auth/login", json={"email": "test@example.com", "password": "bad-password-123"}).status_code == 404
        assert client.post("/auth/logout").status_code == 404
        # The cookie session prototypes must remain inaccessible in public staging.
        assert client.get("/browser/session").status_code == 404
        assert client.get("/browser/me").status_code == 404
        assert client.get("/browser/transfers").status_code == 404
        assert client.post("/browser/session").status_code == 404
        assert client.post("/browser/transfers").status_code == 404
        assert client.post("/browser/logout").status_code == 404
        assert client.post("/demo/credit").status_code == 404
        # Exercise login-throttling only in a separate, nonpublic production-mode test.
