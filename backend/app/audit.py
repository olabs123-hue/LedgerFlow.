"""Privacy-minimizing structured request audit events for LedgerFlow.

Do not include Authorization headers, passwords, JWTs, request bodies, query strings,
email addresses or client IPs. Infrastructure retains stdout by its own policy.
"""
from __future__ import annotations

import json
import logging
import time

audit_logger = logging.getLogger("ledgerflow.security")
audit_logger.setLevel(logging.INFO)

EVENTS = {
    ("POST", "/auth/register"): "auth.registration",
    ("POST", "/auth/login"): "auth.login",
    ("POST", "/auth/logout"): "auth.logout",
    ("POST", "/transfers"): "ledger.transfer",
    ("GET", "/transfers"): "ledger.history",
    ("GET", "/me"): "account.read",
    ("POST", "/demo/credit"): "demo.credit",
}


def emit_request_event(*, request_id: str, method: str, path: str, status: int, elapsed_ms: int):
    """Only permit predefined event classes and non-sensitive scalar fields."""
    event = EVENTS.get((method, path))
    if event is None:
        return
    audit_logger.info(json.dumps({
        "event": event,
        "request_id": request_id,
        "status": int(status),
        "duration_ms": min(max(int(elapsed_ms), 0), 3_600_000),
        "timestamp_epoch": int(time.time()),
    }, separators=(",", ":"), sort_keys=True))
