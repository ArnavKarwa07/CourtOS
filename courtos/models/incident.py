from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from courtos.models.enums import Severity, IncidentStatus
from courtos.models.sanitizers import sanitize_text

class Incident(BaseModel):

    incident_id: str = Field(min_length=1)
    severity: Severity
    category: str = Field(min_length=1)
    message: str = Field(min_length=1)
    created_at: datetime
    source_event_id: str = Field(min_length=1)
    status: IncidentStatus = IncidentStatus.ACTIVE
    resolved_at: datetime | None = None

    @field_validator('category', 'message', mode='before')
    @classmethod
    def sanitize(cls, v: str) -> str:
        return sanitize_text(v)
