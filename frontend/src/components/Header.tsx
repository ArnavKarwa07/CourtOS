import React from 'react';

interface HeaderProps {
  currentMode: 'simulation' | 'realtime';
  handleModeSwitch: (mode: 'simulation' | 'realtime') => void;
  sseStatus: 'connected' | 'disconnected' | 'reconnecting';
  theme: 'light' | 'dark';
  toggleTheme: () => void;
}

export const Header = React.memo(({ currentMode, handleModeSwitch, sseStatus, theme, toggleTheme }: HeaderProps) => {
  return (
    <header className="panel" style={{ gridArea: "header", flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
      <div>
        <h1 style={{ fontSize: "var(--text-xl)", fontWeight: "bold" }}>CourtOS</h1>
        <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)" }}>Arena Operations Dashboard</p>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
        <div className="mode-toggle">
          <button className={`mode-toggle-btn ${currentMode === "simulation" ? "mode-toggle-btn--active" : ""}`} onClick={() => handleModeSwitch("simulation")}>⚡ Simulation</button>
          <button className={`mode-toggle-btn ${currentMode === "realtime" ? "mode-toggle-btn--active" : ""}`} onClick={() => handleModeSwitch("realtime")}>🔴 Real-Time</button>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <span style={{ width: "10px", height: "10px", borderRadius: "50%", backgroundColor: sseStatus === "connected" ? "var(--color-success)" : sseStatus === "reconnecting" ? "var(--color-severity-warning)" : "var(--color-severity-critical)" }} />
          <span style={{ fontSize: "var(--text-sm)", fontWeight: "500" }}>SSE: {sseStatus.toUpperCase()}</span>
        </div>
        <button className="btn" onClick={toggleTheme} aria-label="Toggle light or dark theme mode">Theme: {theme.toUpperCase()}</button>
      </div>
    </header>
  );
});