"""Interactive-mode production policy is cookie-only, signup-disabled.

Tests run against ephemeral CI PostgreSQL after migrations; never real user data.
"""
import os

assert os.getenv("APP_ENV") == "production"
assert os.getenv("PUBLIC_API_READONLY") == "false"
assert os.getenv("ALLOW_REGISTRATION") == "false"

from fastapi.testclient import TestClient
from app.main import app


def test_interactive_mode_hides_all_legacy_bearer_and_funding_routes():
    with TestClient(app) as client:
        for path in ("/", "/docs", "/openapi.json", "/auth/login",
                     "/auth/register", "/auth/logout", "/me",
                     "/transfers", "/demo/credit"):
            for method in ("GET", "POST"):
                response = client.request(method, path)
                assert response.status_code == 404, (method, path, response.text)
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200
        # Cookie endpoints remain present, but reject unauthenticated requests.
        assert client.get("/browser/me").status_code == 401
        assert client.post("/browser/logout-all").status_code == 401
        assert client.get("/browser/session").status_code == 401
        assert client.post("/browser/session",
            json={"email": "nobody@example.org", "password": "long-unknown-password"}
        ).status_code == 403
