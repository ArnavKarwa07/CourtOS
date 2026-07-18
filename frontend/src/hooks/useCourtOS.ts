import { useState, useEffect, useRef, useReducer, useCallback } from "react";
import type { CourtOSState, Incident, Toast, ReducerState, ReducerAction } from "../types";
import { useTelemetryBuffer } from "./useTelemetryBuffer";

const initialState: ReducerState = {
  current: {
    game_clock: "00:00",
    period: 1,
    play_state: "pre_game",
    network_allocation: {
      broadcast: 40,
      telemetry: 30,
      operations: 20,
      emergency: 10,
      simulated: true,
    },
    overlay: { mode: "dynamic", active_overlays: [] },
    active_incidents: [],
    last_event_id: null,
    updated_at: new Date().toISOString(),
  },
  backupIncidents: null,
  backupNetwork: null,
  backupOverlay: null,
};

export const timeoutsRef = { current: new Set<number>() };

function stateReducer(state: ReducerState, action: ReducerAction): ReducerState {
  switch (action.type) {
    case "SET_STATE":
      return { ...state, current: action.payload };
    case "OPTIMISTIC_RESOLVE":
      return {
        ...state,
        backupIncidents: [...state.current.active_incidents],
        current: {
          ...state.current,
          active_incidents: state.current.active_incidents.filter((i) => i.incident_id !== action.payload),
        },
      };
    case "ROLLBACK_RESOLVE":
      return {
        ...state,
        current: { ...state.current, active_incidents: state.backupIncidents || state.current.active_incidents },
        backupIncidents: null,
      };
    case "OPTIMISTIC_ADD_OVERLAY":
      return {
        ...state,
        backupOverlay: { ...state.current.overlay },
        current: {
          ...state.current,
          overlay: {
            ...state.current.overlay,
            active_overlays: [...state.current.overlay.active_overlays, action.payload],
          },
        },
      };
    case "OPTIMISTIC_REMOVE_OVERLAY":
      return {
        ...state,
        backupOverlay: { ...state.current.overlay },
        current: {
          ...state.current,
          overlay: {
            ...state.current.overlay,
            active_overlays: state.current.overlay.active_overlays.filter((o) => o !== action.payload),
          },
        },
      };
    case "ROLLBACK_OVERLAY":
      return {
        ...state,
        current: { ...state.current, overlay: state.backupOverlay || state.current.overlay },
        backupOverlay: null,
      };
    case "OPTIMISTIC_RECALC":
      return {
        ...state,
        backupNetwork: { ...state.current.network_allocation },
        current: { ...state.current, network_allocation: action.payload },
      };
    case "ROLLBACK_RECALC":
      return {
        ...state,
        current: { ...state.current, network_allocation: state.backupNetwork || state.current.network_allocation },
        backupNetwork: null,
      };
    default:
      return state;
  }
}

