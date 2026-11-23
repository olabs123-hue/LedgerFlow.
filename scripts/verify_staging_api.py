"""Verify the read-only LedgerFlow public staging API from a remote CI runner.\n\nRecheck after migration 0007: account-wide session revocation must remain inaccessible.

This intentionally DOES NOT authenticate or create a user. All POST requests must be
blocked before reaching handlers. Use only against the configured staging service.
"""
import json
import os
import time
import urllib.error
import urllib.request
import urllib.parse

BASE = os.environ.get("STAGING_API_URL", "").rstrip("/")
EXPECTED_HOST = "ledgerflow-api-staging-t1yt.onrender.com"
if not BASE.startswith("https://") or urllib.parse.urlparse(BASE).hostname != EXPECTED_HOST:
    raise SystemExit(f"Refusing to probe anything other than https://{EXPECTED_HOST}")

def call(method, path):
    req = urllib.request.Request(BASE + path, method=method, headers={
        "Accept": "application/json",
        "User-Agent": "LedgerFlow-Staging-Safety-Check/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            status = response.status
            headers = response.headers
            raw = response.read(2048).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        status = error.code
        headers = error.headers
        raw = error.read(2048).decode("utf-8", errors="replace")
    return status, headers, raw

def retry_readiness(path):
    last = None
    for attempt in range(12):
        try:
            last = call("GET", path)
            if last[0] == 200:
                return last
        except (OSError, TimeoutError) as exc:
            last = str(exc)
        time.sleep(10)
    raise AssertionError(f"{path}: no successful response; last result {last!r}")

def main():
    for path in ("/health", "/ready"):
        status, headers, payload = retry_readiness(path)
        result = json.loads(payload)
        assert result["status"] in ("ok", "ready"), (path, payload)
        assert result["simulation"] is True
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("X-Frame-Options") == "DENY"
        assert "max-age=" in headers.get("Strict-Transport-Security", "")
        assert headers.get("Cache-Control") == "no-store"
        assert headers.get("Content-Security-Policy") == "default-src 'none'; frame-ancestors 'none'"
        assert headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=()"
        assert len(headers.get("X-Request-ID", "")) == 24
        print(f"PASS GET {path}: HTTP {status}, secure response headers")

    blocked = (
        ("GET", "/"),
        ("GET", "/docs"),
        ("GET", "/openapi.json"),
        ("GET", "/redoc"),
        ("GET", "/assets/index.js"),
        ("GET", "/me"),
        ("GET", "/transfers"),
        ("POST", "/auth/register"),
        ("POST", "/auth/login"),
        ("POST", "/auth/logout"),
        ("POST", "/transfers"),
        ("POST", "/demo/credit"),
        ("GET", "/browser/session"),
        ("GET", "/browser/me"),
        ("GET", "/browser/transfers"),
        ("POST", "/browser/session"),
        ("POST", "/browser/transfers"),
        ("POST", "/browser/logout"),
        ("POST", "/browser/logout-all"),
    )
    request_ids = set()
    for method, path in blocked:
        status, headers, _ = call(method, path)
        assert status == 404, f"SECURITY FAILURE: {method} {path} returned {status}, expected 404"
        request_id = headers.get("X-Request-ID", "")
        assert len(request_id) == 24, (method, path, "missing request correlation ID")
        assert request_id not in request_ids, (method, path, "duplicate request correlation ID")
        assert headers.get("Cache-Control") == "no-store"
        request_ids.add(request_id)
        print(f"PASS {method} {path}: HTTP 404 with secure headers")

if __name__ == "__main__":
    main()
