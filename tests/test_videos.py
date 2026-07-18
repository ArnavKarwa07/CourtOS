import os

os.environ["COURTOS_DB_BACKEND"] = "sqlite"
os.environ["COURTOS_DB_URL"] = "./data/courtos_test.db"

from fastapi.testclient import TestClient
from courtos.app import app

def setup_function():
    import sqlite3
    db_path = "./data/courtos_test.db"
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        for table in ("audit_log", "state_snapshots", "incidents", "telemetry_events", "videos"):
            if table in tables:
                cursor.execute(f"DROP TABLE {table};")
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

def test_videos_endpoints():
    with TestClient(app) as test_client:
        headers = {"X-Requested-With": "CourtOS-Client"}
        
        # Test GET /api/v1/videos (should be empty initially)
        response = test_client.get("/api/v1/videos", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"videos": []}
        
        # Test POST /api/v1/videos/upload
        files = {"file": ("test_video.mp4", b"dummy video content", "video/mp4")}
        response = test_client.post("/api/v1/videos/upload", headers=headers, files=files)
        assert response.status_code == 200
        data = response.json()
        assert "video_id" in data
        assert data["status"] == "processing"
        
        # Test GET /api/v1/videos (should contain the uploaded video)
        response = test_client.get("/api/v1/videos", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["videos"]) == 1
        assert data["videos"][0]["filename"] == "test_video.mp4"
        assert data["videos"][0]["status"] in ["processing", "completed"]
