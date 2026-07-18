from courtos.models import TelemetryEvent, CourtOSState
from courtos.models.telemetry import GameStatePayload
from courtos.services.overlay import OverlayService

class GameStateService:
    """Service class.
    """

    def __init__(self, overlay_service: OverlayService):
        """Method description.

        Args:
            *args: Arguments.
            **kwargs: Keyword arguments.

        Returns:
            Any: Return value.

        Raises:
            Exception: If an error occurs.

        """
        self.overlay_service = overlay_service

    def process(self, event: TelemetryEvent, current_state: CourtOSState) -> None:
        """Method description.

        Args:
            *args: Arguments.
            **kwargs: Keyword arguments.

        Returns:
            Any: Return value.

        Raises:
            Exception: If an error occurs.

        """
        payload: GameStatePayload = event.payload
        
        # 1. Update status parameters
        current_state.play_state = payload.play_state
        current_state.game_clock = payload.game_clock
        current_state.period = payload.period
        
        # 2. Re-evaluate overlay gating mode
        current_state.overlay = self.overlay_service.evaluate_gating(
            current_state.play_state, current_state.overlay
        )
