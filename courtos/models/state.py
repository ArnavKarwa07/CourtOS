from datetime import datetime, timezone
from pydantic import BaseModel, Field
from courtos.models.enums import PlayState
from courtos.models.incident import Incident

class NetworkAllocation(BaseModel):
    """Class description.\n"""

    broadcast: float = Field(ge=0, le=100)
    telemetry: float = Field(ge=0, le=100)
    operations: float = Field(ge=0, le=100)
    emergency: float = Field(ge=0, le=100)
    simulated: bool = True

class OverlayState(BaseModel):
    """Class description.\n"""

    mode: str = "dynamic"  # "static" or "dynamic"
    active_overlays: list[str] = Field(default_factory=list)

class CourtOSState(BaseModel):
    """Class description.\n"""

    game_clock: str = "00:00"
    period: int = 1
    play_state: PlayState = PlayState.PRE_GAME
    network_allocation: NetworkAllocation = Field(
        default_factory=lambda: NetworkAllocation(broadcast=40, telemetry=30, operations=20, emergency=10)
    )
    overlay: OverlayState = Field(default_factory=OverlayState)
    active_incidents: list[Incident] = Field(default_factory=list)
    last_event_id: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
