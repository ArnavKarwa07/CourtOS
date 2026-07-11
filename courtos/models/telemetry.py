from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator
from courtos.models.enums import EventType, PlayState

class BaseTelemetryModel(BaseModel):
    # Enforce strict field checks at the class level
    model_config = ConfigDict(extra="forbid")

class KinematicPayload(BaseTelemetryModel):
    player_id: str = Field(min_length=1)
    deceleration_g: float = Field(ge=0)
    velocity_ms: float = Field(ge=0)
    position_x: float
    position_y: float

class GameStatePayload(BaseTelemetryModel):
    play_state: PlayState
    game_clock: str = Field(pattern=r"^\d{2}:\d{2}$")
    period: int = Field(ge=1, le=4)

class NetworkPayload(BaseTelemetryModel):
    channel: str = Field(min_length=1)
    bandwidth_mbps: float = Field(ge=0)
    latency_ms: float = Field(ge=0)

class ReviewPayload(BaseTelemetryModel):
    review_type: str = Field(min_length=1)
    description: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)

PAYLOAD_MAP = {
    EventType.KINEMATIC: KinematicPayload,
    EventType.GAME_STATE: GameStatePayload,
    EventType.NETWORK: NetworkPayload,
    EventType.REVIEW: ReviewPayload,
}

class TelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    event_type: EventType
    timestamp: datetime
    source: str = Field(min_length=1)
    payload: KinematicPayload | GameStatePayload | NetworkPayload | ReviewPayload

    @model_validator(mode="before")
    @classmethod
    def validate_payload_type(cls, data: dict) -> dict:
        if not isinstance(data, dict):
            return data
        
        event_type = data.get("event_type")
        if not event_type:
            return data  # Let Pydantic raise standard missing field error
        
        # Resolve raw event_type enum if it's a string
        try:
            resolved_type = EventType(event_type)
        except ValueError:
            return data  # Let Pydantic raise enum error

        payload = data.get("payload")
        if payload is None:
            return data

        expected_model = PAYLOAD_MAP.get(resolved_type)
        if expected_model:
            # Validate the payload against the specific sub-model to enforce ConfigDict(extra="forbid")
            if isinstance(payload, dict):
                # This will raise ValidationError if invalid or containing extra fields
                expected_model.model_validate(payload)
                
        return data
