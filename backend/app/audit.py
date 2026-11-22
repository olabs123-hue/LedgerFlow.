"""Privacy-minimizing structured request audit events for LedgerFlow.

Do not include Authorization headers, passwords, JWTs, request bodies, query strings,
email addresses or client IPs. Infrastructure retains stdout by its own policy.
"""
from __future__ import annotations

import json
import logging
import sys
import time

audit_logger = logging.getLogger("ledgerflow.security")
audit_logger.setLevel(logging.INFO)
# Dedicated stdout handler: don't depend on the ASGI server's root logger setup.
audit_handler = logging.StreamHandler(sys.stdout)
audit_handler.setFormatter(logging.Formatter("%(message)s"))
audit_logger.addHandler(audit_handler)
audit_logger.propagate = False

EVENTS = {
    ("POST", "/auth/register"): "auth.registration",
    ("POST", "/auth/login"): "auth.login",
    ("POST", "/auth/logout"): "auth.logout",
    ("POST", "/transfers"): "ledger.transfer",
    ("GET", "/transfers"): "ledger.history",
    ("GET", "/me"): "account.read",
    ("POST", "/demo/credit"): "demo.credit",
    ("POST", "/browser/session"): "browser.login",
    ("POST", "/browser/logout"): "browser.logout",
    ("POST", "/browser/transfers"): "browser.transfer",
    ("GET", "/browser/session"): "browser.session",
    ("GET", "/browser/me"): "browser.account",
    ("GET", "/browser/transfers"): "browser.history",
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
