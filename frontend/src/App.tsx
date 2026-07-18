import VideoUploadPanel from './components/VideoUploadPanel';
import VideoTracker from './components/VideoTracker';
import React, { useState, useEffect, useRef, useReducer } from "react";

// Design Enums matching backend
type Severity = "info" | "warning" | "critical";
type IncidentStatus = "active" | "resolved";

interface Incident {
  incident_id: string;
  severity: Severity;
  category: string;
  message: string;
  created_at: string;
  source_event_id: string;
  status: IncidentStatus;
  resolved_at: string | null;
}

interface NetworkAllocation {
  broadcast: number;
  telemetry: number;
  operations: number;
  emergency: number;
  simulated: boolean;
}

interface OverlayState {
  mode: string;
  active_overlays: string[];
}

interface CourtOSState {
  game_clock: string;
  period: number;
  play_state: string;
  network_allocation: NetworkAllocation;
  overlay: OverlayState;
  active_incidents: Incident[];
  last_event_id: string | null;
  updated_at: string;
}

interface TelemetryEvent {
  event_id: string;
  event_type: string;
  timestamp: string;
  source: string;
  payload: any;
}

interface Toast {
  id: string;
  type: "success" | "error" | "info";
  message: string;
}

// Reducer for canonical state + backups for optimistic UI rollbacks
interface ReducerState {
  current: CourtOSState;
  backupIncidents: Incident[] | null;
  backupNetwork: NetworkAllocation | null;
  backupOverlay: OverlayState | null;
}

type ReducerAction =
  | { type: "SET_STATE"; payload: CourtOSState }
  | { type: "OPTIMISTIC_RESOLVE"; payload: string }
  | { type: "ROLLBACK_RESOLVE"; payload: Incident[] }
  | { type: "OPTIMISTIC_ADD_OVERLAY"; payload: string }
  | { type: "ROLLBACK_OVERLAY"; payload: OverlayState }
  | { type: "OPTIMISTIC_REMOVE_OVERLAY"; payload: string }
  | { type: "OPTIMISTIC_RECALC"; payload: NetworkAllocation }
  | { type: "ROLLBACK_RECALC"; payload: NetworkAllocation };

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

function stateReducer(
  state: ReducerState,
  action: ReducerAction,
): ReducerState {
  switch (action.type) {
    case "SET_STATE":
      return {
        ...state,
        current: action.payload,
      };
    case "OPTIMISTIC_RESOLVE":
      return {
        ...state,
        backupIncidents: [...state.current.active_incidents],
        current: {
          ...state.current,
          active_incidents: state.current.active_incidents.filter(
            (i) => i.incident_id !== action.payload,
          ),
        },
      };
    case "ROLLBACK_RESOLVE":
      return {
        ...state,
        current: {
          ...state.current,
          active_incidents: action.payload,
        },
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
            active_overlays: [
              ...state.current.overlay.active_overlays,
              action.payload,
            ],
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
            active_overlays: state.current.overlay.active_overlays.filter(
              (o) => o !== action.payload,
            ),
          },
        },
      };
    case "ROLLBACK_OVERLAY":
      return {
        ...state,
        current: {
          ...state.current,
          overlay: action.payload,
        },
        backupOverlay: null,
      };
    case "OPTIMISTIC_RECALC":
      return {
        ...state,
        backupNetwork: { ...state.current.network_allocation },
        current: {
          ...state.current,
          network_allocation: action.payload,
        },
      };
    case "ROLLBACK_RECALC":
      return {
        ...state,
        current: {
          ...state.current,
          network_allocation: action.payload,
        },
        backupNetwork: null,
      };
    default:
      return state;
  }
}

