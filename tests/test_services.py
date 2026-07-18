import pytest
from datetime import datetime, timezone
from courtos.models import TelemetryEvent, OverlayState, Incident, CourtOSState, NetworkAllocation
from courtos.models.enums import EventType, PlayState, Severity, IncidentStatus
from courtos.services import KinematicService, OverlayService, NetworkPolicyService, GameStateService, EventRouter

def test_kinematic_service_boundaries():
    service = KinematicService(decel_warn=5.0, decel_crit=9.0, velocity_warn=12.0, velocity_crit=18.0)
    
    # Deceleration breaching warning (> 5.0)
    event_warn = TelemetryEvent(
        event_id="evt-bound-1",
        event_type=EventType.KINEMATIC,
        timestamp=datetime.now(timezone.utc),
        source="sensor-01",
        payload={"player_id": "P1", "deceleration_g": 5.5, "velocity_ms": 10.0, "position_x": 0.0, "position_y": 0.0}
    )
    incidents = service.evaluate(event_warn)
    assert len(incidents) == 1
    assert incidents[0].severity == Severity.WARNING

    # Deceleration breaching critical (> 9.0)
    event_crit = TelemetryEvent(
        event_id="evt-bound-2",
        event_type=EventType.KINEMATIC,
        timestamp=datetime.now(timezone.utc),
        source="sensor-01",
        payload={"player_id": "P1", "deceleration_g": 9.5, "velocity_ms": 10.0, "position_x": 0.0, "position_y": 0.0}
    )
    incidents = service.evaluate(event_crit)
    assert len(incidents) == 1
    assert incidents[0].severity == Severity.CRITICAL

    # Velocity breach warning (15.0 > 12.0)
    event_vel_warn = TelemetryEvent(
        event_id="evt-bound-3",
        event_type=EventType.KINEMATIC,
        timestamp=datetime.now(timezone.utc),
        source="sensor-01",
        payload={"player_id": "P1", "deceleration_g": 2.0, "velocity_ms": 15.0, "position_x": 0.0, "position_y": 0.0}
    )
    incidents = service.evaluate(event_vel_warn)
    assert len(incidents) == 1
    assert incidents[0].severity == Severity.WARNING

def test_overlay_service_manipulation():
    service = OverlayService()
    current = OverlayState(mode="dynamic", active_overlays=["ov1", "ov2"])

    # Remove overlay during dynamic play
    updated, err = service.remove_overlay(current, "ov1")
    assert err is None
    assert updated.active_overlays == ["ov2"]

    # Try removing non-existent overlay
    _, err_none = service.remove_overlay(current, "non_existent")
    assert err_none is not None

def test_game_state_service_transitions():
    overlay_service = OverlayService()
    game_state_service = GameStateService(overlay_service)
    
    current_state = CourtOSState(
        play_state=PlayState.DEAD_BALL,
        game_clock="10:00",
        period=1,
        active_incidents=[],
        network_allocation=NetworkAllocation(broadcast=40.0, telemetry=30.0, operations=20.0, emergency=10.0),
        overlay=OverlayState(mode="dynamic", active_overlays=["marker_1"])
    )
    
    event = TelemetryEvent(
        event_id="evt-gs1",
        event_type=EventType.GAME_STATE,
        timestamp=datetime.now(timezone.utc),
        source="referee",
        payload={"play_state": PlayState.LIVE, "game_clock": "09:55", "period": 1}
    )

    # Process play state change to LIVE (clears overlays)
    game_state_service.process(event, current_state)
    assert current_state.play_state == PlayState.LIVE
    assert current_state.overlay.mode == "static"
    assert len(current_state.overlay.active_overlays) == 0

def test_event_router():
    kinematic = KinematicService(decel_warn=5.0, decel_crit=9.0, velocity_warn=12.0, velocity_crit=18.0)
    overlay = OverlayService()
    game_state = GameStateService(overlay)
    network = NetworkPolicyService()
    router = EventRouter(kinematic, game_state, network)

    current_state = CourtOSState(
        play_state=PlayState.LIVE,
        game_clock="08:00",
        period=2,
        active_incidents=[],
        network_allocation=NetworkAllocation(broadcast=40.0, telemetry=30.0, operations=20.0, emergency=10.0),
        overlay=OverlayState(mode="static", active_overlays=[])
    )

    event = TelemetryEvent(
        event_id="evt-r1",
        event_type=EventType.KINEMATIC,
        timestamp=datetime.now(timezone.utc),
        source="sensor-01",
        payload={"player_id": "P1", "deceleration_g": 10.0, "velocity_ms": 5.0, "position_x": 0.0, "position_y": 0.0}
    )

    incidents, state_updated = router.route(event, current_state)
    assert state_updated is True
    assert len(incidents) == 1
    assert incidents[0].severity == Severity.CRITICAL
