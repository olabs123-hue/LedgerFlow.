"""Docker Compose end-to-end smoke test against an isolated local simulation stack.

Requires web localhost:5173 and API localhost:8000 started by docker compose.
No real payment endpoints or real money are involved.
"""
import json
import time
import urllib.error
import urllib.request
import uuid

API = "http://127.0.0.1:8000"
WEB = "http://127.0.0.1:5173"


def request(url, method="GET", body=None, token=None, key=None):
    payload = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json" if url.startswith(API) else "text/html"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    if key:
        headers["Idempotency-Key"] = key
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()
            if url.startswith(API):
                try:
                    return response.status, json.loads(data.decode())
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Non-JSON API response from {url}: HTTP {response.status}, body={data[:160]!r}") from exc
            return response.status, data.decode()
    except urllib.error.HTTPError as error:
        raw = error.read().decode(errors="replace")
        if url.startswith(API):
            try:
                return error.code, json.loads(raw)
            except json.JSONDecodeError:
                return error.code, {"detail": raw[:250]}
        return error.code, raw



def wait_for_stack():
    last = None
    for attempt in range(45):
        try:
            api_status, health = request(API + "/health")
            web_status, html = request(WEB)
            last = {
                "api": api_status,
                "health": health,
                "frontend": web_status,
                "html_contains_ledgerflow": "LedgerFlow" in html,
                "html_start": html[:130],
            }
            if api_status == 200 and health.get("status") == "ok" and web_status == 200 and "LedgerFlow" in html:
                print("Frontend and backend reachable through Docker Compose", flush=True)
                return
        except (OSError, TimeoutError, ValueError) as error:
            last = repr(error)
        if attempt % 5 == 0:
            print(f"Readiness attempt {attempt + 1}: {last}", flush=True)
        time.sleep(2)
    raise AssertionError(f"Docker stack did not become ready; last observation: {last}")


def main():
    wait_for_stack()
    suffix = uuid.uuid4().hex[:12]
    sender_email = f"sender-{suffix}@example.com"
    recipient_email = f"recipient-{suffix}@example.com"
    password = "local-testing-password-only-123"
    for email in (sender_email, recipient_email):
        status, _ = request(API + "/auth/register", "POST", {"email": email, "password": password})
        assert status == 201, f"Registration failed: {status}"

    def login(email):
        status, response = request(API + "/auth/login", "POST", {"email": email, "password": password})
        assert status == 200, response
        return response["access_token"]

    sender = login(sender_email)
    recipient = login(recipient_email)
    status, credit = request(API + "/demo/credit", "POST", {}, sender)
    assert status == 200 and credit["credited_cents"] == 100_000, (status, credit)

    transfer = {"recipient_email": recipient_email, "amount_cents": 1250}
    key = "e2e-" + uuid.uuid4().hex
    status, result = request(API + "/transfers", "POST", transfer, sender, key)
    assert status == 200 and result["replayed"] is False, (status, result)
    status, replay = request(API + "/transfers", "POST", transfer, sender, key)
    assert status == 200 and replay["replayed"] is True, (status, replay)
    assert replay["transfer_id"] == result["transfer_id"]
    status, conflict = request(API + "/transfers", "POST", {**transfer, "amount_cents": 2500}, sender, key)
    assert status == 409, conflict

    status, sender_profile = request(API + "/me", token=sender)
    assert status == 200 and sender_profile["balance_cents"] == 98750, sender_profile
    status, recipient_profile = request(API + "/me", token=recipient)
    assert status == 200 and recipient_profile["balance_cents"] == 1250, recipient_profile
    status, sender_history = request(API + "/transfers", token=sender)
    assert status == 200 and len(sender_history) == 1 and sender_history[0]["direction"] == "sent"
    status, recipient_history = request(API + "/transfers", token=recipient)
    assert status == 200 and len(recipient_history) == 1 and recipient_history[0]["direction"] == "received"
    print("Docker end-to-end API and frontend smoke checks passed (simulated credits only)")


if __name__ == "__main__":
    main()
