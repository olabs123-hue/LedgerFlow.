"""Browser session tests: HttpOnly cookies, CSRF, origin checks and revocation.

The public read-only staging guard remains active in production and hides these paths.
"""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./ledgerflow_test.sqlite"
os.environ["JWT_SECRET"] = "integration-test-secret-string-32-bytes-minimum-only"
os.environ["DEMO_MODE"] = "true"

from fastapi.testclient import TestClient
from app.main import Base, app, engine

ORIGIN = "http://localhost:5173"
CREDENTIALS = {"email": "cookie-alice@example.com", "password": "password-for-cookie-alice"}


def test_browser_session_cookie_csrf_and_logout_revocation():
    Base.metadata.drop_all(engine)
    with TestClient(app) as client:
        assert client.post("/auth/register", json=CREDENTIALS).status_code == 201
        assert client.post("/auth/register", json={
            "email": "cookie-bob@example.com", "password": "password-for-cookie-bob"
        }).status_code == 201
        assert client.post("/browser/session", json=CREDENTIALS).status_code == 403
        assert client.post(
            "/browser/session", json=CREDENTIALS, headers={"Origin": "https://attacker.example"}
        ).status_code == 403
        session = client.post(
            "/browser/session", json=CREDENTIALS, headers={"Origin": ORIGIN}
        )
        assert session.status_code == 200, session.text
        assert "access_token" not in session.json()
        assert "token_type" not in session.json()
        csrf = session.json()["csrf_token"]
        cookie_header = session.headers["set-cookie"].lower()
        assert "httponly" in cookie_header
        assert "samesite=strict" in cookie_header
        assert "lf_session" in cookie_header
        token = client.cookies.get("lf_session")
        assert token
        assert token not in session.text
        refreshed = client.get("/browser/session", headers={"Origin": ORIGIN})
        assert refreshed.status_code == 200
        assert refreshed.json()["csrf_token"] == csrf
        assert client.get("/browser/session", headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.get("/browser/me").json()["email"] == CREDENTIALS["email"]
        assert client.get("/browser/transfers").status_code == 200

        request = {"recipient_email": "cookie-bob@example.com", "amount_cents": 100}
        transfer_headers = {"Origin": ORIGIN, "Idempotency-Key": "cookie-transfer-1"}
        assert client.post("/browser/transfers", json=request, headers=transfer_headers).status_code == 403
        bad_headers = {**transfer_headers, "X-CSRF-Token": csrf, "Origin": "https://evil.example"}
        assert client.post("/browser/transfers", json=request, headers=bad_headers).status_code == 403

        # Test a protected write with a legitimate session and CSRF proof.
        bearer = client.post("/auth/login", json=CREDENTIALS).json()["access_token"]
        assert client.post("/demo/credit", headers={"Authorization": "Bearer " + bearer}).status_code == 200
        good_headers = {**transfer_headers, "X-CSRF-Token": csrf}
        result = client.post("/browser/transfers", json=request, headers=good_headers)
        assert result.status_code == 200, result.text
        assert result.json()["replayed"] is False
        assert client.get("/browser/me").json()["balance_cents"] == 99900

        assert client.post("/browser/logout", headers={"Origin": ORIGIN}).status_code == 403
        logout = client.post("/browser/logout", headers={
            "Origin": ORIGIN, "X-CSRF-Token": csrf
        })
        assert logout.status_code == 200
        assert client.cookies.get("lf_session") is None
        assert client.get("/browser/me", headers={"Cookie": "lf_session=" + token}).status_code == 401
        # Bearer session remains valid independently of the cookie session.
        assert client.get("/me", headers={"Authorization": "Bearer " + bearer}).status_code == 200
    Base.metadata.drop_all(engine)
