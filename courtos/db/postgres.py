import json
import asyncpg
from typing import List, Optional
from datetime import datetime, timezone
from courtos.models import TelemetryEvent, Incident
from courtos.db.adapter import DatabaseAdapter

class PostgresAdapter(DatabaseAdapter):
    """Service class.
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        self._pool: Optional[asyncpg.Pool] = None

    async def initialize(self) -> None:
        # Create connection pool
        self._pool = await asyncpg.create_pool(
            dsn=self.db_url,
            min_size=2,
            max_size=20
        )

    async def store_event(self, event: TelemetryEvent) -> None:
        query = """
            INSERT INTO telemetry_events (event_id, event_type, timestamp, source, payload, received_at)
            VALUES ($1, $2, $3, $4, $5, $6)
        """
        payload_json = json.dumps(event.payload.model_dump())
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                event.event_id,
                event.event_type,
                event.timestamp.replace(tzinfo=timezone.utc),
                event.source,
                payload_json,
                datetime.now(timezone.utc)
            )

    async def store_incident(self, incident: Incident) -> None:
        query = """
            INSERT INTO incidents (incident_id, severity, category, message, created_at, source_event_id, status, resolved_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                incident.incident_id,
                incident.severity,
                incident.category,
                incident.message,
                incident.created_at.replace(tzinfo=timezone.utc),
                incident.source_event_id,
                incident.status,
                incident.resolved_at.replace(tzinfo=timezone.utc) if incident.resolved_at else None
            )

    async def resolve_incident(self, incident_id: str, resolved_at: datetime) -> Optional[Incident]:
        update_query = """
            UPDATE incidents
            SET status = $1, resolved_at = $2
            WHERE incident_id = $3
        """
        select_query = """
            SELECT incident_id, severity, category, message, created_at, source_event_id, status, resolved_at
            FROM incidents
            WHERE incident_id = $1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(select_query, incident_id)
            if not row:
                return None
            
            await conn.execute(update_query, "resolved", resolved_at.replace(tzinfo=timezone.utc), incident_id)
            
            row = await conn.fetchrow(select_query, incident_id)
            if row:
                return Incident(
                    incident_id=row["incident_id"],
                    severity=row["severity"],
                    category=row["category"],
                    message=row["message"],
                    created_at=row["created_at"],
                    source_event_id=row["source_event_id"],
                    status=row["status"],
                    resolved_at=row["resolved_at"]
                )
        return None

    async def write_audit(
        self, action: str, details: dict, actor: str = "system",
        source_event_id: Optional[str] = None, request_id: Optional[str] = None
    ) -> None:
        query = """
            INSERT INTO audit_log (log_id, action, actor, details, source_event_id, request_id, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        import uuid
        log_id = f"log-{uuid.uuid4()}"
        details_json = json.dumps(details)
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                log_id,
                action,
                actor,
                details_json,
                source_event_id,
                request_id,
                datetime.now(timezone.utc)
            )

    async def store_snapshot(self, snapshot_id: str, state_json: str, trigger_event_id: Optional[str]) -> None:
        query = """
            INSERT INTO state_snapshots (snapshot_id, state, trigger_event_id, created_at)
            VALUES ($1, $2, $3, $4)
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                snapshot_id,
                state_json,
                trigger_event_id,
                datetime.now(timezone.utc)
            )

    async def get_latest_snapshot(self) -> Optional[dict]:
        query = """
            SELECT state, trigger_event_id
            FROM state_snapshots
            ORDER BY created_at DESC
            LIMIT 1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query)
            if row:
                # asyncpg returns json column as string or parsed dict depending on config.
                # We normalize it to string.
                state_val = row["state"]
                if not isinstance(state_val, str):
                    state_val = json.dumps(state_val)
                return {
                    "state": state_val,
                    "trigger_event_id": row["trigger_event_id"]
                }
        return None

    async def get_events(self, limit: int = 100, offset: int = 0) -> List[TelemetryEvent]:
        query = """
            SELECT event_id, event_type, timestamp, source, payload
            FROM telemetry_events
            ORDER BY received_at DESC
            LIMIT $1 OFFSET $2
        """
        events = []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, limit, offset)
            for row in rows:
                payload_val = row["payload"]
                if isinstance(payload_val, str):
                    payload_val = json.loads(payload_val)
                events.append(TelemetryEvent(
                    event_id=row["event_id"],
                    event_type=row["event_type"],
                    timestamp=row["timestamp"],
                    source=row["source"],
                    payload=payload_val
                ))
        return events

    async def get_events_after(self, event_id: str) -> List[TelemetryEvent]:
        time_query = "SELECT received_at FROM telemetry_events WHERE event_id = $1"
        query = """
            SELECT event_id, event_type, timestamp, source, payload
            FROM telemetry_events
            WHERE received_at > $1
            ORDER BY received_at ASC
        """
        events = []
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(time_query, event_id)
            if not row:
                return []
            received_at = row["received_at"]
            
            rows = await conn.fetch(query, received_at)
            for r in rows:
                payload_val = r["payload"]
                if isinstance(payload_val, str):
                    payload_val = json.loads(payload_val)
                events.append(TelemetryEvent(
                    event_id=r["event_id"],
                    event_type=r["event_type"],
                    timestamp=r["timestamp"],
                    source=r["source"],
                    payload=payload_val
                ))
        return events

    async def get_incidents(self, status: Optional[str] = None) -> List[Incident]:
        if status:
            query = """
                SELECT incident_id, severity, category, message, created_at, source_event_id, status, resolved_at
                FROM incidents
                WHERE status = $1
                ORDER BY created_at DESC
            """
            args = (status,)
        else:
            query = """
                SELECT incident_id, severity, category, message, created_at, source_event_id, status, resolved_at
                FROM incidents
                ORDER BY created_at DESC
            """
            args = ()

        incidents = []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            for r in rows:
                incidents.append(Incident(
                    incident_id=r["incident_id"],
                    severity=r["severity"],
                    category=r["category"],
                    message=r["message"],
                    created_at=r["created_at"],
                    source_event_id=r["source_event_id"],
                    status=r["status"],
                    resolved_at=r["resolved_at"]
                ))
        return incidents

    async def get_incident(self, incident_id: str) -> Optional[Incident]:
        query = """
            SELECT incident_id, severity, category, message, created_at, source_event_id, status, resolved_at
            FROM incidents
            WHERE incident_id = $1
        """
        async with self._pool.acquire() as conn:
            r = await conn.fetchrow(query, incident_id)
            if r:
                return Incident(
                    incident_id=r["incident_id"],
                    severity=r["severity"],
                    category=r["category"],
                    message=r["message"],
                    created_at=r["created_at"],
                    source_event_id=r["source_event_id"],
                    status=r["status"],
                    resolved_at=r["resolved_at"]
                )
        return None

    async def get_audit_entries(self, limit: int = 50, offset: int = 0) -> List[dict]:
        query = """
            SELECT log_id, action, actor, details, source_event_id, request_id, created_at
            FROM audit_log
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """
        entries = []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, limit, offset)
            for r in rows:
                details_val = r["details"]
                if isinstance(details_val, str):
                    details_val = json.loads(details_val)
                entries.append({
                    "log_id": r["log_id"],
                    "action": r["action"],
                    "actor": r["actor"],
                    "details": details_val,
                    "source_event_id": r["source_event_id"],
                    "request_id": r["request_id"],
                    "created_at": r["created_at"].isoformat()
                })
        return entries

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
