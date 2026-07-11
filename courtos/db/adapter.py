from typing import Protocol, List, Optional
from datetime import datetime
from courtos.models import TelemetryEvent, Incident

class DatabaseAdapter(Protocol):
    async def initialize(self) -> None:
        """Initialize connection and create tables if needed."""
        ...

    async def store_event(self, event: TelemetryEvent) -> None:
        """Store a telemetry event."""
        ...

    async def store_incident(self, incident: Incident) -> None:
        """Store an incident."""
        ...

    async def resolve_incident(self, incident_id: str, resolved_at: datetime) -> Optional[Incident]:
        """Mark incident as resolved. Return the updated incident or None if not found."""
        ...

    async def write_audit(
        self, action: str, details: dict, actor: str = "system",
        source_event_id: Optional[str] = None, request_id: Optional[str] = None
    ) -> None:
        """Write an audit entry."""
        ...

    async def store_snapshot(self, snapshot_id: str, state_json: str, trigger_event_id: Optional[str]) -> None:
        """Store a state snapshot."""
        ...

    async def get_latest_snapshot(self) -> Optional[dict]:
        """Retrieve the latest snapshot row. Return dict with 'state' and 'trigger_event_id' or None."""
        ...

    async def get_events(self, limit: int = 100, offset: int = 0) -> List[TelemetryEvent]:
        """Fetch historical events."""
        ...

    async def get_events_after(self, event_id: str) -> List[TelemetryEvent]:
        """Fetch all events received after the specified event_id."""
        ...

    async def get_incidents(self, status: Optional[str] = None) -> List[Incident]:
        """Fetch incidents filtered by status."""
        ...

    async def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Fetch a specific incident by id."""
        ...

    async def get_audit_entries(self, limit: int = 50, offset: int = 0) -> List[dict]:
        """Fetch audit log entries."""
        ...

    async def close(self) -> None:
        """Close DB connections."""
        ...
