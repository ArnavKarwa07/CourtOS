import uuid
from datetime import datetime, timezone
from typing import List
from courtos.models import TelemetryEvent, Incident
from courtos.models.enums import Severity, IncidentStatus
from courtos.models.telemetry import KinematicPayload

class KinematicService:
    def __init__(self, decel_warn: float, decel_crit: float, velocity_warn: float, velocity_crit: float):
        self.decel_warn = decel_warn
        self.decel_crit = decel_crit
        self.velocity_warn = velocity_warn
        self.velocity_crit = velocity_crit

    def evaluate(self, event: TelemetryEvent) -> List[Incident]:
        payload: KinematicPayload = event.payload
        incidents = []
        now = datetime.now(timezone.utc)

        # 1. Check deceleration
        if payload.deceleration_g > self.decel_crit:
            incidents.append(Incident(
                incident_id=f"inc-{uuid.uuid4()}",
                severity=Severity.CRITICAL,
                category="kinematic_threshold",
                message=f"Player {payload.player_id}: deceleration {payload.deceleration_g}g exceeds critical threshold ({self.decel_crit}g)",
                created_at=now,
                source_event_id=event.event_id,
                status=IncidentStatus.ACTIVE
            ))
        elif payload.deceleration_g > self.decel_warn:
            incidents.append(Incident(
                incident_id=f"inc-{uuid.uuid4()}",
                severity=Severity.WARNING,
                category="kinematic_threshold",
                message=f"Player {payload.player_id}: deceleration {payload.deceleration_g}g exceeds warning threshold ({self.decel_warn}g)",
                created_at=now,
                source_event_id=event.event_id,
                status=IncidentStatus.ACTIVE
            ))

        # 2. Check velocity
        if payload.velocity_ms > self.velocity_crit:
            incidents.append(Incident(
                incident_id=f"inc-{uuid.uuid4()}",
                severity=Severity.CRITICAL,
                category="kinematic_threshold",
                message=f"Player {payload.player_id}: velocity {payload.velocity_ms}m/s exceeds critical threshold ({self.velocity_crit}m/s)",
                created_at=now,
                source_event_id=event.event_id,
                status=IncidentStatus.ACTIVE
            ))
        elif payload.velocity_ms > self.velocity_warn:
            incidents.append(Incident(
                incident_id=f"inc-{uuid.uuid4()}",
                severity=Severity.WARNING,
                category="kinematic_threshold",
                message=f"Player {payload.player_id}: velocity {payload.velocity_ms}m/s exceeds warning threshold ({self.velocity_warn}m/s)",
                created_at=now,
                source_event_id=event.event_id,
                status=IncidentStatus.ACTIVE
            ))

        return incidents
