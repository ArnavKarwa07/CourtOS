# CourtOS Product Requirement Document

## 1. Product Summary

CourtOS is an arena operations dashboard for simulated or integrated venue telemetry. It helps operators monitor game-state changes, surface incident alerts, visualize court overlays during dead-ball moments, and review bandwidth policy recommendations in one place.

CourtOS must be deployable, accessible, and actually usable as software. Any hardware-specific behavior that is not available in the current environment must be represented as a clearly labeled simulation layer, not as a hidden dependency.

## 2. Product Goals

1. Provide a live operations dashboard that is understandable at a glance.
2. Ingest structured telemetry events and update a shared system state.
3. Detect incidents, explain them clearly, and preserve audit history.
4. Show court visual overlays only when the current game state allows it.
5. Keep the product accessible, keyboard navigable, responsive, and safe to deploy.

## 3. Non-Goals

1. Direct control of physical arena hardware unless a real integration exists.
2. Unverified claims about sub-millisecond or guaranteed real-world timing.
3. Promotional or speculative features that cannot be tested end to end.
4. Complex analytics that do not improve the primary operator workflow.

## 4. Primary Users

### 4.1 Arena Operations Operator

Monitors incoming telemetry, current play state, incident alerts, and operational status.

### 4.2 Medical / Safety Reviewer

Reviews injury-risk flags, confirms incident severity, and tracks response actions.

### 4.3 Broadcast / Venue Systems Operator

Reviews overlay eligibility, network policy status, and facility alert conditions.

### 4.4 Administrator

Manages configuration, access, data retention, and deployment settings.

## 5. Core User Experience

### 5.1 Operations Dashboard

The main screen must show current game clock, play state, active incidents, bandwidth allocation, court overlay status, and recent telemetry.

### 5.2 Telemetry Ingest

Users or services can submit structured telemetry events. The system validates events, stores them, and updates derived state.

### 5.3 Incident Review

When telemetry crosses a threshold, CourtOS creates an incident card with severity, reason, timestamp, and suggested action.

### 5.4 Court Overlay Review

The system can render contextual overlays only when play is dead. While play is live, overlays must be cleared except for regulatory markings.

### 5.5 Network Policy View

Operators can see the current bandwidth policy and any emergency reallocation triggered by incidents.

## 6. Functional Requirements

### 6.1 Telemetry and State

1. The system must accept structured telemetry events with a stable schema.
2. The system must validate inputs before state mutation.
3. The system must keep a single source of truth for current arena state.
4. The system must retain an event history for auditing and debugging.

### 6.2 Incident Detection

1. The system must create an incident when a telemetry rule is violated.
2. The incident record must include type, severity, source event, and human-readable explanation.
3. The system must not silently drop malformed telemetry; it must log and surface validation errors safely.

### 6.3 Court Overlay Rules

1. When play is live, the court overlay must be cleared or limited to approved baseline markings.
2. When play is dead, the system may display contextual graphics, review markers, and telemetry highlights.
3. Review and highlighting actions must be recorded in the audit trail.

### 6.4 Network Policy Rules

1. The system must display a default policy distribution for normal operations.
2. When a critical incident exists, the system must recommend emergency-priority allocation.
3. Any automatic network change must be clearly labeled as simulated unless a real integration is present.

### 6.5 Accessibility and Usability

1. Every user-facing control must be keyboard accessible.
2. Every state change must have clear text feedback.
3. Color must never be the only signal for severity or status.
4. The interface must work on mobile and desktop screen sizes.

## 7. Success Criteria

1. A user can ingest telemetry, see a state update, and read the resulting incident or overlay decision.
2. A user can navigate the app without a mouse.
3. Failed validation never corrupts the shared state.
4. The app can be deployed and exercised with realistic sample data.
5. The docs clearly separate real features from simulation.

## 8. Acceptance Criteria by Area

### 8.1 Telemetry

- Valid event: accepted and stored.
- Invalid event: rejected with a clear error.

### 8.2 Incidents

- Threshold breach: incident created and visible.
- Severity escalation: reflected in the UI and history.

### 8.3 Overlays

- Live play: overlay disabled.
- Dead ball: overlay enabled.

### 8.4 Accessibility

- Full keyboard navigation.
- Visible focus states.
- Screen-reader friendly labels and announcements.

## 9. Deployment Constraints

1. Production behavior must be configurable by environment variables.
2. Secrets must never be committed to the repository.
3. The application must fail safely if a dependency is unavailable.
4. Logging must avoid sensitive payload data.
