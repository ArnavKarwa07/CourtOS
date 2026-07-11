import os

# Ensure SQLite test DB URL - Set before imports
os.environ["COURTOS_DB_BACKEND"] = "sqlite"
os.environ["COURTOS_DB_URL"] = "./data/courtos_test.db"

from fastapi.testclient import TestClient
from courtos.app import app

client = TestClient(app)

def setup_function():
    import sqlite3
    db_path = "./data/courtos_test.db"
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        for table in ("audit_log", "state_snapshots", "incidents", "telemetry_events"):
            if table in tables:
                cursor.execute(f"DROP TABLE {table};")
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

def test_health():
    # Make sure app is started to trigger DB initialize
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["mode"] == "simulation"
        assert data["db_backend"] == "sqlite"

def test_ingest_kinematic_valid():
    with TestClient(app) as test_client:
        payload = {
            "event_id": "evt-001",
            "event_type": "kinematic",
            "timestamp": "2026-07-11T20:00:00Z",
            "source": "sensor-01",
            "payload": {
                "player_id": "P10",
                "deceleration_g": 4.5,
                "velocity_ms": 10.2,
                "position_x": 12.5,
                "position_y": 6.8
            }
        }
        headers = {"X-Requested-With": "CourtOS-Client"}
        response = test_client.post("/api/v1/telemetry", json=payload, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["event_id"] == "evt-001"
        assert data["state_updated"] is True

def test_ingest_invalid_payload():
    with TestClient(app) as test_client:
        payload = {
            "event_id": "evt-002",
            "event_type": "kinematic",
            "timestamp": "2026-07-11T20:00:00Z",
            "source": "sensor-01",
            "payload": {
                "player_id": "P10",
                "deceleration_g": -1.0,  # Invalid: deceleration_g >= 0
                "velocity_ms": 10.2,
                "position_x": 12.5,
                "position_y": 6.8
            }
        }
        headers = {"X-Requested-With": "CourtOS-Client"}
        response = test_client.post("/api/v1/telemetry", json=payload, headers=headers)
        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "validation_error"
        assert any("payload.deceleration_g" in d["field"] for d in data["details"])

def test_ingest_extra_fields():
    with TestClient(app) as test_client:
        payload = {
            "event_id": "evt-003",
            "event_type": "kinematic",
            "timestamp": "2026-07-11T20:00:00Z",
            "source": "sensor-01",
            "payload": {
                "player_id": "P10",
                "deceleration_g": 4.5,
                "velocity_ms": 10.2,
                "position_x": 12.5,
                "position_y": 6.8,
                "extra_field": "not_allowed"  # ConfigDict extra=forbid
            }
        }
        headers = {"X-Requested-With": "CourtOS-Client"}
        response = test_client.post("/api/v1/telemetry", json=payload, headers=headers)
        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "validation_error"
        assert any("extra_field" in d["message"] or "extra_field" in d["field"] for d in data["details"])

def test_ingest_duplicate():
    with TestClient(app) as test_client:
        payload = {
            "event_id": "evt-004",
            "event_type": "network",
            "timestamp": "2026-07-11T20:00:00Z",
            "source": "simulation",
            "payload": {
                "channel": "telemetry",
                "bandwidth_mbps": 10.0,
                "latency_ms": 5.0
            }
        }
        headers = {"X-Requested-With": "CourtOS-Client"}
        # First ingest succeeds
        response1 = test_client.post("/api/v1/telemetry", json=payload, headers=headers)
        assert response1.status_code == 201
        
        # Second ingest of duplicate fails with 409
        response2 = test_client.post("/api/v1/telemetry", json=payload, headers=headers)
        assert response2.status_code == 409
        data = response2.json()
        assert data["error"] == "duplicate_event"
        assert "already exists" in data["message"]
