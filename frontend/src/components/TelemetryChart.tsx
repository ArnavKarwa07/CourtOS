import React from 'react';
import type { TelemetryEvent } from '../types';

interface TelemetryChartProps {
  telemetryFeed: TelemetryEvent[];
}

export const TelemetryChart = React.memo(({ telemetryFeed }: TelemetryChartProps) => {
  return (
    <section className="panel" style={{ gridArea: "feed", maxHeight: "350px" }} aria-labelledby="feed-heading">
      <div className="panel-header">
        <h2 id="feed-heading" className="panel-title">Telemetry & Events Feed</h2>
      </div>
      <ul className="scroll-list" style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        {telemetryFeed.length === 0 ? (
          <li style={{ textAlign: "center", color: "var(--color-text-secondary)", padding: "var(--space-6) 0" }}>No events received. Waiting for simulation stream...</li>
        ) : (
          telemetryFeed.map((event, idx) => (
            <li key={event.event_id + idx} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "var(--text-xs)", padding: "var(--space-2)", borderBottom: "1px solid var(--color-border)", fontFamily: "var(--font-mono)" }} aria-label={`${event.event_type} event from ${event.source} at ${new Date(event.timestamp).toLocaleTimeString()}`}>
              <span style={{ fontWeight: "bold", color: "var(--color-focus)" }}>[{event.event_type.toUpperCase()}]</span>
              <span style={{ color: "var(--color-text-secondary)" }}>src: {event.source}</span>
              <span>{new Date(event.timestamp).toLocaleTimeString()}</span>
            </li>
          ))
        )}
      </ul>
    </section>
  );
});