export function useCourtOS() {
  const [state, dispatch] = useReducer(stateReducer, initialState);
  const { telemetryFeed, addEvent, setEvents: setTelemetryFeed } = useTelemetryBuffer([], 50);
  const [sseStatus, setSseStatus] = useState<"connected" | "disconnected" | "reconnecting">("disconnected");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [resolvingIds, setResolvingIds] = useState<string[]>([]);
  const [isRecalculating, setIsRecalculating] = useState(false);
  const [srAnnouncement, setSrAnnouncement] = useState("");
  const [commentaries, setCommentaries] = useState<{ commentary: string; timestamp: string }[]>([]);

  const apiBase = window.location.origin;
  const sseReconnectDelay = useRef(1000);
  const reconnectTimer = useRef<number | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  const announceToSR = useCallback((msg: string) => {
    setSrAnnouncement(msg);
    const timer = window.setTimeout(() => setSrAnnouncement(""), 1000);
    timeoutsRef.current.add(timer);
  }, []);

  const addToast = useCallback((type: "success" | "error" | "info", message: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, message }].slice(-5));
    if (type !== "error") {
      const timer = window.setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
        timeoutsRef.current.delete(timer);
      }, 5000);
      timeoutsRef.current.add(timer);
    }
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const incidentToastQueueRef = useRef<{ lastIncident?: Incident; count: number }>({ count: 0 });
  const incidentToastTimerRef = useRef<number | null>(null);

  const flushIncidentToast = useCallback(() => {
    const queued = incidentToastQueueRef.current;
    if (!queued.count || !queued.lastIncident) return;
    const first = queued.lastIncident;
    const n = queued.count;
    addToast("error", n === 1 ? "New alert: " + first.message : "New alerts: " + n + " (latest: " + first.message + ")");
    announceToSR(n === 1 ? "New " + first.severity + " alert: " + first.message : "New alerts batch: " + n + ". Latest: " + first.message);
    incidentToastQueueRef.current = { count: 0 };
    if (incidentToastTimerRef.current) {
      window.clearTimeout(incidentToastTimerRef.current);
      incidentToastTimerRef.current = null;
    }
  }, [addToast, announceToSR]);

  useEffect(() => {
    let eventSource: EventSource | null = null;
    const connectSSE = () => {
      if (eventSource) eventSource.close();
      eventSource = new EventSource(apiBase + "/api/v1/events/stream");
      eventSource.onopen = () => {
        setSseStatus("connected");
        sseReconnectDelay.current = 1000;
        addToast("info", "Real-time connection restored.");
        announceToSR("Connection restored. Dashboard data updated.");
      };
      eventSource.onerror = () => {
        setSseStatus("reconnecting");
        eventSource?.close();
        const delay = sseReconnectDelay.current;
        sseReconnectDelay.current = Math.min(delay * 2, 30000);
        addToast("error", "Connection lost. Retrying in " + (delay / 1000) + "s...");
        announceToSR("Connection lost. Dashboard data may be stale.");
        reconnectTimer.current = window.setTimeout(connectSSE, delay);
      };
      eventSource.addEventListener("state_snapshot", (e: MessageEvent) => {
        dispatch({ type: "SET_STATE", payload: JSON.parse(e.data) });
      });
      eventSource.addEventListener("state_update", (e: MessageEvent) => {
        const update: CourtOSState = JSON.parse(e.data);
        dispatch({ type: "SET_STATE", payload: update });
        addEvent({
          event_id: update.last_event_id || Math.random().toString(),
          event_type: "game_state",
          timestamp: update.updated_at,
          source: "system",
          payload: { play_state: update.play_state, game_clock: update.game_clock },
        });
      });
      eventSource.addEventListener("incident_created", (e: MessageEvent) => {
        const incident: Incident = JSON.parse(e.data);
        incidentToastQueueRef.current = {
          lastIncident: incident,
          count: (incidentToastQueueRef.current.count || 0) + 1,
        };
        if (incidentToastTimerRef.current) window.clearTimeout(incidentToastTimerRef.current);
        incidentToastTimerRef.current = window.setTimeout(() => flushIncidentToast(), 1200);
      });
      eventSource.addEventListener("incident_resolved", () => {
        addToast("success", "Incident resolved.");
        announceToSR("Incident resolved.");
      });
      eventSource.addEventListener("overlay_changed", (e: MessageEvent) => {
        const data = JSON.parse(e.data);
        announceToSR("Overlay mode changed to " + data.mode + ".");
      });
      eventSource.addEventListener("commentary_event", (e: MessageEvent) => {
        const data = JSON.parse(e.data);
        setCommentaries((prev) => [data, ...prev.slice(0, 19)]);
        announceToSR("AI Commentary: " + data.commentary);
      });
    };
    connectSSE();
    return () => {
      if (eventSource) eventSource.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (incidentToastTimerRef.current) clearTimeout(incidentToastTimerRef.current);
      timeoutsRef.current.forEach((t) => clearTimeout(t));
      timeoutsRef.current.clear();
    };
  }, [addToast, announceToSR, addEvent, flushIncidentToast, apiBase]);

  useEffect(() => {
    fetch(apiBase + "/api/v1/audit?limit=20")
      .then((res) => res.json())
      .then((data) => {
        const events = data.entries.map((entry: { source_event_id?: string; log_id: string; action: string; created_at: string; actor: string; details: Record<string, unknown> }) => ({
          event_id: entry.source_event_id || entry.log_id,
          event_type: entry.action.replace("event_", ""),
          timestamp: entry.created_at,
          source: entry.actor,
          payload: entry.details,
        }));
        setTelemetryFeed(events);
      })
      .catch(() => {});
  }, [apiBase, setTelemetryFeed]);

  const resolveIncident = useCallback(async (incidentId: string) => {
    setResolvingIds((prev) => [...prev, incidentId]);
    dispatch({ type: "OPTIMISTIC_RESOLVE", payload: incidentId });
    try {
      const res = await fetch(apiBase + "/api/v1/incidents/" + incidentId + "/resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Requested-With": "CourtOS-Client" },
      });
      if (!res.ok) throw new Error("API failure");
      addToast("success", "Incident resolved successfully.");
    } catch (err) {
      dispatch({ type: "ROLLBACK_RESOLVE", payload: null as any });
      addToast("error", "Failed to resolve incident. Check connection and try again.");
      announceToSR("Failed to resolve incident.");
    } finally {
      setResolvingIds((prev) => prev.filter((id) => id !== incidentId));
    }
  }, [apiBase, addToast, announceToSR]);

  const recalculateNetwork = useCallback(async () => {
    if (isRecalculating) return;
    setIsRecalculating(true);
    const hasCritical = stateRef.current.current.active_incidents.some((i) => i.severity === "critical");
    const optimisticAllocation = hasCritical
      ? { broadcast: 20, telemetry: 20, operations: 10, emergency: 50, simulated: true }
      : { broadcast: 40, telemetry: 30, operations: 20, emergency: 10, simulated: true };
    dispatch({ type: "OPTIMISTIC_RECALC", payload: optimisticAllocation });
    try {
      const res = await fetch(apiBase + "/api/v1/network/recalculate", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Requested-With": "CourtOS-Client" },
      });
      if (!res.ok) throw new Error("API failure");
      addToast("success", "Network allocation recalculated.");
    } catch (err) {
      dispatch({ type: "ROLLBACK_RECALC", payload: null as any });
      addToast("error", "Network recalculation failed. Try again.");
    } finally {
      setIsRecalculating(false);
    }
  }, [apiBase, isRecalculating, addToast]);

  const addOverlay = useCallback(async (overlayVal: string) => {
    if (!overlayVal) return;
    if (stateRef.current.current.play_state === "live") {
      addToast("error", "Overlays blocked. Dynamic overlays are disabled during live play.");
      announceToSR("Error: Cannot add overlays during live play.");
      return;
    }
    dispatch({ type: "OPTIMISTIC_ADD_OVERLAY", payload: overlayVal });
    try {
      const res = await fetch(apiBase + "/api/v1/court/overlay", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Requested-With": "CourtOS-Client" },
        body: JSON.stringify({ action: "add", overlay_id: overlayVal }),
      });
      if (res.status === 409) throw new Error("Blocked: Live play active");
      if (!res.ok) throw new Error("API error");
    } catch (err) {
      dispatch({ type: "ROLLBACK_OVERLAY", payload: null as any });
      addToast("error", "Cannot add overlay. Dynamic overlays are disabled during live play.");
    }
  }, [apiBase, addToast, announceToSR]);

  const removeOverlay = useCallback(async (overlayId: string) => {
    dispatch({ type: "OPTIMISTIC_REMOVE_OVERLAY", payload: overlayId });
    try {
      const res = await fetch(apiBase + "/api/v1/court/overlay", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Requested-With": "CourtOS-Client" },
        body: JSON.stringify({ action: "remove", overlay_id: overlayId }),
      });
      if (!res.ok) throw new Error("API error");
    } catch (err) {
      dispatch({ type: "ROLLBACK_OVERLAY", payload: null as any });
      addToast("error", "Failed to remove overlay.");
    }
  }, [apiBase, addToast]);

  return {
    state,
    telemetryFeed,
    sseStatus,
    toasts,
    resolvingIds,
    isRecalculating,
    srAnnouncement,
    commentaries,
    dismissToast,
    resolveIncident,
    recalculateNetwork,
    addOverlay,
    removeOverlay,
    apiBase,
    addToast
  };
}


