import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from courtos.models import CourtOSState, TelemetryEvent, Incident, NetworkAllocation, OverlayState
from courtos.models.enums import IncidentStatus
from courtos.db.adapter import DatabaseAdapter
from courtos.core.sse import SSEPublisher
from courtos.services.router import EventRouter
from courtos.services.network import NetworkPolicyService

class StateManager:
    def __init__(self, db: DatabaseAdapter, sse: SSEPublisher, router: EventRouter, network_service: NetworkPolicyService):
        self.db = db
        self.sse = sse
        self.router = router
        self.network_service = network_service
        self._lock = asyncio.Lock()
        self._state: CourtOSState = CourtOSState()

    async def initialize(self) -> None:
        """Startup: reconstruct the canonical state from snapshots and subsequent events."""
        async with self._lock:
            # 1. Fetch latest snapshot
            snapshot_row = await self.db.get_latest_snapshot()
            
            if snapshot_row:
                try:
                    self._state = CourtOSState.model_validate_json(snapshot_row["state"])
                    # 2. Replay subsequent events
                    recent_events = await self.db.get_events_after(snapshot_row["trigger_event_id"])
                except Exception:
                    # Fallback if snapshot deserialization fails
                    self._state = self._default_state()
                    recent_events = await self.db.get_events(limit=1000)
                    recent_events.reverse()  # Order ascending for replay
            else:
                self._state = self._default_state()
                recent_events = await self.db.get_events(limit=1000)
                recent_events.reverse()  # Order ascending for replay

            # 3. Apply events in memory (pure updates, no DB writes during initialize)
            for event in recent_events:
                self.router.route(event, self._state)

            # 4. Synchronize active incidents from DB directly to ensure correct status
            active_incidents = await self.db.get_incidents(status="active")
            self._state.active_incidents = active_incidents
            # Recalculate network policy on active incidents
            self._state.network_allocation = self.network_service.calculate_allocation(active_incidents)

    def get_state(self) -> CourtOSState:
        """Return the current canonical state."""
        return self._state

    async def process_event(self, event: TelemetryEvent) -> Tuple[int, List[Incident]]:
        """
        Ingest event, run rules, save state transactionally, and broadcast SSE.
        Returns: Tuple[incidents_created_count, list_of_new_incidents]
        """
        async with self._lock:
            # 1. Store the event first. If duplicate event_id, database PK constraint will raise.
            # We first verify event_id is not already present to return a clean 409
            events = await self.db.get_events(limit=100)
            if any(e.event_id == event.event_id for e in events):
                raise ValueError("DuplicateEvent")

            await self.db.store_event(event)

            # 2. Write audit log for event ingest
            await self.db.write_audit(
                action="event_ingested",
                details={"event_type": event.event_type, "source": event.source},
                actor=event.source,
                source_event_id=event.event_id
            )

            # 3. Clone current state, compute new state
            new_state = CourtOSState.model_validate(self._state.model_dump())
            new_incidents, state_updated = self.router.route(event, new_state)

            # 4. Write new incidents to database (if any)
            for incident in new_incidents:
                await self.db.store_incident(incident)
                await self.db.write_audit(
                    action="incident_created",
                    details={"incident_id": incident.incident_id, "severity": incident.severity},
                    source_event_id=event.event_id
                )

            # 5. Save state snapshot & update memory (only on state change)
            if state_updated:
                # Update timestamp
                new_state.updated_at = datetime.now(timezone.utc)
                
                state_json = new_state.model_dump_json()
                snapshot_id = f"snap-{uuid.uuid4()}"
                
                await self.db.store_snapshot(snapshot_id, state_json, event.event_id)
                await self.db.write_audit(
                    action="state_snapshot_created",
                    details={"snapshot_id": snapshot_id},
                    source_event_id=event.event_id
                )

                # Commit to memory
                self._state = new_state

                # 6. Broadcast SSE events
                # Broadcast state update
                state_data = json.loads(self._state.model_dump_json())
                await self.sse.broadcast("state_update", state_data)

                # Broadcast incident created details
                for incident in new_incidents:
                    inc_data = json.loads(incident.model_dump_json())
                    await self.sse.broadcast("incident_created", inc_data)

                # Broadcast overlay update if mode shifts
                await self.sse.broadcast("overlay_changed", {
                    "mode": self._state.overlay.mode,
                    "active_overlays": self._state.overlay.active_overlays
                })

            return len(new_incidents), new_incidents

    async def resolve_incident(self, incident_id: str, request_id: Optional[str] = None) -> Incident:
        """Resolve active incident and trigger network policy re-allocation."""
        async with self._lock:
            # 1. Update in database
            resolved = await self.db.resolve_incident(incident_id, datetime.now(timezone.utc))
            if not resolved:
                raise ValueError("NotFound")

            # 2. Write audit log
            await self.db.write_audit(
                action="incident_resolved",
                details={"incident_id": incident_id},
                actor="operator",
                request_id=request_id
            )

            # 3. Update active incidents and recompute network policy
            self._state.active_incidents = [
                i for i in self._state.active_incidents if i.incident_id != incident_id
            ]
            self._state.network_allocation = self.network_service.calculate_allocation(
                self._state.active_incidents
            )
            self._state.updated_at = datetime.now(timezone.utc)

            # 4. Store state snapshot
            state_json = self._state.model_dump_json()
            snapshot_id = f"snap-{uuid.uuid4()}"
            # Resolve incident action is trigger for state change
            await self.db.store_snapshot(snapshot_id, state_json, None)
            
            # 5. Broadcast SSE updates
            await self.sse.broadcast("incident_resolved", {
                "incident_id": incident_id,
                "resolved_at": resolved.resolved_at.isoformat() if resolved.resolved_at else None
            })
            await self.sse.broadcast("state_update", json.loads(state_json))
            
            return resolved

    async def force_network_recalculate(self, request_id: Optional[str] = None) -> NetworkAllocation:
        """Manually trigger network allocation update and broadcast."""
        async with self._lock:
            self._state.network_allocation = self.network_service.calculate_allocation(
                self._state.active_incidents
            )
            self._state.updated_at = datetime.now(timezone.utc)

            # Write audit log
            await self.db.write_audit(
                action="network_recalculated",
                details={"trigger": "manual"},
                actor="operator",
                request_id=request_id
            )

            # Save state snapshot
            state_json = self._state.model_dump_json()
            snapshot_id = f"snap-{uuid.uuid4()}"
            await self.db.store_snapshot(snapshot_id, state_json, None)

            # Broadcast updates
            await self.sse.broadcast("state_update", json.loads(state_json))
            return self._state.network_allocation

    async def update_overlay_state(self, action: str, overlay_id: str, request_id: Optional[str] = None) -> OverlayState:
        """Add, remove, or clear overlays on dynamic gating screen."""
        async with self._lock:
            # Gating check: cannot add overlays during live play
            if action == "add" and self._state.play_state == "live":
                raise ValueError("OverlayBlocked")

            err = None
            if action == "add":
                new_overlay, err = self.router.game_state_service.overlay_service.add_overlay(
                    self._state.overlay, overlay_id, self._state.play_state
                )
            elif action == "remove":
                new_overlay, err = self.router.game_state_service.overlay_service.remove_overlay(
                    self._state.overlay, overlay_id
                )
            elif action == "clear":
                new_overlay = OverlayState(mode=self._state.overlay.mode, active_overlays=[])
            else:
                raise ValueError("InvalidAction")

            if err:
                raise ValueError(err)  # will raise overlay remove not found

            self._state.overlay = new_overlay
            self._state.updated_at = datetime.now(timezone.utc)

            # Write audit log
            await self.db.write_audit(
                action="overlay_state_change",
                details={"action": action, "overlay_id": overlay_id},
                actor="operator",
                request_id=request_id
            )

            # Save state snapshot
            state_json = self._state.model_dump_json()
            snapshot_id = f"snap-{uuid.uuid4()}"
            await self.db.store_snapshot(snapshot_id, state_json, None)

            # Broadcast updates
            await self.sse.broadcast("overlay_changed", {
                "mode": self._state.overlay.mode,
                "active_overlays": self._state.overlay.active_overlays
            })
            await self.sse.broadcast("state_update", json.loads(state_json))

            return self._state.overlay

    def _default_state(self) -> CourtOSState:
        return CourtOSState(
            game_clock="00:00",
            period=1,
            network_allocation=NetworkAllocation(broadcast=40, telemetry=30, operations=20, emergency=10),
            overlay=OverlayState(mode="dynamic", active_overlays=[])
        )
