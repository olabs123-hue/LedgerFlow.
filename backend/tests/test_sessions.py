"""Check sign-out revokes only the presented token."""
import os
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./ledgerflow_test.sqlite"
os.environ["JWT_SECRET"] = "integration-test-secret-string-32-bytes-minimum-only"
os.environ["DEMO_MODE"] = "true"

from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app, Base, engine, SessionLocal, RevokedToken


def test_logout_revokes_access_token_and_preserves_other_session():
    Base.metadata.drop_all(engine)
    with TestClient(app) as client:
        credentials = {"email": "session@example.com", "password": "secure-password-123"}
        assert client.post("/auth/register", json=credentials).status_code == 201
        first = client.post("/auth/login", json=credentials).json()["access_token"]
        second = client.post("/auth/login", json=credentials).json()["access_token"]
        assert first != second, "Each login must issue a distinct token"
        h1 = {"Authorization": "Bearer " + first}
        h2 = {"Authorization": "Bearer " + second}
        assert client.get("/me", headers=h1).status_code == 200
        assert client.post("/auth/logout", headers=h1).status_code == 200
        assert client.get("/me", headers=h1).status_code == 401
        assert client.post("/auth/logout", headers=h1).status_code == 401
        assert client.get("/me", headers=h2).status_code == 200
        with SessionLocal() as db:
            assert len(db.scalars(select(RevokedToken)).all()) == 1
    Base.metadata.drop_all(engine)
