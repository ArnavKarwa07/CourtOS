import os

# Ensure SQLite is used during integration testing - Set before imports
os.environ["COURTOS_DB_BACKEND"] = "sqlite"
os.environ["COURTOS_DB_URL"] = "./data/courtos_test.db"

from fastapi.testclient import TestClient
from courtos.app import app, db_adapter, state_manager

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

def test_health_check_db_integration():
    # Make sure app is started and DB works
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

def test_telemetry_flow_incident_generation_and_resolution():
    with TestClient(app) as test_client:
        # 1. Ingest event that breaches critical decel threshold (>9.0g)
        event_payload = {
            "event_id": "evt-crit-001",
            "event_type": "kinematic",
            "timestamp": "2026-07-11T20:00:00Z",
            "source": "sensor-01",
            "payload": {
                "player_id": "P24",
                "deceleration_g": 11.5,  # Critical breach (>9.0)
                "velocity_ms": 10.0,
                "position_x": 1.0,
                "position_y": 2.0
            }
        }
        
        # Must include the X-Requested-With header to bypass CSRF shield middleware
        headers = {"X-Requested-With": "CourtOS-Client"}
        
        response = test_client.post("/api/v1/telemetry", json=event_payload, headers=headers)
        assert response.status_code == 201
        res_data = response.json()
        assert res_data["incidents_created"] == 1
        assert len(res_data["incidents"]) == 1
        incident_id = res_data["incidents"][0]["incident_id"]
        
        # 2. Get state and verify active critical incident exists & network is in emergency mode
        response_state = test_client.get("/api/v1/state")
        assert response_state.status_code == 200
        state_data = response_state.json()
        assert len(state_data["active_incidents"]) == 1
        assert state_data["network_allocation"]["emergency"] == 50.0 # Emergency allocation
        
        # 3. Resolve the critical incident
        response_res = test_client.post(
            f"/api/v1/incidents/{incident_id}/resolve",
            headers=headers
        )
        assert response_res.status_code == 200
        assert response_res.json()["status"] == "resolved"
        
        # 4. Verify state network allocation has reverted to normal (10.0)
        response_state2 = test_client.get("/api/v1/state")
        assert response_state2.json()["network_allocation"]["emergency"] == 10.0

def test_csrf_middleware_protection():
    with TestClient(app) as test_client:
        # Submit POST without correct header
        event_payload = {
            "event_id": "evt-csrf-001",
            "event_type": "network",
            "timestamp": "2026-07-11T20:00:00Z",
            "source": "test",
            "payload": {
                "channel": "telemetry",
                "bandwidth_mbps": 10.0,
                "latency_ms": 1.0
            }
        }
        # Missing X-Requested-With header
        response = test_client.post("/api/v1/telemetry", json=event_payload)
        assert response.status_code == 403
        assert response.json()["error"] == "CSRF protection triggered"
