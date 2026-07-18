import React from 'react';
import type { NetworkAllocation } from '../types';

interface NetworkAllocationPanelProps {
  allocation: NetworkAllocation;
  recalculateNetwork: () => void;
  isRecalculating: boolean;
}

export const NetworkAllocationPanel = React.memo(({ allocation, recalculateNetwork, isRecalculating }: NetworkAllocationPanelProps) => {
  return (
    <section className="panel" style={{ gridArea: "network" }} aria-labelledby="network-heading">
      <div className="panel-header">
        <h2 id="network-heading" className="panel-title">Network Allocation Recommendations</h2>
        <span className="badge badge-simulated">[SIMULATED]</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        {(["broadcast", "telemetry", "operations", "emergency"] as const).map((channel) => {
          const val = allocation[channel];
          return (
            <div key={channel} style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-sm)" }}>
                <span style={{ textTransform: "capitalize", fontWeight: "500" }}>{channel}</span>
                <span style={{ fontFamily: "var(--font-mono)" }}>{val}%</span>
              </div>
              <div role="meter" aria-label={`${channel} allocation: ${val}%`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={val} style={{ height: "10px", backgroundColor: "var(--color-surface-elevated)", borderRadius: "5px", overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${val}%`, backgroundColor: channel === "emergency" && val > 10 ? "var(--color-severity-critical)" : "var(--color-focus)", transition: "width 0.5s ease-in-out" }} />
              </div>
            </div>
          );
        })}
        <button className="btn" style={{ marginTop: "var(--space-2)" }} onClick={recalculateNetwork} disabled={isRecalculating} aria-label="Force network policy recalculation">
          {isRecalculating ? "Recalculating..." : "Recalculate Allocations"}
        </button>
      </div>
    </section>
  );
});
