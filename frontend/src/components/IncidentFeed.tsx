import React from 'react';
import type { Incident } from '../types';

interface IncidentFeedProps {
  incidents: Incident[];
  resolvingIds: string[];
  resolveIncident: (id: string) => void;
}

export const IncidentFeed = React.memo(({ incidents, resolvingIds, resolveIncident }: IncidentFeedProps) => {
  return (
    <section className="panel" style={{ gridArea: "incidents", maxHeight: "550px" }} aria-labelledby="incidents-heading">
      <div className="panel-header">
        <h2 id="incidents-heading" className="panel-title">Active Incidents ({incidents.length})</h2>
      </div>
      <ul className="scroll-list" style={{ flexGrow: 1, display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        {incidents.length === 0 ? (
          <li style={{ textAlign: "center", color: "var(--color-text-secondary)", padding: "var(--space-8) 0" }}>No active incidents. Venue telemetry is normal.</li>
        ) : (
          incidents.map((incident) => (
            <li key={incident.incident_id} className="panel" style={{ backgroundColor: "var(--color-surface-elevated)", borderLeft: `4px solid ${incident.severity === 'critical' ? 'var(--color-severity-critical)' : incident.severity === 'warning' ? 'var(--color-severity-warning)' : 'var(--color-severity-info)'}`, gap: "var(--space-2)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className={`badge ${incident.severity === 'critical' ? 'badge-critical' : incident.severity === 'warning' ? 'badge-warning' : 'badge-info'}`}>{incident.severity}</span>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", fontFamily: "var(--font-mono)" }}>{incident.incident_id.substring(0, 8)}</span>
              </div>
              <p style={{ fontSize: "var(--text-sm)", fontWeight: "500" }}>{incident.message}</p>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "var(--space-2)" }}>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)" }}>Category: {incident.category}</span>
                <button className="btn" style={{ padding: "4px 12px", fontSize: "var(--text-xs)" }} onClick={() => resolveIncident(incident.incident_id)} disabled={resolvingIds.includes(incident.incident_id)} aria-label={`Resolve incident: ${incident.message}`}>
                  {resolvingIds.includes(incident.incident_id) ? "Resolving..." : "Resolve"}
                </button>
              </div>
            </li>
          ))
        )}
      </ul>
    </section>
  );
});
