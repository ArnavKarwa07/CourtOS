from datetime import datetime
from pydantic import BaseModel, Field
from courtos.models.enums import Severity, IncidentStatus

class Incident(BaseModel):
    incident_id: str = Field(min_length=1)
    severity: Severity
    category: str = Field(min_length=1)
    message: str = Field(min_length=1)
    created_at: datetime
    source_event_id: str = Field(min_length=1)
    status: IncidentStatus = IncidentStatus.ACTIVE
    resolved_at: datetime | None = None
