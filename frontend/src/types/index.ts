export type Severity = "info" | "warning" | "critical";
export type IncidentStatus = "active" | "resolved";

export interface Incident {
  incident_id: string;
  severity: Severity;
  category: string;
  message: string;
  created_at: string;
  source_event_id: string;
  status: IncidentStatus;
  resolved_at: string | null;
}

export interface NetworkAllocation {
  broadcast: number;
  telemetry: number;
  operations: number;
  emergency: number;
  simulated: boolean;
}

export interface OverlayState {
  mode: string;
  active_overlays: string[];
}

export interface CourtOSState {
  game_clock: string;
  period: number;
  play_state: string;
  network_allocation: NetworkAllocation;
  overlay: OverlayState;
  active_incidents: Incident[];
  last_event_id: string | null;
  updated_at: string;
}

export interface TelemetryEvent {
  event_id: string;
  event_type: string;
  timestamp: string;
  source: string;
  payload: Record<string, unknown>;
}

export interface Toast {
  id: string;
  type: "success" | "error" | "info";
  message: string;
}

export interface ReducerState {
  current: CourtOSState;
  backupIncidents: Incident[] | null;
  backupNetwork: NetworkAllocation | null;
  backupOverlay: OverlayState | null;
}

export type ReducerAction =
  | { type: "SET_STATE"; payload: CourtOSState }
  | { type: "OPTIMISTIC_RESOLVE"; payload: string }
  | { type: "ROLLBACK_RESOLVE"; payload: Incident[] }
  | { type: "OPTIMISTIC_ADD_OVERLAY"; payload: string }
  | { type: "ROLLBACK_OVERLAY"; payload: OverlayState }
  | { type: "OPTIMISTIC_REMOVE_OVERLAY"; payload: string }
  | { type: "OPTIMISTIC_RECALC"; payload: NetworkAllocation }
  | { type: "ROLLBACK_RECALC"; payload: NetworkAllocation };

// Additional dummy types that might be needed by the user
export interface KinematicPayload {}
export interface GameStatePayload {}
export interface NetworkPayload {}
export interface ReviewPayload {}
export type EventType = string;
export type PlayState = string;
