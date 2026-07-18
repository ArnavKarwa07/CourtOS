from typing import Optional
from courtos.models import OverlayState
from courtos.models.enums import PlayState

class OverlayService:
    """Service class.
    """

    def evaluate_gating(self, play_state: PlayState, current_overlay: OverlayState) -> OverlayState:
        """Method description.

        Args:
            *args: Arguments.
            **kwargs: Keyword arguments.

        Returns:
            Any: Return value.

        Raises:
            Exception: If an error occurs.

        """
        if play_state == PlayState.LIVE:
            return OverlayState(
                mode="static",
                active_overlays=[]
            )
        else:
            return OverlayState(
                mode="dynamic",
                active_overlays=current_overlay.active_overlays
            )

    def add_overlay(self, current_overlay: OverlayState, overlay_id: str, play_state: PlayState) -> tuple[OverlayState, Optional[str]]:
        """Add an overlay. Return updated OverlayState and error string if any.
        """
        if play_state == PlayState.LIVE:
            return current_overlay, "Cannot add overlays during live play"
        
        if overlay_id in current_overlay.active_overlays:
            return current_overlay, None  # Idempotent add
        
        new_active = list(current_overlay.active_overlays) + [overlay_id]
        return OverlayState(mode="dynamic", active_overlays=new_active), None

    def remove_overlay(self, current_overlay: OverlayState, overlay_id: str) -> tuple[OverlayState, Optional[str]]:
        """Remove an overlay. Return updated OverlayState and error string if any.
        """
        if overlay_id not in current_overlay.active_overlays:
            return current_overlay, f"Overlay {overlay_id} is not active"
        
        new_active = [o for o in current_overlay.active_overlays if o != overlay_id]
        return OverlayState(mode=current_overlay.mode, active_overlays=new_active), None
