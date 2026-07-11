import uuid
from datetime import datetime, timezone
from courtos.models import TelemetryEvent, OverlayState, Incident
from courtos.models.enums import EventType, PlayState, Severity, IncidentStatus
from courtos.services import KinematicService, OverlayService, NetworkPolicyService

def test_kinematic_thresholds():
    service = KinematicService(decel_warn=5.0, decel_crit=9.0, velocity_warn=12.0, velocity_crit=18.0)
    
    # 1. No incident
    event = TelemetryEvent(
        event_id="evt-k1",
        event_type=EventType.KINEMATIC,
        timestamp=datetime.now(timezone.utc),
        source="test",
        payload={"player_id": "P1", "deceleration_g": 3.0, "velocity_ms": 10.0, "position_x": 0.0, "position_y": 0.0}
    )
    incidents = service.evaluate(event)
    assert len(incidents) == 0
    
    # 2. Warning incident decel
    event.payload.deceleration_g = 6.0
    incidents = service.evaluate(event)
    assert len(incidents) == 1
    assert incidents[0].severity == Severity.WARNING
    assert "exceeds warning threshold" in incidents[0].message
    
    # 3. Critical incident decel
    event.payload.deceleration_g = 10.0
    incidents = service.evaluate(event)
    assert len(incidents) == 1
    assert incidents[0].severity == Severity.CRITICAL
    assert "exceeds critical threshold" in incidents[0].message

def test_overlay_gating():
    service = OverlayService()
    current = OverlayState(mode="dynamic", active_overlays=["marker1"])
    
    # 1. Gating live state clears overlays and locks
    updated = service.evaluate_gating(PlayState.LIVE, current)
    assert updated.mode == "static"
    assert len(updated.active_overlays) == 0
    
    # 2. Gating non-live state stays dynamic
    updated_dead = service.evaluate_gating(PlayState.DEAD_BALL, current)
    assert updated_dead.mode == "dynamic"
    assert updated_dead.active_overlays == ["marker1"]
    
    # 3. Add overlay blocked during live play
    _, err = service.add_overlay(current, "marker2", PlayState.LIVE)
    assert err is not None
    
    # 4. Add overlay works during dead ball
    new_state, err = service.add_overlay(current, "marker2", PlayState.DEAD_BALL)
    assert err is None
    assert new_state.active_overlays == ["marker1", "marker2"]

def test_network_policy_allocation():
    service = NetworkPolicyService()
    
    # 1. Default allocation
    alloc = service.calculate_allocation([])
    assert alloc.broadcast == 40.0
    assert alloc.emergency == 10.0
    
    # 2. Emergency allocation when critical incident active
    critical_incident = Incident(
        incident_id="inc-1",
        severity=Severity.CRITICAL,
        category="test",
        message="Critical breach",
        created_at=datetime.now(timezone.utc),
        source_event_id="evt-1",
        status=IncidentStatus.ACTIVE
    )
    alloc_crit = service.calculate_allocation([critical_incident])
    assert alloc_crit.broadcast == 20.0
    assert alloc_crit.emergency == 50.0
    
    # 3. Resolved critical incident reverts to default allocation
    critical_incident.status = IncidentStatus.RESOLVED
    alloc_resolved = service.calculate_allocation([critical_incident])
    assert alloc_resolved.broadcast == 40.0
    assert alloc_resolved.emergency == 10.0
