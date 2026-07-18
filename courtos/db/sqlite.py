import os
import json
import aiosqlite
from typing import List, Optional
from datetime import datetime, timezone
from courtos.models import TelemetryEvent, Incident, VideoRecord, VideoStatus
from courtos.db.adapter import DatabaseAdapter

class SqliteAdapter(DatabaseAdapter):
    def __init__(self, db_url: str):
        # Allow standard file paths (e.g. ./data/courtos.db)
        self.db_url = db_url

    async def initialize(self) -> None:
        # Create directory if it does not exist
        db_dir = os.path.dirname(self.db_url)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        async with aiosqlite.connect(self.db_url) as db:
            # Enable foreign keys and WAL mode
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute("PRAGMA journal_mode = WAL;")
            
            # Read and execute migrations
            migration_path = os.path.join(os.path.dirname(__file__), "migrations", "001_init.sql")
            with open(migration_path, "r") as f:
                schema_sql = f.read()
            
            # Executescript handles multiple commands separated by semicolons
            await db.executescript(schema_sql)
            await db.commit()

    async def store_event(self, event: TelemetryEvent) -> None:
        query = """
            INSERT INTO telemetry_events (event_id, event_type, timestamp, source, payload, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        payload_json = json.dumps(event.payload.model_dump())
        async with aiosqlite.connect(self.db_url) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute(query, (
                event.event_id,
                event.event_type,
                event.timestamp.isoformat(),
                event.source,
                payload_json,
                datetime.now(timezone.utc).isoformat()
            ))
            await db.commit()

    async def store_incident(self, incident: Incident) -> None:
        query = """
            INSERT INTO incidents (incident_id, severity, category, message, created_at, source_event_id, status, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        async with aiosqlite.connect(self.db_url) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute(query, (
                incident.incident_id,
                incident.severity,
                incident.category,
                incident.message,
                incident.created_at.isoformat(),
                incident.source_event_id,
                incident.status,
                incident.resolved_at.isoformat() if incident.resolved_at else None
            ))
            await db.commit()

    async def resolve_incident(self, incident_id: str, resolved_at: datetime) -> Optional[Incident]:
        update_query = """
            UPDATE incidents
            SET status = ?, resolved_at = ?
            WHERE incident_id = ?
        """
        select_query = """
            SELECT incident_id, severity, category, message, created_at, source_event_id, status, resolved_at
            FROM incidents
            WHERE incident_id = ?
        """
        async with aiosqlite.connect(self.db_url) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            async with db.execute(select_query, (incident_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
            
            await db.execute(update_query, ("resolved", resolved_at.isoformat(), incident_id))
            await db.commit()

            async with db.execute(select_query, (incident_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Incident(
                        incident_id=row[0],
                        severity=row[1],
                        category=row[2],
                        message=row[3],
                        created_at=datetime.fromisoformat(row[4]),
                        source_event_id=row[5],
                        status=row[6],
                        resolved_at=datetime.fromisoformat(row[7]) if row[7] else None
                    )
        return None

    async def write_audit(
        self, action: str, details: dict, actor: str = "system",
        source_event_id: Optional[str] = None, request_id: Optional[str] = None
    ) -> None:
        query = """
            INSERT INTO audit_log (log_id, action, actor, details, source_event_id, request_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        import uuid
        log_id = f"log-{uuid.uuid4()}"
        details_json = json.dumps(details)
        async with aiosqlite.connect(self.db_url) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute(query, (
                log_id,
                action,
                actor,
                details_json,
                source_event_id,
                request_id,
                datetime.now(timezone.utc).isoformat()
            ))
            await db.commit()

    async def store_snapshot(self, snapshot_id: str, state_json: str, trigger_event_id: Optional[str]) -> None:
        query = """
            INSERT INTO state_snapshots (snapshot_id, state, trigger_event_id, created_at)
            VALUES (?, ?, ?, ?)
        """
        async with aiosqlite.connect(self.db_url) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute(query, (
                snapshot_id,
                state_json,
                trigger_event_id,
                datetime.now(timezone.utc).isoformat()
            ))
            await db.commit()

    async def get_latest_snapshot(self) -> Optional[dict]:
        query = """
            SELECT state, trigger_event_id
            FROM state_snapshots
            ORDER BY created_at DESC
            LIMIT 1
        """
        async with aiosqlite.connect(self.db_url) as db:
            async with db.execute(query) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "state": row[0],
                        "trigger_event_id": row[1]
                    }
        return None

    async def get_events(self, limit: int = 100, offset: int = 0) -> List[TelemetryEvent]:
        query = """
            SELECT event_id, event_type, timestamp, source, payload
            FROM telemetry_events
            ORDER BY received_at DESC
            LIMIT ? OFFSET ?
        """
        events = []
        async with aiosqlite.connect(self.db_url) as db:
            async with db.execute(query, (limit, offset)) as cursor:
                async for row in cursor:
                    events.append(TelemetryEvent(
                        event_id=row[0],
                        event_type=row[1],
                        timestamp=datetime.fromisoformat(row[2]),
                        source=row[3],
                        payload=json.loads(row[4])
                    ))
        return events

    async def get_events_after(self, event_id: str) -> List[TelemetryEvent]:
        # First query received_at of trigger_event_id
        time_query = "SELECT received_at FROM telemetry_events WHERE event_id = ?"
        query = """
            SELECT event_id, event_type, timestamp, source, payload
            FROM telemetry_events
            WHERE received_at > ?
            ORDER BY received_at ASC
        """
        events = []
        async with aiosqlite.connect(self.db_url) as db:
            async with db.execute(time_query, (event_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return []
                received_at = row[0]
            
            async with db.execute(query, (received_at,)) as cursor:
                async for row in cursor:
                    events.append(TelemetryEvent(
                        event_id=row[0],
                        event_type=row[1],
                        timestamp=datetime.fromisoformat(row[2]),
                        source=row[3],
                        payload=json.loads(row[4])
                    ))
        return events

    async def get_incidents(self, status: Optional[str] = None) -> List[Incident]:
        if status:
            query = """
                SELECT incident_id, severity, category, message, created_at, source_event_id, status, resolved_at
                FROM incidents
                WHERE status = ?
                ORDER BY created_at DESC
            """
            params = (status,)
        else:
            query = """
                SELECT incident_id, severity, category, message, created_at, source_event_id, status, resolved_at
                FROM incidents
                ORDER BY created_at DESC
            """
            params = ()

        incidents = []
        async with aiosqlite.connect(self.db_url) as db:
            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    incidents.append(Incident(
                        incident_id=row[0],
                        severity=row[1],
                        category=row[2],
                        message=row[3],
                        created_at=datetime.fromisoformat(row[4]),
                        source_event_id=row[5],
                        status=row[6],
                        resolved_at=datetime.fromisoformat(row[7]) if row[7] else None
                    ))
        return incidents

    async def get_incident(self, incident_id: str) -> Optional[Incident]:
        query = """
            SELECT incident_id, severity, category, message, created_at, source_event_id, status, resolved_at
            FROM incidents
            WHERE incident_id = ?
        """
        async with aiosqlite.connect(self.db_url) as db:
            async with db.execute(query, (incident_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Incident(
                        incident_id=row[0],
                        severity=row[1],
                        category=row[2],
                        message=row[3],
                        created_at=datetime.fromisoformat(row[4]),
                        source_event_id=row[5],
                        status=row[6],
                        resolved_at=datetime.fromisoformat(row[7]) if row[7] else None
                    )
        return None

    async def get_audit_entries(self, limit: int = 50, offset: int = 0) -> List[dict]:
        query = """
            SELECT log_id, action, actor, details, source_event_id, request_id, created_at
            FROM audit_log
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        entries = []
        async with aiosqlite.connect(self.db_url) as db:
            async with db.execute(query, (limit, offset)) as cursor:
                async for row in cursor:
                    entries.append({
                        "log_id": row[0],
                        "action": row[1],
                        "actor": row[2],
                        "details": json.loads(row[3]),
                        "source_event_id": row[4],
                        "request_id": row[5],
                        "created_at": row[6]
                    })
        return entries


    async def store_video(self, video: VideoRecord) -> None:
        query = """
            INSERT INTO videos (video_id, filename, status, uploaded_at, completed_at)
            VALUES (?, ?, ?, ?, ?)
        """
        async with aiosqlite.connect(self.db_url) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute(query, (
                video.video_id,
                video.filename,
                video.status.value,
                video.uploaded_at.isoformat(),
                video.completed_at.isoformat() if video.completed_at else None
            ))
            await db.commit()

    async def get_videos(self) -> List[VideoRecord]:
        query = """
            SELECT video_id, filename, status, uploaded_at, completed_at
            FROM videos
            ORDER BY uploaded_at DESC
        """
        videos = []
        async with aiosqlite.connect(self.db_url) as db:
            async with db.execute(query) as cursor:
                async for row in cursor:
                    videos.append(VideoRecord(
                        video_id=row[0],
                        filename=row[1],
                        status=VideoStatus(row[2]),
                        uploaded_at=datetime.fromisoformat(row[3]),
                        completed_at=datetime.fromisoformat(row[4]) if row[4] else None
                    ))
        return videos

    async def update_video_status(self, video_id: str, status: VideoStatus, completed_at: Optional[datetime] = None) -> None:
        query = """
            UPDATE videos
            SET status = ?, completed_at = ?
            WHERE video_id = ?
        """
        async with aiosqlite.connect(self.db_url) as db:
            await db.execute(query, (
                status.value,
                completed_at.isoformat() if completed_at else None,
                video_id
            ))
            await db.commit()

    async def close(self) -> None:
        pass
