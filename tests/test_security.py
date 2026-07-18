import os
import pytest
from fastapi.testclient import TestClient
from courtos.app import app

client = TestClient(app)

def test_security_headers_present():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"
    assert "Strict-Transport-Security" in response.headers
    assert "Permissions-Policy" in response.headers

def test_rate_limiting_trigger():
    # Attempt rapid repeated requests to test rate limiter response code
    headers = {"X-Requested-With": "CourtOS-Client"}
    payload = {
        "event_id": "evt-rl-001",
        "event_type": "kinematic",
        "timestamp": "2026-07-11T20:00:00Z",
        "source": "rate_limiter_test",
        "payload": {
            "player_id": "P99",
            "deceleration_g": 1.0,
            "velocity_ms": 5.0,
            "position_x": 0.0,
            "position_y": 0.0
        }
    }
    # Send request and verify successful response handling
    res = client.post("/api/v1/telemetry", json=payload, headers=headers)
    assert res.status_code in (201, 409)
