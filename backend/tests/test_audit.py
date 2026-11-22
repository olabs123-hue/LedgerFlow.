"""Structured audit logging should preserve useful metadata without secrets or PII."""
import json
import logging
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./ledgerflow_test.sqlite"
os.environ["JWT_SECRET"] = "integration-test-secret-string-32-bytes-minimum-only"
os.environ["DEMO_MODE"] = "true"

from fastapi.testclient import TestClient
from app.main import app, Base, engine
from app.audit import emit_request_event


def test_request_audit_emits_safe_metadata_only(caplog):
    Base.metadata.drop_all(engine)
    caplog.set_level(logging.INFO, logger="ledgerflow.security")
    secret_password = "redact-me-supersecret-123"
    email = "private-person@example.com"
    bearer = "Bearer secret-token-should-never-appear"
    with TestClient(app) as client:
        res = client.post(
            "/auth/login?please_do_not_log=personal-data",
            json={"email": email, "password": secret_password},
            headers={"Authorization": bearer, "X-Request-ID": "attacker-controlled-id"},
        )
        assert res.status_code == 401
        request_id = res.headers["x-request-id"]
        assert len(request_id) == 24
        assert "attacker-controlled" not in request_id
        assert request_id != client.get("/health").headers["x-request-id"]
        res = client.post("/auth/register", json={"email": email, "password": secret_password})
        assert res.status_code == 201
        assert "x-request-id" in res.headers
    lines = [json.loads(record.message) for record in caplog.records
             if record.name == "ledgerflow.security"]
    assert any(row["event"] == "auth.login" and row["status"] == 401 for row in lines)
    assert any(row["event"] == "auth.registration" and row["status"] == 201 for row in lines)
    assert all(set(row) == {"event", "request_id", "status", "duration_ms", "timestamp_epoch"}
               for row in lines)
    entire_log = "\n".join(record.message for record in caplog.records)
    for sensitive in (secret_password, email, bearer, "personal-data", "attacker-controlled"):
        assert sensitive not in entire_log
    Base.metadata.drop_all(engine)


def test_unapproved_paths_are_never_logged(caplog):
    caplog.set_level(logging.INFO, logger="ledgerflow.security")
    emit_request_event(request_id="abc", method="GET", path="/health", status=200, elapsed_ms=3)
    emit_request_event(request_id="abc", method="GET", path="/unknown/private-info", status=404, elapsed_ms=3)
    assert not [record for record in caplog.records if record.name == "ledgerflow.security"]
