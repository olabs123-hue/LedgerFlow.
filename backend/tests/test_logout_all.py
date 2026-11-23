"""All-device revocation invalidates two cookies and a bearer token.

This covers the engineering logic; not a provider penetration test.
"""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./ledgerflow_test.sqlite"
os.environ["JWT_SECRET"] = "integration-test-secret-string-32-bytes-minimum-only"
os.environ["DEMO_MODE"] = "true"

from fastapi.testclient import TestClient
from app.main import app, Base, engine

ORIGIN="http://localhost:5173"
ACCOUNT={"email":"all-devices@example.org","password":"test-only-session-password-123"}

def test_account_wide_signout_revokes_all_device_sessions():
    Base.metadata.drop_all(engine)
    with TestClient(app) as first, TestClient(app) as second:
        assert first.post("/auth/register",json=ACCOUNT).status_code==201
        bearer=first.post("/auth/login",json=ACCOUNT).json()["access_token"]
        login_a=first.post("/browser/session",json=ACCOUNT,headers={"Origin":ORIGIN})
        login_b=second.post("/browser/session",json=ACCOUNT,headers={"Origin":ORIGIN})
        assert login_a.status_code==200 and login_b.status_code==200
        assert first.get("/browser/me").status_code==200
        assert second.get("/browser/me").status_code==200

        assert first.post("/browser/logout-all").status_code==403
        assert first.post("/browser/logout-all",headers={"Origin":ORIGIN,"X-CSRF-Token":"not-valid"}).status_code==403
        assert second.get("/browser/me").status_code==200

        logout=first.post("/browser/logout-all",headers={
            "Origin":ORIGIN,"X-CSRF-Token":login_a.json()["csrf_token"],
        })
        assert logout.status_code==200,logout.text
        assert first.cookies.get("lf_session") is None
        assert second.get("/browser/me").status_code==401
        assert first.get("/me",headers={"Authorization":"Bearer "+bearer}).status_code==401

        reauth=second.post("/browser/session",json=ACCOUNT,headers={"Origin":ORIGIN})
        assert reauth.status_code==200,reauth.text
        assert second.get("/browser/me").status_code==200
    Base.metadata.drop_all(engine)
