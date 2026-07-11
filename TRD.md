# CourtOS Technical Requirement Document

## 1. Technical Summary

CourtOS is a Python backend with a web UI that processes telemetry events, maintains a canonical arena state, and exposes operator workflows through a REST API.

The implementation must support two input modes:

1. Simulation mode for local development and testing.
2. Real integration mode for any future live feeds or hardware adapters.

Simulation mode is the default and must be fully functional on its own.

## 2. Recommended Stack

### Backend

- Python 3.11+
- FastAPI or a similar async web framework
- Pydantic for schema validation
- PostgreSQL for persistent state and audit history

### Frontend

- React or Next.js
- Accessible component library or carefully reviewed custom UI
- Keyboard-first interaction patterns

### Tooling

- pytest for tests
- Playwright for E2E and accessibility checks
- ruff or an equivalent linter
- env-based configuration

## 3. System Architecture

### 3.1 Data Flow

1. Telemetry event arrives through the API.
2. Input is validated against the event schema.
3. The router classifies the event by type.
4. Domain services update the canonical state.
5. Derived outputs are written to the audit log and returned to the UI.

### 3.2 Canonical State Model

```python
from typing import Any, TypedDict, Literal


class TelemetryEvent(TypedDict):
    event_id: str
    event_type: Literal["kinematic", "game_state", "network", "review"]
    timestamp: str
    source: str
    payload: dict[str, Any]


class Incident(TypedDict):
    incident_id: str
    severity: Literal["info", "warning", "critical"]
    category: str
    message: str
    created_at: str
    source_event_id: str


class CourtOSState(TypedDict):
    game_clock: str
    play_state: bool
    kinematic_telemetry: dict[str, Any]
    network_allocation: dict[str, float]
    court_visual_render: list[str]
    concourse_status: dict[str, Any]
    active_incidents: list[Incident]
    last_event_id: str | None
```

### 3.3 Storage Model

- `telemetry_events`: append-only event history
- `incidents`: active and resolved incidents
- `state_snapshots`: latest derived state per event or interval
- `audit_log`: operator actions and system decisions

## 4. Domain Services

### 4.1 Event Router

- Routes telemetry to the correct domain handler.
- Rejects unknown or malformed event types.
- Never mutates state directly without validation.

### 4.2 Kinematic Service

- Evaluates joint and deceleration payloads.
- Produces incident records when threshold rules are violated.
- Keeps the rule engine deterministic and testable.

### 4.3 Court Overlay Service

- Clears overlays while `play_state` is true.
- Allows contextual overlays while `play_state` is false.
- Tracks overlay actions in the audit log.

### 4.4 Network Policy Service

- Maintains the current allocation model.
- Applies emergency policy recommendations when critical incidents exist.
- Separates recommendation output from actual network control.

## 5. API Surface

### 5.1 Required Endpoints

- `GET /health`
- `GET /state`
- `POST /telemetry`
- `GET /incidents`
- `POST /incidents/{id}/resolve`
- `POST /court/overlay`
- `GET /network/allocation`
- `POST /network/recalculate`

### 5.2 Response Rules

- All endpoints return consistent JSON.
- Errors must be explicit but non-sensitive.
- Validation failures return 400 or 422.
- Unauthorized access returns 401 or 403.

## 6. Validation and Safety

1. Validate all request bodies with typed schemas.
2. Reject payloads with missing required fields.
3. Reject unknown enum values and invalid coordinate formats.
4. Sanitize any text shown back to the user.
5. Log internal errors without exposing stack traces to the client.

## 7. Accessibility Requirements for the UI

1. Every panel needs a visible heading.
2. Every status indicator needs text, not just color.
3. All tables need sortable or scannable labels where relevant.
4. Focus order must follow visual order.
5. Toasts and alerts must be announced to assistive technology.

## 8. Testing Requirements

### 8.1 Unit Tests

- Event validation
- Threshold detection
- State transition rules
- Network allocation calculations

### 8.2 Integration Tests

- Telemetry ingest updates state
- Incident creation writes audit history
- Overlay policy respects play state
- Network recalculation reflects incidents

### 8.3 E2E Tests

- Operator can submit an event
- Operator can review incidents
- Operator can verify overlay state
- Keyboard-only navigation works

### 8.4 Accessibility Tests

- No critical axe violations on core screens
- Keyboard focus visible everywhere
- Screen-reader labels present on all actions

## 9. Deployment and Operations

1. Keep configuration in environment variables.
2. Store secrets only in deployment secret stores.
3. Provide sample `.env.example` values with names only.
4. Add structured logging and request IDs.
5. Add health checks and rollback-safe deployment steps.

## 10. Implementation Notes

- Start with simulation mode and a small set of deterministic rules.
- Build the dashboard and API before adding more event types.
- Do not block release on unavailable hardware integrations.
- Keep the code modular so the real integrations can be added later.
