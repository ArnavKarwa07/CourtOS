import React, { useState, useEffect } from 'react';
import type { OverlayState } from '../types';

interface CourtOverlayViewProps {
  overlay: OverlayState;
  playState: string;
  addOverlay: (id: string) => void;
  removeOverlay: (id: string) => void;
  currentMode: 'simulation' | 'realtime';
}

export const CourtOverlayView = React.memo(({ overlay, playState, addOverlay, removeOverlay, currentMode }: CourtOverlayViewProps) => {
  const [newOverlayId, setNewOverlayId] = useState("");
  const [heatmapData, setHeatmapData] = useState<number[][]>(() => {
    const rows = 6;
    const cols = 10;
    return Array.from({ length: rows }, () => Array(cols).fill(0));
  });

  useEffect(() => {
    if (currentMode !== "simulation") return;
    const interval = setInterval(() => {
      setHeatmapData(prev => {
        const next = prev.map(row => row.map(v => Math.max(0, v * 0.85)));
        if (playState === "live") {
          for (let k = 0; k < 3; k++) {
            const r = Math.floor(Math.random() * 6);
            const c = Math.floor(Math.random() * 10);
            next[r][c] = Math.min(1, next[r][c] + 0.3 + Math.random() * 0.5);
          }
          next[Math.floor(Math.random() * 3) + 1][Math.floor(Math.random() * 2)] += 0.4;
          next[Math.floor(Math.random() * 3) + 1][8 + Math.floor(Math.random() * 2)] += 0.4;
        } else if (playState === "dead_ball" || playState === "timeout") {
          const r = 2 + Math.floor(Math.random() * 2);
          const c = 4 + Math.floor(Math.random() * 2);
          next[r][c] = Math.min(1, next[r][c] + 0.2);
        } else if (playState === "halftime") {
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
  }, [currentMode, playState]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    addOverlay(newOverlayId);
    setNewOverlayId("");
  };

  return (
    <section className="panel" style={{ gridArea: "overlay" }} aria-labelledby="overlay-heading">
      <div className="panel-header">
        <h2 id="overlay-heading" className="panel-title">Court Overlay Controls</h2>
        <span className={`badge ${overlay.mode === 'static' ? 'badge-critical' : 'badge-info'}`}>Mode: {overlay.mode.toUpperCase()}</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 120px", gap: "var(--space-4)" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          {overlay.active_overlays.length === 0 ? (
            <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", textAlign: "center", padding: "var(--space-4) 0" }}>
              {overlay.mode === "static" ? "🔒 Overlays suppressed during live play." : "No active overlays."}
            </p>
          ) : (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
              {overlay.active_overlays.map((overlayId) => (
                <span key={overlayId} className="badge badge-info" style={{ paddingRight: "var(--space-1)", textTransform: "none", display: "inline-flex", alignItems: "center" }}>
                  {overlayId}
                  <button style={{ border: "none", background: "transparent", cursor: "pointer", color: "inherit", marginLeft: "var(--space-1)", padding: "var(--space-1)" }} onClick={() => removeOverlay(overlayId)} aria-label={`Remove overlay ${overlayId}`}>✕</button>
                </span>
              ))}
            </div>
          )}
          <form onSubmit={handleSubmit} style={{ display: "flex", gap: "var(--space-2)" }}>
            <input type="text" className="btn" style={{ flexGrow: 1, textAlign: "left", cursor: "text" }} placeholder="Enter overlay ID (e.g. heatmap-q2)" value={newOverlayId} onChange={(e) => setNewOverlayId(e.target.value)} disabled={overlay.mode === "static"} aria-label="New overlay name input" />
            <button type="submit" className="btn" disabled={overlay.mode === "static" || !newOverlayId.trim()} aria-label="Add overlay button">Add</button>
          </form>
        </div>
        <svg viewBox="0 0 100 60" className="court-svg" aria-label="Basketball court diagram with live heatmap">
          <defs>
            <radialGradient id="heatGlow">
              <stop offset="0%" stopColor="rgba(239,68,68,0.8)" />
              <stop offset="50%" stopColor="rgba(245,158,11,0.4)" />
              <stop offset="100%" stopColor="rgba(96,165,250,0)" />
            </radialGradient>
          </defs>
          {heatmapData.map((row, ri) => row.map((val, ci) => {
            if (val < 0.05) return null;
            const x = ci * 10;
            const y = ri * 10;
            const r = val > 0.7 ? 0 : val > 0.4 ? 120 : 200;
            const g = val > 0.7 ? Math.floor(68 + (1 - val) * 100) : val > 0.4 ? Math.floor(158 - val * 60) : Math.floor(165 + val * 50);
            const b = val > 0.7 ? 68 : val > 0.4 ? 11 : 250;
            return <rect key={`heat-${ri}-${ci}`} x={x} y={y} width="10" height="10" fill={`rgba(${r},${g},${b},${val * 0.7})`} rx="2" style={{ transition: "fill 0.4s ease" }} />;
          }))}
          <rect x="0" y="0" width="100" height="60" fill="none" stroke="var(--color-border)" strokeWidth="2" />
          <line x1="50" y1="0" x2="50" y2="60" stroke="var(--color-border)" strokeWidth="2" />
          <circle cx="50" cy="30" r="10" fill="none" stroke="var(--color-border)" strokeWidth="2" />
          <rect x="0" y="15" width="19" height="30" fill="none" stroke="var(--color-border)" strokeWidth="2" />
          <rect x="81" y="15" width="19" height="30" fill="none" stroke="var(--color-border)" strokeWidth="2" />
          {overlay.active_overlays.includes("paint") && <rect x="0" y="15" width="19" height="30" fill="rgba(96, 165, 250, 0.3)" />}
          {overlay.active_overlays.map((id, index) => <circle key={id} cx={30 + index * 15} cy="30" r="4" fill="rgba(96, 165, 250, 0.6)" stroke="var(--color-focus)" strokeWidth="1" />)}
        </svg>
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
  );
});
