from typing import List, Tuple
from courtos.models import TelemetryEvent, CourtOSState, Incident
from courtos.models.enums import EventType
from courtos.services.kinematic import KinematicService
from courtos.services.game_state import GameStateService
from courtos.services.network import NetworkPolicyService

class EventRouter:
    def __init__(
        self,
        kinematic_service: KinematicService,
        game_state_service: GameStateService,
        network_service: NetworkPolicyService
    ):
        self.kinematic_service = kinematic_service
        self.game_state_service = game_state_service
        self.network_service = network_service

    def route(self, event: TelemetryEvent, current_state: CourtOSState) -> Tuple[List[Incident], bool]:
        """
        Route telemetry event to appropriate service.
        Returns: Tuple[List[Incident], state_updated_bool]
        """
        state_updated = False
        new_incidents: List[Incident] = []

        if event.event_type == EventType.KINEMATIC:
            # 1. Evaluate kinematics
            new_incidents = self.kinematic_service.evaluate(event)
            if new_incidents:
                # Add to active incidents list
                current_state.active_incidents.extend(new_incidents)
                # Recalculate network policy allocation
                current_state.network_allocation = self.network_service.calculate_allocation(
                    current_state.active_incidents
                )
                state_updated = True
            
            # Kinematic events don't update main clock, but update last_event_id
            current_state.last_event_id = event.event_id
            current_state.updated_at = event.timestamp
            # In all cases, event ingestion updates at least last_event_id
            state_updated = True

        elif event.event_type == EventType.GAME_STATE:
            # 1. Process game state ticks/changes
            self.game_state_service.process(event, current_state)
            current_state.last_event_id = event.event_id
            current_state.updated_at = event.timestamp
            state_updated = True

        elif event.event_type == EventType.NETWORK:
            # Stored for telemetry feed & monitoring, no direct canonical state mutation in MVP
            current_state.last_event_id = event.event_id
            current_state.updated_at = event.timestamp
            state_updated = True

        elif event.event_type == EventType.REVIEW:
            # Stored for audit and feed, no direct canonical state mutation in MVP
            current_state.last_event_id = event.event_id
            current_state.updated_at = event.timestamp
            state_updated = True

        return new_incidents, state_updated
