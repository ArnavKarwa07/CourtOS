import { useState, useEffect } from "react";
import { useCourtOS } from "./hooks/useCourtOS";
import { Header } from "./components/Header";
import { TelemetryChart } from "./components/TelemetryChart";
import { IncidentFeed } from "./components/IncidentFeed";
import { NetworkAllocationPanel } from "./components/NetworkAllocationPanel";
import { CourtOverlayView } from "./components/CourtOverlayView";
import { AIAssistantWidget } from "./components/AIAssistantWidget";

export default function App() {
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  const [currentMode, setCurrentMode] = useState<"simulation" | "realtime">("simulation");
  const [showRealtimeModal, setShowRealtimeModal] = useState(false);
  const { state, telemetryFeed, sseStatus, toasts, resolvingIds, isRecalculating, srAnnouncement, commentaries, dismissToast, resolveIncident, recalculateNetwork, addOverlay, removeOverlay, apiBase, addToast } = useCourtOS();

  const handleModeSwitch = (mode: "simulation" | "realtime") => {
    if (mode === "realtime") setShowRealtimeModal(true);
    else setCurrentMode("simulation");
  };

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
  };

  useEffect(() => {
    const activeCount = state.current.active_incidents.length;
    const alertLabel = activeCount > 0 ? `[!] ${activeCount} Alerts` : "Normal";
    const stateLabel = state.current.play_state.toUpperCase().replace("_", " ");
    document.title = `${alertLabel} | ${stateLabel} | CourtOS`;
  }, [state.current.active_incidents, state.current.play_state]);

  return (
    <div style={{ paddingBottom: "80px" }}>
      <div className="sr-only" role="status" aria-live="polite" style={{ position: "absolute", width: "1px", height: "1px", padding: "0", overflow: "hidden", clip: "rect(0,0,0,0)", border: "0" }}>{srAnnouncement}</div>
      <div className="dashboard-container">
        <Header currentMode={currentMode} handleModeSwitch={handleModeSwitch} sseStatus={sseStatus} theme={theme} toggleTheme={toggleTheme} />
        <section className="panel" style={{ gridArea: "game" }} aria-labelledby="game-status-heading">
          <div className="panel-header"><h2 id="game-status-heading" className="panel-title">Game Status</h2></div>
          <div style={{ display: "flex", justifyContent: "space-around", alignItems: "center", padding: "var(--space-4) 0" }}>
            <div style={{ textAlign: "center" }}><p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", textTransform: "uppercase" }}>Game Clock</p><p style={{ fontSize: "var(--text-3xl)", fontFamily: "var(--font-mono)", fontWeight: "bold" }}>{state.current.game_clock}</p></div>
            <div style={{ textAlign: "center" }}><p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", textTransform: "uppercase" }}>Period</p><p style={{ fontSize: "var(--text-xl)", fontWeight: "bold" }}>Q{state.current.period}</p></div>
            <div style={{ textAlign: "center" }}><p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", textTransform: "uppercase", marginBottom: "var(--space-2)" }}>Play State</p><span className={`badge ${state.current.play_state === "live" ? "badge-live" : "badge-warning"}`} style={{ fontSize: "var(--text-sm)", padding: "var(--space-2) var(--space-4)" }}>{state.current.play_state.toUpperCase().replace("_", " ")}</span></div>
          </div>
        </section>
        <CourtOverlayView overlay={state.current.overlay} playState={state.current.play_state} addOverlay={addOverlay} removeOverlay={removeOverlay} currentMode={currentMode} />
        <IncidentFeed incidents={state.current.active_incidents} resolvingIds={resolvingIds} resolveIncident={resolveIncident} />
        <NetworkAllocationPanel allocation={state.current.network_allocation} recalculateNetwork={recalculateNetwork} isRecalculating={isRecalculating} />
        <TelemetryChart telemetryFeed={telemetryFeed} />
        <AIAssistantWidget apiBase={apiBase} addToast={addToast} commentaries={commentaries} />
      </div>
      {showRealtimeModal && (
        <div className="modal-overlay" onClick={() => setShowRealtimeModal(false)} role="dialog" aria-modal="true" aria-labelledby="realtime-modal-title">
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-icon">ðŸ”’</div><h3 id="realtime-modal-title" className="modal-title">Real-Time Mode Unavailable</h3>
            <div className="modal-body"><p>Real-time mode is currently not available for the following reasons:</p><ul className="modal-reasons"><li><strong>No live hardware connected</strong></li><li><strong>No active game session</strong></li><li><strong>Network policy not configured</strong></li></ul></div>
            <button className="btn modal-close-btn" onClick={() => setShowRealtimeModal(false)} autoFocus>Got it â€” Stay in Simulation</button>
          </div>
        </div>
      )}
      <div role="status" aria-live="polite" style={{ position: "fixed", bottom: "20px", right: "20px", zIndex: 1000, display: "flex", flexDirection: "column", gap: "10px" }}>
        {toasts.map((toast) => (
          <div key={toast.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "15px", padding: "12px 20px", borderRadius: "var(--radius-md)", color: "#FFFFFF", boxShadow: "0 4px 12px rgba(0,0,0,0.5)", fontSize: "var(--text-sm)", fontWeight: "500", backgroundColor: toast.type === "success" ? "#10B981" : toast.type === "error" ? "#EF4444" : "#3B82F6" }}>
            <span>{toast.message}</span>
            <button style={{ border: "none", background: "transparent", color: "#FFFFFF", cursor: "pointer", fontWeight: "bold" }} onClick={() => dismissToast(toast.id)} aria-label="Dismiss notification">âœ•</button>
          </div>
        ))}
      </div>
    </div>
  );
}