export default function App() {
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  const [state, dispatch] = useReducer(stateReducer, initialState);
  const [telemetryFeed, setTelemetryFeed] = useState<TelemetryEvent[]>([]);
  const [sseStatus, setSseStatus] = useState<
    "connected" | "disconnected" | "reconnecting"
  >("disconnected");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [newOverlayId, setNewOverlayId] = useState("");
  const [resolvingIds, setResolvingIds] = useState<string[]>([]);
  const [isRecalculating, setIsRecalculating] = useState(false);
  const [srAnnouncement, setSrAnnouncement] = useState("");

  // Mode toggle state
  const [currentMode, setCurrentMode] = useState<"simulation" | "realtime">("simulation");
  const [showRealtimeModal, setShowRealtimeModal] = useState(false);

  // Heatmap state - tracks activity intensity at grid positions on the court
  const [heatmapData, setHeatmapData] = useState<number[][]>(() => {
    const rows = 6;
    const cols = 10;
    return Array.from({ length: rows }, () => Array(cols).fill(0));
  });

  // AI state variables
  const [commentaries, setCommentaries] = useState<
    { commentary: string; timestamp: string }[]
  >([]);
  const [chatMessages, setChatMessages] = useState<
    { sender: "operator" | "ai"; text: string }[]
  >([
    {
      sender: "ai",
      text: "Hello Operator. Ask me anything about arena logs or incidents.",
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [isChatSending, setIsChatSending] = useState(false);

  const apiBase = window.location.origin; // Same-origin in production, Vite proxies in dev
  const sseReconnectDelay = useRef(1000);
  const reconnectTimer = useRef<number | null>(null);

  // Mode toggle handler
  const handleModeSwitch = (mode: "simulation" | "realtime") => {
    if (mode === "realtime") {
      setShowRealtimeModal(true);
    } else {
      setCurrentMode("simulation");
    }
  };

  // Heatmap simulation effect - generates activity hotspots based on play state
  useEffect(() => {
    if (currentMode !== "simulation") return;
    const interval = setInterval(() => {
      setHeatmapData(prev => {
        const next = prev.map(row => row.map(v => Math.max(0, v * 0.85))); // decay
        const playState = state.current.play_state;
        // Generate activity based on play state
        if (playState === "live") {
          // Multiple hotspots during live play
          for (let k = 0; k < 3; k++) {
            const r = Math.floor(Math.random() * 6);
            const c = Math.floor(Math.random() * 10);
            next[r][c] = Math.min(1, next[r][c] + 0.3 + Math.random() * 0.5);
          }
          // Paint area activity
          next[Math.floor(Math.random() * 3) + 1][Math.floor(Math.random() * 2)] += 0.4;
          next[Math.floor(Math.random() * 3) + 1][8 + Math.floor(Math.random() * 2)] += 0.4;
        } else if (playState === "dead_ball" || playState === "timeout") {
          // Concentrated activity near center
          const r = 2 + Math.floor(Math.random() * 2);
          const c = 4 + Math.floor(Math.random() * 2);
          next[r][c] = Math.min(1, next[r][c] + 0.2);
        } else if (playState === "halftime") {
          // Very low activity, scattered
          if (Math.random() > 0.7) {
            const r = Math.floor(Math.random() * 6);
            const c = Math.floor(Math.random() * 10);
            next[r][c] = Math.min(1, next[r][c] + 0.1);
          }
        }
        return next.map(row => row.map(v => Math.min(1, v)));
      });
    }, 800);
    return () => clearInterval(interval);
  }, [currentMode, state.current.play_state]);

  // Toggle visual theme
  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
  };

  // Add toast alert
  const addToast = (type: "success" | "error" | "info", message: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, message }]);
    if (type !== "error") {
      setTimeout(() => dismissToast(id), 5000);
    }
  };

  // Debounce incident_created to reduce alert spam in fast telemetry windows
  const incidentToastQueueRef = useRef<{
    lastIncident?: Incident;
    count: number;
  }>({ count: 0 });
  const incidentToastTimerRef = useRef<number | null>(null);

  const flushIncidentToast = () => {
    const queued = incidentToastQueueRef.current;
    if (!queued.count || !queued.lastIncident) return;

    const first = queued.lastIncident;
    const n = queued.count;
    addToast(
      "error",
      n === 1
        ? `New alert: ${first.message}`
        : `New alerts: ${n} (latest: ${first.message})`,
    );
    announceToSR(
      n === 1
        ? `New ${first.severity} alert: ${first.message}`
        : `New alerts batch: ${n}. Latest: ${first.message}`,
    );

    incidentToastQueueRef.current = { count: 0 };
    if (incidentToastTimerRef.current) {
      window.clearTimeout(incidentToastTimerRef.current);
      incidentToastTimerRef.current = null;
    }
  };

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Screen Reader polite announcement helper
  const announceToSR = (msg: string) => {
    setSrAnnouncement(msg);
    // Reset after some time so duplicate alerts re-trigger voice synthesis
    setTimeout(() => setSrAnnouncement(""), 1000);
  };

  // Update dynamic page tab title based on incident counts
  useEffect(() => {
    const activeCount = state.current.active_incidents.length;
    const alertLabel = activeCount > 0 ? `[!] ${activeCount} Alerts` : "Normal";
    const stateLabel = state.current.play_state.toUpperCase().replace("_", " ");
    document.title = `${alertLabel} | ${stateLabel} | CourtOS`;
  }, [state.current.active_incidents, state.current.play_state]);

  // Connect to SSE stream
  useEffect(() => {
    let eventSource: EventSource | null = null;

    const connectSSE = () => {
      if (eventSource) {
        eventSource.close();
      }

      eventSource = new EventSource(`${apiBase}/api/v1/events/stream`);

      eventSource.onopen = () => {
        setSseStatus("connected");
        sseReconnectDelay.current = 1000;
        addToast("info", "Real-time connection restored.");
        announceToSR("Connection restored. Dashboard data updated.");
      };

      eventSource.onerror = () => {
        setSseStatus("reconnecting");
        eventSource?.close();

        // Exponential backoff reconnect
        const delay = sseReconnectDelay.current;
        sseReconnectDelay.current = Math.min(delay * 2, 30000);

        addToast("error", `Connection lost. Retrying in ${delay / 1000}s...`);
        announceToSR("Connection lost. Dashboard data may be stale.");

        reconnectTimer.current = window.setTimeout(() => {
          connectSSE();
        }, delay);
      };

      // Handler for initial state snapshot and updates
      eventSource.addEventListener("state_snapshot", (e: MessageEvent) => {
        const snap: CourtOSState = JSON.parse(e.data);
        dispatch({ type: "SET_STATE", payload: snap });
      });

      eventSource.addEventListener("state_update", (e: MessageEvent) => {
        const update: CourtOSState = JSON.parse(e.data);
        dispatch({ type: "SET_STATE", payload: update });

        // Add to telemetry feed
        const dummyEvent: TelemetryEvent = {
          event_id: update.last_event_id || Math.random().toString(),
          event_type: "game_state",
          timestamp: update.updated_at,
          source: "system",
          payload: {
            play_state: update.play_state,
            game_clock: update.game_clock,
          },
        };
        setTelemetryFeed((prev) => [dummyEvent, ...prev.slice(0, 19)]);
      });

      eventSource.addEventListener("incident_created", (e: MessageEvent) => {
        const incident: Incident = JSON.parse(e.data);

        // Queue incidents and flush at most once per window to reduce alert spam.
        incidentToastQueueRef.current = {
          lastIncident: incident,
          count: (incidentToastQueueRef.current.count || 0) + 1,
        };

        if (incidentToastTimerRef.current) {
          window.clearTimeout(incidentToastTimerRef.current);
        }

        incidentToastTimerRef.current = window.setTimeout(() => {
          flushIncidentToast();
        }, 1200);
      });

      eventSource.addEventListener("incident_resolved", () => {
        addToast("success", "Incident resolved.");
        announceToSR("Incident resolved.");
      });

      eventSource.addEventListener("overlay_changed", (e: MessageEvent) => {
        const data = JSON.parse(e.data);
        announceToSR(`Overlay mode changed to ${data.mode}.`);
      });

      eventSource.addEventListener("commentary_event", (e: MessageEvent) => {
        const data = JSON.parse(e.data);
        setCommentaries((prev) => [data, ...prev.slice(0, 19)]);
        announceToSR(`AI Commentary: ${data.commentary}`);
      });
    };

    connectSSE();

    return () => {
      if (eventSource) {
        eventSource.close();
      }
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
    };
  }, []);

  // Fetch telemetry events list on load
  useEffect(() => {
    fetch(`${apiBase}/api/v1/audit?limit=20`)
      .then((res) => res.json())
      .then((data) => {
        const events = data.entries.map((entry: any) => ({
          event_id: entry.source_event_id || entry.log_id,
          event_type: entry.action.replace("event_", ""),
          timestamp: entry.created_at,
          source: entry.actor,
          payload: entry.details,
        }));
        setTelemetryFeed(events);
      })
      .catch(() => {});
  }, []);

  // Action: Resolve Incident (Optimistic UI)
  const resolveIncident = async (incidentId: string) => {
    const backup = [...state.current.active_incidents];
    setResolvingIds((prev) => [...prev, incidentId]);

    // Optimistic dispatch
    dispatch({ type: "OPTIMISTIC_RESOLVE", payload: incidentId });

    try {
      const res = await fetch(
        `${apiBase}/api/v1/incidents/${incidentId}/resolve`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "CourtOS-Client",
          },
        },
      );

      if (!res.ok) {
        throw new Error("API failure");
      }

      addToast("success", "Incident resolved successfully.");
    } catch (err) {
      // Rollback on failure
      dispatch({ type: "ROLLBACK_RESOLVE", payload: backup });
      addToast(
        "error",
        "Failed to resolve incident. Check connection and try again.",
      );
      announceToSR("Failed to resolve incident.");
    } finally {
      setResolvingIds((prev) => prev.filter((id) => id !== incidentId));
    }
  };

  // Action: Recalculate Network Allocation (Optimistic UI)
  const recalculateNetwork = async () => {
    if (isRecalculating) return;
    setIsRecalculating(true);
    const backup = { ...state.current.network_allocation };

    // Optimistic recalculation mock data
    const hasCritical = state.current.active_incidents.some(
      (i) => i.severity === "critical",
    );
    const optimisticAllocation = hasCritical
      ? {
          broadcast: 20,
          telemetry: 20,
          operations: 10,
          emergency: 50,
          simulated: true,
        }
      : {
          broadcast: 40,
          telemetry: 30,
          operations: 20,
          emergency: 10,
          simulated: true,
        };

    dispatch({ type: "OPTIMISTIC_RECALC", payload: optimisticAllocation });

    try {
      const res = await fetch(`${apiBase}/api/v1/network/recalculate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "CourtOS-Client",
        },
      });

      if (!res.ok) {
        throw new Error("API failure");
      }

      addToast("success", "Network allocation recalculated.");
    } catch (err) {
      dispatch({ type: "ROLLBACK_RECALC", payload: backup });
      addToast("error", "Network recalculation failed. Try again.");
    } finally {
      setIsRecalculating(false);
    }
  };

  // Action: Send Operator Chat Message
  const sendChatMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    const query = chatInput.trim();
    if (!query) return;

    setChatMessages((prev) => [...prev, { sender: "operator", text: query }]);
    setChatInput("");
    setIsChatSending(true);

    try {
      const res = await fetch(`${apiBase}/api/v1/ai/assistant`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "CourtOS-Client",
        },
        body: JSON.stringify({ query }),
      });

      if (!res.ok) {
        throw new Error("API failure");
      }

      const data = await res.json();
      setChatMessages((prev) => [...prev, { sender: "ai", text: data.reply }]);
    } catch (err) {
      addToast(
        "error",
        "AI Assistant failed to reply. Please check your credentials and connection.",
      );
      setChatMessages((prev) => [
        ...prev,
        {
          sender: "ai",
          text: "Error: Failed to obtain response from Gemini AI. Check server logs.",
        },
      ]);
    } finally {
      setIsChatSending(false);
    }
  };

  // Action: Add Court Overlay (Optimistic UI)
  const addOverlay = async (e: React.FormEvent) => {
    e.preventDefault();
    const overlayVal = newOverlayId.trim();
    if (!overlayVal) return;

    if (state.current.play_state === "live") {
      addToast(
        "error",
        "Overlays blocked. Dynamic overlays are disabled during live play.",
      );
      announceToSR("Error: Cannot add overlays during live play.");
      return;
    }

    const backup = { ...state.current.overlay };
    dispatch({ type: "OPTIMISTIC_ADD_OVERLAY", payload: overlayVal });
    setNewOverlayId("");

    try {
      const res = await fetch(`${apiBase}/api/v1/court/overlay`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "CourtOS-Client",
        },
        body: JSON.stringify({ action: "add", overlay_id: overlayVal }),
      });

      if (res.status === 409) {
        throw new Error("Blocked: Live play active");
      }
      if (!res.ok) {
        throw new Error("API error");
      }
    } catch (err) {
      dispatch({ type: "ROLLBACK_OVERLAY", payload: backup });
      addToast(
        "error",
        "Cannot add overlay. Dynamic overlays are disabled during live play.",
      );
    }
  };

  // Action: Remove Court Overlay (Optimistic UI)
  const removeOverlay = async (overlayId: string) => {
    const backup = { ...state.current.overlay };
    dispatch({ type: "OPTIMISTIC_REMOVE_OVERLAY", payload: overlayId });

    try {
      const res = await fetch(`${apiBase}/api/v1/court/overlay`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "CourtOS-Client",
        },
        body: JSON.stringify({ action: "remove", overlay_id: overlayId }),
      });

      if (!res.ok) {
        throw new Error("API error");
      }
    } catch (err) {
      dispatch({ type: "ROLLBACK_OVERLAY", payload: backup });
      addToast("error", "Failed to remove overlay.");
    }
  };

  return (
    <div style={{ paddingBottom: "80px" }}>
      {/* Screen Reader Live Region */}
      <div
        className="sr-only"
        role="status"
        aria-live="polite"
        style={{
          position: "absolute",
          width: "1px",
          height: "1px",
          padding: "0",
          overflow: "hidden",
          clip: "rect(0,0,0,0)",
          border: "0",
        }}
      >
        {srAnnouncement}
      </div>

      <div className="dashboard-container">
        {/* Header */}
        <header
          className="panel"
          style={{
            gridArea: "header",
            flexDirection: "row",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <h1 style={{ fontSize: "var(--text-xl)", fontWeight: "bold" }}>
              CourtOS
            </h1>
            <p
              style={{
                fontSize: "var(--text-xs)",
                color: "var(--color-text-secondary)",
              }}
            >
              Arena Operations Dashboard
            </p>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-4)",
            }}
          >
            {/* Mode Toggle */}
            <div className="mode-toggle">
              <button
                className={`mode-toggle-btn ${currentMode === "simulation" ? "mode-toggle-btn--active" : ""}`}
                onClick={() => handleModeSwitch("simulation")}
              >
                ⚡ Simulation
              </button>
              <button
                className={`mode-toggle-btn ${currentMode === "realtime" ? "mode-toggle-btn--active" : ""}`}
                onClick={() => handleModeSwitch("realtime")}
              >
                🔴 Real-Time
              </button>
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-2)",
              }}
            >
              <span
                style={{
                  width: "10px",
                  height: "10px",
                  borderRadius: "50%",
                  backgroundColor:
                    sseStatus === "connected"
                      ? "var(--color-success)"
                      : sseStatus === "reconnecting"
                        ? "var(--color-severity-warning)"
                        : "var(--color-severity-critical)",
                }}
              />
              <span style={{ fontSize: "var(--text-sm)", fontWeight: "500" }}>
                SSE: {sseStatus.toUpperCase()}
              </span>
            </div>
            <button
              className="btn"
              onClick={toggleTheme}
              aria-label="Toggle light or dark theme mode"
            >
              Theme: {theme.toUpperCase()}
            </button>
          </div>
        </header>

        {/* Game Status */}
        <section
          className="panel"
          style={{ gridArea: "game" }}
          aria-labelledby="game-status-heading"
        >
          <div className="panel-header">
            <h2 id="game-status-heading" className="panel-title">
              Game Status
            </h2>
          </div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-around",
              alignItems: "center",
              padding: "var(--space-4) 0",
            }}
          >
            <div style={{ textAlign: "center" }}>
              <p
                style={{
                  fontSize: "var(--text-xs)",
                  color: "var(--color-text-secondary)",
                  textTransform: "uppercase",
                }}
              >
                Game Clock
              </p>
              <p
                style={{
                  fontSize: "var(--text-3xl)",
                  fontFamily: "var(--font-mono)",
                  fontWeight: "bold",
                }}
                aria-label={`Game clock: ${state.current.game_clock.split(":")[0]} minutes and ${state.current.game_clock.split(":")[1]} seconds`}
              >
                {state.current.game_clock}
              </p>
            </div>
            <div style={{ textAlign: "center" }}>
              <p
                style={{
                  fontSize: "var(--text-xs)",
                  color: "var(--color-text-secondary)",
                  textTransform: "uppercase",
                }}
              >
                Period
              </p>
              <p style={{ fontSize: "var(--text-xl)", fontWeight: "bold" }}>
                Q{state.current.period}
              </p>
            </div>
            <div style={{ textAlign: "center" }}>
              <p
                style={{
                  fontSize: "var(--text-xs)",
                  color: "var(--color-text-secondary)",
                  textTransform: "uppercase",
                  marginBottom: "var(--space-2)",
                }}
              >
                Play State
              </p>
              <span
                className={`badge ${state.current.play_state === "live" ? "badge-live" : "badge-warning"}`}
                style={{
                  fontSize: "var(--text-sm)",
                  padding: "var(--space-2) var(--space-4)",
                }}
              >
                {state.current.play_state.toUpperCase().replace("_", " ")}
              </span>
            </div>
          </div>
        </section>

        {/* Court Overlay Gating */}
        <section
          className="panel"
          style={{ gridArea: "overlay" }}
          aria-labelledby="overlay-heading"
        >
          <div className="panel-header">
            <h2 id="overlay-heading" className="panel-title">
              Court Overlay Controls
            </h2>
            <span
              className={`badge ${state.current.overlay.mode === "static" ? "badge-critical" : "badge-info"}`}
            >
              Mode: {state.current.overlay.mode.toUpperCase()}
            </span>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 120px",
              gap: "var(--space-4)",
            }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-3)",
              }}
            >
              {/* Active overlays list */}
              {state.current.overlay.active_overlays.length === 0 ? (
                <p
                  style={{
                    fontSize: "var(--text-sm)",
                    color: "var(--color-text-secondary)",
                    textAlign: "center",
                    padding: "var(--space-4) 0",
                  }}
                >
                  {state.current.overlay.mode === "static"
                    ? "🔒 Overlays suppressed during live play."
                    : "No active overlays."}
                </p>
              ) : (
                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: "var(--space-2)",
                  }}
                >
                  {state.current.overlay.active_overlays.map((overlayId) => (
                    <span
                      key={overlayId}
                      className="badge badge-info"
                      style={{
                        paddingRight: "var(--space-1)",
                        textTransform: "none",
                        display: "inline-flex",
                        alignItems: "center",
                      }}
                    >
                      {overlayId}
                      <button
                        style={{
                          border: "none",
                          background: "transparent",
                          cursor: "pointer",
                          color: "inherit",
                          marginLeft: "var(--space-1)",
                          padding: "var(--space-1)",
                        }}
                        onClick={() => removeOverlay(overlayId)}
                        aria-label={`Remove overlay ${overlayId}`}
                      >
                        ✕
                      </button>
                    </span>
                  ))}
                </div>
              )}

              {/* Add overlay form */}
              <form
                onSubmit={addOverlay}
                style={{ display: "flex", gap: "var(--space-2)" }}
              >
                <input
                  type="text"
                  className="btn"
                  style={{ flexGrow: 1, textAlign: "left", cursor: "text" }}
                  placeholder="Enter overlay ID (e.g. heatmap-q2)"
                  value={newOverlayId}
                  onChange={(e) => setNewOverlayId(e.target.value)}
                  disabled={state.current.overlay.mode === "static"}
                  aria-label="New overlay name input"
                />
                <button
                  type="submit"
                  className="btn"
                  disabled={
                    state.current.overlay.mode === "static" ||
                    !newOverlayId.trim()
                  }
                  aria-label="Add overlay button"
                >
                  Add
                </button>
              </form>
            </div>

            {/* Court visualizer with live heatmap */}
            <svg
              viewBox="0 0 100 60"
              className="court-svg"
              aria-label="Basketball court diagram with live heatmap"
            >
              <defs>
                <radialGradient id="heatGlow">
                  <stop offset="0%" stopColor="rgba(239,68,68,0.8)" />
                  <stop offset="50%" stopColor="rgba(245,158,11,0.4)" />
                  <stop offset="100%" stopColor="rgba(96,165,250,0)" />
                </radialGradient>
              </defs>

              {/* Heatmap cells */}
              {heatmapData.map((row, ri) =>
                row.map((val, ci) => {
                  if (val < 0.05) return null;
                  const x = ci * 10;
                  const y = ri * 10;
                  const r = val > 0.7 ? 0 : val > 0.4 ? 120 : 200;
                  const g = val > 0.7 ? Math.floor(68 + (1 - val) * 100) : val > 0.4 ? Math.floor(158 - val * 60) : Math.floor(165 + val * 50);
                  const b = val > 0.7 ? 68 : val > 0.4 ? 11 : 250;
                  return (
                    <rect
                      key={`heat-${ri}-${ci}`}
                      x={x}
                      y={y}
                      width="10"
                      height="10"
                      fill={`rgba(${r},${g},${b},${val * 0.7})`}
                      rx="2"
                      style={{ transition: "fill 0.4s ease" }}
                    />
                  );
                })
              )}

              {/* Court lines */}
              <rect
                x="0"
                y="0"
                width="100"
                height="60"
                fill="none"
                stroke="var(--color-border)"
                strokeWidth="2"
              />
              <line
                x1="50"
                y1="0"
                x2="50"
                y2="60"
                stroke="var(--color-border)"
                strokeWidth="2"
              />
              <circle
                cx="50"
                cy="30"
                r="10"
                fill="none"
                stroke="var(--color-border)"
                strokeWidth="2"
              />
              <rect
                x="0"
                y="15"
                width="19"
                height="30"
                fill="none"
                stroke="var(--color-border)"
                strokeWidth="2"
              />
              <rect
                x="81"
                y="15"
                width="19"
                height="30"
                fill="none"
                stroke="var(--color-border)"
                strokeWidth="2"
              />

              {/* Draw active overlay placeholders */}
              {state.current.overlay.active_overlays.includes("paint") && (
                <rect
                  x="0"
                  y="15"
                  width="19"
                  height="30"
                  fill="rgba(96, 165, 250, 0.3)"
                />
              )}
              {state.current.overlay.active_overlays.map((id, index) => (
                <circle
                  key={id}
                  cx={30 + index * 15}
                  cy="30"
                  r="4"
                  fill="rgba(96, 165, 250, 0.6)"
                  stroke="var(--color-focus)"
                  strokeWidth="1"
                />
              ))}
            </svg>

            {/* Heatmap legend */}
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", marginTop: "var(--space-2)" }}>
              <span>Activity:</span>
              <div style={{ display: "flex", height: "8px", borderRadius: "4px", overflow: "hidden", flex: 1 }}>
                <div style={{ flex: 1, background: "rgba(96,165,250,0.3)" }} />
                <div style={{ flex: 1, background: "rgba(245,158,11,0.5)" }} />
                <div style={{ flex: 1, background: "rgba(239,68,68,0.7)" }} />
              </div>
              <span style={{ display: "flex", justifyContent: "space-between", gap: "var(--space-4)" }}>
                <span>Low</span>
                <span>High</span>
              </span>
            </div>
          </div>
        </section>

        {/* Active Incidents */}
        <section
          className="panel"
          style={{ gridArea: "incidents", maxHeight: "550px" }}
          aria-labelledby="incidents-heading"
        >
          <div className="panel-header">
            <h2 id="incidents-heading" className="panel-title">
              Active Incidents ({state.current.active_incidents.length})
            </h2>
          </div>
          <ul
            className="scroll-list"
            style={{
              flexGrow: 1,
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-2)",
            }}
          >
            {state.current.active_incidents.length === 0 ? (
              <li
                style={{
                  textAlign: "center",
                  color: "var(--color-text-secondary)",
                  padding: "var(--space-8) 0",
                }}
              >
                No active incidents. Venue telemetry is normal.
              </li>
            ) : (
              state.current.active_incidents.map((incident) => (
                <li
                  key={incident.incident_id}
                  className="panel"
                  style={{
                    backgroundColor: "var(--color-surface-elevated)",
                    borderLeft: `4px solid ${
                      incident.severity === "critical"
                        ? "var(--color-severity-critical)"
                        : incident.severity === "warning"
                          ? "var(--color-severity-warning)"
                          : "var(--color-severity-info)"
                    }`,
                    gap: "var(--space-2)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <span
                      className={`badge ${incident.severity === "critical" ? "badge-critical" : incident.severity === "warning" ? "badge-warning" : "badge-info"}`}
                    >
                      {incident.severity}
                    </span>
                    <span
                      style={{
                        fontSize: "var(--text-xs)",
                        color: "var(--color-text-secondary)",
                        fontFamily: "var(--font-mono)",
                      }}
                    >
                      {incident.incident_id.substring(0, 8)}
                    </span>
                  </div>
                  <p style={{ fontSize: "var(--text-sm)", fontWeight: "500" }}>
                    {incident.message}
                  </p>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginTop: "var(--space-2)",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "var(--text-xs)",
                        color: "var(--color-text-secondary)",
                      }}
                    >
                      Category: {incident.category}
                    </span>
                    <button
                      className="btn"
                      style={{
                        padding: "4px 12px",
                        fontSize: "var(--text-xs)",
                      }}
                      onClick={() => resolveIncident(incident.incident_id)}
                      disabled={resolvingIds.includes(incident.incident_id)}
                      aria-label={`Resolve incident: ${incident.message}`}
                    >
                      {resolvingIds.includes(incident.incident_id)
                        ? "Resolving..."
                        : "Resolve"}
                    </button>
                  </div>
                </li>
              ))
            )}
          </ul>
        </section>

        {/* Network Policy */}
        <section
          className="panel"
          style={{ gridArea: "network" }}
          aria-labelledby="network-heading"
        >
          <div className="panel-header">
            <h2 id="network-heading" className="panel-title">
              Network Allocation Recommendations
            </h2>
            <span className="badge badge-simulated">[SIMULATED]</span>
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-3)",
            }}
          >
            {(
              ["broadcast", "telemetry", "operations", "emergency"] as const
            ).map((channel) => {
              const val = state.current.network_allocation[channel];
              return (
                <div
                  key={channel}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "2px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "var(--text-sm)",
                    }}
                  >
                    <span
                      style={{ textTransform: "capitalize", fontWeight: "500" }}
                    >
                      {channel}
                    </span>
                    <span style={{ fontFamily: "var(--font-mono)" }}>
                      {val}%
                    </span>
                  </div>
                  <div
                    role="meter"
                    aria-label={`${channel} allocation: ${val}%`}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={val}
                    style={{
                      height: "10px",
                      backgroundColor: "var(--color-surface-elevated)",
                      borderRadius: "5px",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        height: "100%",
                        width: `${val}%`,
                        backgroundColor:
                          channel === "emergency" && val > 10
                            ? "var(--color-severity-critical)"
                            : "var(--color-focus)",
                        transition: "width 0.5s ease-in-out",
                      }}
                    />
                  </div>
                </div>
              );
            })}

            <button
              className="btn"
              style={{ marginTop: "var(--space-2)" }}
              onClick={recalculateNetwork}
              disabled={isRecalculating}
              aria-label="Force network policy recalculation"
            >
              {isRecalculating ? "Recalculating..." : "Recalculate Allocations"}
            </button>
          </div>
        </section>

        {/* Telemetry Feed */}
        <section
          className="panel"
          style={{ gridArea: "feed", maxHeight: "350px" }}
          aria-labelledby="feed-heading"
        >
          <div className="panel-header">
            <h2 id="feed-heading" className="panel-title">
              Telemetry & Events Feed
            </h2>
          </div>
          <ul
            className="scroll-list"
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-2)",
            }}
          >
            {telemetryFeed.length === 0 ? (
              <li
                style={{
                  textAlign: "center",
                  color: "var(--color-text-secondary)",
                  padding: "var(--space-6) 0",
                }}
              >
                No events received. Waiting for simulation stream...
              </li>
            ) : (
              telemetryFeed.map((event, idx) => (
                <li
                  key={event.event_id + idx}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    fontSize: "var(--text-xs)",
                    padding: "var(--space-2)",
                    borderBottom: "1px solid var(--color-border)",
                    fontFamily: "var(--font-mono)",
                  }}
                  aria-label={`${event.event_type} event from ${event.source} at ${new Date(event.timestamp).toLocaleTimeString()}`}
                >
                  <span
                    style={{ fontWeight: "bold", color: "var(--color-focus)" }}
                  >
                    [{event.event_type.toUpperCase()}]
                  </span>
                  <span style={{ color: "var(--color-text-secondary)" }}>
                    src: {event.source}
                  </span>
                  <span>{new Date(event.timestamp).toLocaleTimeString()}</span>
                </li>
              ))
            )}
          </ul>
        </section>

        {/* AI Operator Assistant */}
        <section
          className="panel"
          style={{ gridArea: "assistant", maxHeight: "450px" }}
          aria-labelledby="assistant-heading"
        >
          <div className="panel-header">
            <h2 id="assistant-heading" className="panel-title">
              AI Operator Assistant
            </h2>
            <span className="badge badge-simulated">LangGraph Router</span>
          </div>
          <div
            style={{
              flexGrow: 1,
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-2)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                flexGrow: 1,
                overflowY: "auto",
                backgroundColor: "var(--color-surface-elevated)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-md)",
                padding: "var(--space-3)",
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-2)",
              }}
            >
              {chatMessages.map((msg, idx) => (
                <div
                  key={idx}
                  style={{
                    alignSelf:
                      msg.sender === "operator" ? "flex-end" : "flex-start",
                    backgroundColor:
                      msg.sender === "operator"
                        ? "var(--color-focus)"
                        : "var(--color-border)",
                    color:
                      msg.sender === "operator"
                        ? "#FFFFFF"
                        : "var(--color-text-primary)",
                    padding: "8px 12px",
                    borderRadius: "8px",
                    maxWidth: "85%",
                    fontSize: "var(--text-sm)",
                    wordBreak: "break-word",
                  }}
                >
                  <p
                    style={{
                      fontSize: "10px",
                      color:
                        msg.sender === "operator"
                          ? "rgba(255,255,255,0.7)"
                          : "var(--color-text-secondary)",
                      marginBottom: "2px",
                      fontWeight: "bold",
                    }}
                  >
                    {msg.sender === "operator" ? "OPERATOR" : "AI"}
                  </p>
                  <p>{msg.text}</p>
                </div>
              ))}
            </div>

            <form
              onSubmit={sendChatMessage}
              style={{
                display: "flex",
                gap: "var(--space-2)",
                marginTop: "2px",
              }}
            >
              <input
                type="text"
                className="btn"
                style={{ flexGrow: 1, textAlign: "left", cursor: "text" }}
                placeholder="Ask AI (e.g. show incident count)..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                disabled={isChatSending}
                aria-label="Ask AI Assistant input field"
              />
              <button
                type="submit"
                className="btn"
                disabled={isChatSending || !chatInput.trim()}
                aria-label="Send query to AI"
              >
                {isChatSending ? "..." : "Ask"}
              </button>
            </form>
          </div>
        </section>

        {/* AI Live Commentary */}
        <section
          className="panel"
          style={{ gridArea: "commentary", maxHeight: "350px" }}
          aria-labelledby="commentary-heading"
        >
          <div className="panel-header">
            <h2 id="commentary-heading" className="panel-title">
              AI Sports Commentary
            </h2>
            <span className="badge badge-live">Live play-by-play</span>
          </div>
          <ul
            className="scroll-list"
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-2)",
            }}
          >
            {commentaries.length === 0 ? (
              <li
                style={{
                  textAlign: "center",
                  color: "var(--color-text-secondary)",
                  padding: "var(--space-6) 0",
                }}
              >
                Waiting for game events to commentate...
              </li>
            ) : (
              commentaries.map((com, idx) => (
                <li
                  key={idx}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "4px",
                    padding: "var(--space-2)",
                    backgroundColor: "var(--color-surface-elevated)",
                    borderLeft: "4px solid var(--color-simulated)",
                    borderRadius: "var(--radius-sm)",
                    fontSize: "var(--text-sm)",
                  }}
                  aria-label={`Commentary at ${new Date(com.timestamp).toLocaleTimeString()}: ${com.commentary}`}
                >
                  <p style={{ fontStyle: "italic" }}>🎙️ "{com.commentary}"</p>
                  <span
                    style={{
                      fontSize: "10px",
                      color: "var(--color-text-secondary)",
                      alignSelf: "flex-end",
                    }}
                  >
                    {new Date(com.timestamp).toLocaleTimeString()}
                  </span>
                </li>
              ))
            )}
          </ul>
        </section>
                {/* Mock Video Feature */}
        <VideoUploadPanel />
        <VideoTracker />
{/* end grid container */}
      </div>

      {/* Real-Time Mode Alert Modal */}
      {showRealtimeModal && (
        <div
          className="modal-overlay"
          onClick={() => setShowRealtimeModal(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="realtime-modal-title"
        >
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-icon">🔒</div>
            <h3 id="realtime-modal-title" className="modal-title">
              Real-Time Mode Unavailable
            </h3>
            <div className="modal-body">
              <p>Real-time mode is currently not available for the following reasons:</p>
              <ul className="modal-reasons">
                <li>
                  <strong>No live hardware connected</strong> — Real-time mode requires active venue sensor feeds (accelerometers, tracking cameras, RFID tags) which are not currently online.
                </li>
                <li>
                  <strong>No active game session</strong> — There is no scheduled game or event session bound to this CourtOS instance.
                </li>
                <li>
                  <strong>Network policy not configured</strong> — Production network policies (broadcast, telemetry, emergency channels) have not been provisioned by the venue operator.
                </li>
              </ul>
              <p style={{ marginTop: "var(--space-3)", color: "var(--color-text-secondary)", fontSize: "var(--text-sm)" }}>
                Please use <strong>Simulation Mode</strong> to explore all CourtOS features with synthetic game data.
              </p>
            </div>
            <button
              className="btn modal-close-btn"
              onClick={() => setShowRealtimeModal(false)}
              autoFocus
            >
              Got it — Stay in Simulation
            </button>
          </div>
        </div>
      )}

      {/* Floating Toast Notification Stack */}
      <div
        role="status"
        aria-live="polite"
        style={{
          position: "fixed",
          bottom: "20px",
          right: "20px",
          zIndex: 1000,
          display: "flex",
          flexDirection: "column",
          gap: "10px",
        }}
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "15px",
              padding: "12px 20px",
              borderRadius: "var(--radius-md)",
              color: "#FFFFFF",
              boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
              fontSize: "var(--text-sm)",
              fontWeight: "500",
              backgroundColor:
                toast.type === "success"
                  ? "#10B981"
                  : toast.type === "error"
                    ? "#EF4444"
                    : "#3B82F6",
            }}
          >
            <span>{toast.message}</span>
            <button
              style={{
                border: "none",
                background: "transparent",
                color: "#FFFFFF",
                cursor: "pointer",
                fontWeight: "bold",
              }}
              onClick={() => dismissToast(toast.id)}
              aria-label="Dismiss notification"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
