"""
Unit tests for global exception handling in main.py.
Verifies that raw internal exceptions are sanitized to a generic message and never leaked to API clients.
"""

from fastapi.testclient import TestClient
from main import app


def test_global_exception_handler_sanitizes_error():
    # Dynamically mount a temporary route that raises a sensitive internal exception
    @app.get("/api/test-internal-error")
    async def trigger_internal_error():
        raise RuntimeError("psycopg2.OperationalError: password authentication failed for user 'postgres'")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/test-internal-error")
    assert resp.status_code == 500
    data = resp.json()
    assert data == {"detail": "Internal server error"}
    assert "password" not in resp.text
    assert "psycopg2" not in resp.text
    assert "RuntimeError" not in resp.text
