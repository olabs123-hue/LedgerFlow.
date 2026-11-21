"""Small SQLite smoke tests. PostgreSQL concurrency tests are still required."""
import os
from pathlib import Path

os.environ['DATABASE_URL'] = 'sqlite+pysqlite:///./ledgerflow_test.sqlite'
os.environ['JWT_SECRET'] = 'integration-test-secret-string-32-bytes-minimum-only'
os.environ['DEMO_MODE'] = 'true'

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.main import app, Base, engine, SessionLocal, Entry


def test_registration_transfer_and_idempotency():
    Base.metadata.drop_all(engine)
    with TestClient(app) as client:
        for email in ['alice@example.com', 'bob@example.com']:
            response = client.post('/auth/register', json={'email': email, 'password': 'password_12345'})
            assert response.status_code == 201, response.text
        alice = client.post('/auth/login', json={'email': 'alice@example.com', 'password': 'password_12345'})
        assert alice.status_code == 200
        token = alice.json()['access_token']
        headers = {'Authorization': f'Bearer {token}', 'Idempotency-Key': 'abc-unique-123'}
        assert client.post('/demo/credit', headers={'Authorization': f'Bearer {token}'}).status_code == 200
        body = {'recipient_email': 'bob@example.com', 'amount_cents': 2500}
        transfer = client.post('/transfers', json=body, headers=headers)
        assert transfer.status_code == 200, transfer.text
        assert transfer.json()['replayed'] is False
        replay = client.post('/transfers', json=body, headers=headers)
        assert replay.status_code == 200, replay.text
        assert replay.json()['replayed'] is True
        changed = client.post('/transfers', json={**body, 'amount_cents': 3500}, headers=headers)
        assert changed.status_code == 409
        overdraft = client.post('/transfers', json={**body, 'amount_cents': 200000}, headers={**headers, 'Idempotency-Key': 'another-key-1234'})
        assert overdraft.status_code == 400
        assert client.get('/transfers').status_code in (401, 403)
        assert client.get('/me', headers=headers).json()['balance_cents'] == 97500
        bob = client.post('/auth/login', json={'email': 'bob@example.com', 'password': 'password_12345'}).json()['access_token']
        assert client.get('/me', headers={'Authorization': f'Bearer {bob}'}).json()['balance_cents'] == 2500
        with SessionLocal() as db:
            assert db.scalar(select(func.sum(Entry.delta_cents))) == 0
            assert db.scalar(select(func.count()).select_from(Entry)) == 2
    Base.metadata.drop_all(engine)
    # Keep the SQLite file until all pooled connections are released at process exit.


def test_authentication_and_validation():
    Base.metadata.drop_all(engine)
    with TestClient(app) as client:
        assert client.get('/health').json()['simulation'] is True
        assert client.post('/auth/register', json={'email': 'test@example.com', 'password': 'secure-password-123'}).status_code == 201
        assert client.post('/auth/register', json={'email': 'test@example.com', 'password': 'secure-password-123'}).status_code == 409
        assert client.post('/auth/login', json={'email': 'test@example.com', 'password': 'incorrect-password'}).status_code == 401
        assert client.get('/me', headers={'Authorization': 'Bearer invalid'}).status_code == 401
        token = client.post('/auth/login', json={'email':'test@example.com','password':'secure-password-123'}).json()['access_token']
        headers = {'Authorization': f'Bearer {token}', 'Idempotency-Key': 'unique-12345'}
        assert client.post('/transfers', json={'recipient_email':'test@example.com','amount_cents':100}, headers=headers).status_code == 400
        assert client.post('/transfers', json={'recipient_email':'nobody@example.com','amount_cents':100}, headers=headers).status_code == 404
    Base.metadata.drop_all(engine)
    # Keep the SQLite file until all pooled connections are released at process exit.


def test_failed_login_throttling_and_reset():
    Base.metadata.drop_all(engine)
    with TestClient(app) as client:
        email = 'limited@example.com'
        password = 'correct-password-123'
        assert client.post('/auth/register', json={'email':email, 'password':password}).status_code == 201
        for _ in range(5):
            result = client.post('/auth/login', json={'email':email, 'password':'wrong-password-123'})
            assert result.status_code == 401, result.text
        locked = client.post('/auth/login', json={'email':email, 'password':password})
        assert locked.status_code == 429, locked.text
        assert int(locked.headers['Retry-After']) > 0
        # Simulate window expiration without sleeping in the test.
        from sqlalchemy import update
        from app.main import LoginAttempt
        with SessionLocal() as db:
            db.execute(update(LoginAttempt).values(last_failure_epoch=0))
            db.commit()
        assert client.post('/auth/login', json={'email':email, 'password':password}).status_code == 200
        with SessionLocal() as db:
            from sqlalchemy import func
            assert db.scalar(select(func.count()).select_from(LoginAttempt)) == 0
    Base.metadata.drop_all(engine)
