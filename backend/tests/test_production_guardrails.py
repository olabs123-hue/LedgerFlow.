"""Production configuration guard tests run without connecting to a production database."""
import os
import subprocess
import sys


def check_import(overrides):
    env = os.environ.copy()
    env.update({
        "APP_ENV": "production",
        "JWT_SECRET": "x" * 64,
        "FRONTEND_ORIGIN": "https://demo.example.org",
        "DATABASE_URL": "postgresql+psycopg://unused:unused@localhost:5432/unused",
        "DEMO_MODE": "false",
    })
    env.update(overrides)
    return subprocess.run(
        [sys.executable, "-c", "import app.main"],
        capture_output=True, text=True, env=env, timeout=20
    )


def test_production_rejects_demo_funding():
    result = check_import({"DEMO_MODE": "true"})
    assert result.returncode != 0
    assert "DEMO_MODE cannot be enabled" in result.stderr


def test_production_rejects_short_jwt_secret():
    result = check_import({"JWT_SECRET": "short-but-longer-than-32-characters"})
    assert result.returncode != 0
    assert "48+" in result.stderr


def test_production_rejects_http_origin():
    result = check_import({"FRONTEND_ORIGIN": "http://example.org"})
    assert result.returncode != 0
    assert "HTTPS" in result.stderr


def test_production_rejects_sqlite():
    result = check_import({"DATABASE_URL": "sqlite+pysqlite:///./dummy.db"})
    assert result.returncode != 0
    assert "requires PostgreSQL" in result.stderr


def test_valid_production_configuration_imports():
    result = check_import({})
    assert result.returncode == 0, result.stderr
