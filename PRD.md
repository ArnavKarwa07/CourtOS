# CourtOS — Product Requirements (MVP)

## 1. Product Summary

CourtOS is an arena operations dashboard that ingests telemetry events, maintains a canonical arena state, detects incidents, enforces court-overlay rules, and displays network-policy recommendations. It runs in simulation mode by default; real hardware adapters can be swapped in later without changing the core product.

## 2. MVP Scope

The first release ships these capabilities and nothing else:

| Area | Ships in MVP | Deferred |
|------|-------------|----------|
| Telemetry ingest | Structured events via REST API | Bulk import, file upload |
| State management | Single canonical state, event history | Multi-arena / multi-tenant |
| Incident detection | Threshold-based rules, manual resolve | Auto-escalation, ML-based detection |
| Court overlays | Play-state gating (static outline vs. dynamic) | AR/projection integration |
| Network policy | Simulated allocation display | Real SDN / network control |
| Dashboard | Single-page operator view with SSE updates | Role-specific views, saved layouts |
| Auth | None (single operator) | RBAC, login, session management |
| Storage | SQLite (dev) / PostgreSQL (prod) | Analytics warehouse, time-series DB |

## 3. Non-Goals

1. Direct control of physical arena hardware (projection, HVAC, lighting, network switches).
2. Real-time guarantees below 1 second for UI updates.
3. Multi-user roles, authentication, or authorization.
4. Mobile-optimized layout (below 1024 px viewport).
5. Injury-risk scoring or medical-response tracking.
6. Severity escalation logic (incidents are created at a fixed severity).
7. Historical analytics, trend charts, or data export.

## 4. Users

MVP supports one user type:

**Arena Operations Operator** — a single user who monitors the dashboard, reviews incidents, and verifies overlay and network-policy states. No login required. No concurrent sessions.

Future personas (Medical Reviewer, Broadcast Operator, Administrator) are documented in the TRD as v2 candidates.

## 5. System Modes

CourtOS operates in one of two modes, configured by environment variable.

| Capability | Simulation Mode (default) | Real Mode |
|-----------|--------------------------|-----------|
| Telemetry source | Built-in event generator (1 event/sec) | External API callers / adapters |
| Network policy | `[SIMULATED]` label on all allocations | Live SDN integration (future) |
| Court overlay | State-gated rendering, no projection | Projection adapter (future) |
| Storage | SQLite | PostgreSQL |
| Incidents | Deterministic threshold rules | Same rules, real payloads |

**Rule**: Every UI element that represents a simulated capability must display a visible `[SIMULATED]` badge. The badge must be included in the accessible label.

## 6. Play State

Play state is an enum, not a boolean. The following values are valid:

| Value | Overlays Allowed | Description |
|-------|-----------------|-------------|
| `pre_game` | Yes | Before the game starts |
| `live` | No (static court outline only) | Active play |
| `dead_ball` | Yes | Stoppage during play |
| `timeout` | Yes | Called timeout |
| `halftime` | Yes | Between periods |
| `post_game` | Yes | After the game ends |

**Rule**: When `play_state` is `live`, the system must suppress all dynamic overlays. Only a static court outline is rendered. When `play_state` is any other value, the system may display contextual overlays (review markers, telemetry highlights, heatmaps).

## 7. Core Workflows

### 7.1 Telemetry Ingest

1. Operator or service sends `POST /api/v1/telemetry` with a valid event payload.
2. Server validates the payload against the Pydantic schema.
3. On success: event is stored, canonical state is updated, SSE pushes state diff to dashboard. API returns `201` with the stored event.
4. On failure: API returns `422` with field-level error details. State is unchanged.

### 7.2 Incident Detection

1. After state update, the system evaluates threshold rules against the new state.
2. If a rule fires: an incident record is created with `severity`, `category`, `message`, and `source_event_id`.
3. The incident appears in the active-incidents panel on the dashboard via SSE.
4. The operator can resolve the incident via `POST /api/v1/incidents/{id}/resolve`.
5. Resolved incidents move to history. They are never deleted.

### 7.3 Court Overlay Gating

1. When a `game_state` telemetry event changes `play_state`, the overlay service re-evaluates.
2. If new state is `live`: all dynamic overlays are suppressed. Dashboard shows static court outline only.
3. If new state is anything else: dynamic overlays are enabled. Dashboard may render review markers.
4. Every overlay state change is written to the audit log.

### 7.4 Network Policy Display

1. The system maintains a 4-channel allocation model: `broadcast`, `telemetry`, `operations`, `emergency`.
2. Normal mode: default percentage split is displayed.
3. When any `critical` incident is active: the system displays an emergency reallocation recommendation.
4. All values are labeled `[SIMULATED]` in MVP.
5. Operator can trigger `POST /api/v1/network/recalculate` to recompute based on current incidents.

## 8. Functional Requirements

### 8.1 Telemetry

| ID | Requirement | Acceptance Criterion |
|----|------------|---------------------|
| T-1 | Accept events matching the schema | `POST /api/v1/telemetry` with valid payload → 201, event in DB |
| T-2 | Reject malformed events | Missing `event_type` → 422 with `{"field": "event_type", "error": "..."}` |
| T-3 | Reject unknown enum values | `event_type: "unknown"` → 422 |
| T-4 | Update canonical state on valid ingest | `GET /api/v1/state` returns updated `last_event_id` matching the ingested event |
| T-5 | Store all events in append-only history | `telemetry_events` table row count increases by 1 per valid ingest |
| T-6 | Push state update via SSE | Dashboard receives an SSE message within 1 second of ingest |

### 8.2 Incidents

| ID | Requirement | Acceptance Criterion |
|----|------------|---------------------|
| I-1 | Create incident on threshold breach | Kinematic event with `deceleration_g > 9.0` → new `critical` incident in DB |
| I-2 | Include all required fields | Incident record has `incident_id`, `severity`, `category`, `message`, `created_at`, `source_event_id` |
| I-3 | Display incident in dashboard | Active-incidents panel shows a card with severity badge, message, and timestamp |
| I-4 | Resolve incident via API | `POST /api/v1/incidents/{id}/resolve` → incident `status` changes to `resolved` |
| I-5 | Preserve resolved incidents | Resolved incidents appear in `GET /api/v1/incidents?status=resolved`, not deleted |

### 8.3 Court Overlays

| ID | Requirement | Acceptance Criterion |
|----|------------|---------------------|
| O-1 | Suppress overlays during live play | `play_state: "live"` → overlay panel shows only static court outline |
| O-2 | Enable overlays during dead ball | `play_state: "dead_ball"` → overlay panel accepts and renders dynamic overlays |
| O-3 | Log overlay state transitions | Each play-state change writes a row to `audit_log` with `action: "overlay_state_change"` |

### 8.4 Network Policy

| ID | Requirement | Acceptance Criterion |
|----|------------|---------------------|
| N-1 | Display default allocation | `GET /api/v1/network/allocation` returns 4 channels summing to 100% |
| N-2 | Shift to emergency on critical incident | With active critical incident, `broadcast` drops and `emergency` increases |
| N-3 | Label all values as simulated | Response includes `"simulated": true`. UI displays `[SIMULATED]` badge |
| N-4 | Recalculate on demand | `POST /api/v1/network/recalculate` recomputes based on current active incidents |

## 9. Accessibility Requirements

| ID | Requirement | Test Method |
|----|------------|------------|
| A-1 | All controls reachable by keyboard (Tab / Shift+Tab / Enter / Escape) | Playwright: tab through all interactive elements |
| A-2 | Visible focus indicator on every interactive element | Playwright: screenshot + CSS check for `:focus-visible` |
| A-3 | Severity conveyed by text label and icon, not color alone | Visual audit: grayscale screenshot must be readable |
| A-4 | Status changes announced via `aria-live` region | Playwright: check `aria-live="polite"` on status containers |
| A-5 | Every panel has an `<h2>` or `<h3>` heading | axe-core: heading-order rule passes |
| A-6 | No critical or serious axe-core violations | `npx playwright test --project=accessibility` passes |
| A-7 | Minimum viewport: 1024 × 768 | Playwright: render at 1024 × 768, no horizontal scroll |

## 10. Success Criteria

| # | Criterion | How to Verify |
|---|-----------|--------------|
| S-1 | Seed data (100 events) loads and processes without error | `python -m courtos.seed --count 100` exits 0 |
| S-2 | Simulation mode runs for 5 minutes without crash or state corruption | Simulation runner + `GET /api/v1/state` returns valid JSON after 5 min |
| S-3 | All unit and integration tests pass | `pytest` exits 0 |
| S-4 | E2E smoke test passes | Playwright test: ingest → incident → overlay → resolve |
| S-5 | axe-core accessibility audit passes | Zero critical/serious violations |
| S-6 | App starts with `docker compose up` and is usable at `localhost:8000` | Manual verification |
| S-7 | Every `[SIMULATED]` feature is visually labeled | Manual audit of all dashboard panels |

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Kinematic threshold values are wrong | High | Incorrect incidents | Make thresholds configurable via env vars; document as placeholder |
| SSE connections drop under load | Medium | Stale dashboard | Auto-reconnect in frontend with exponential backoff |
| PostgreSQL unavailable in prod | Low | Data loss | Health check on startup; fail fast with clear error |
| Scope creep into multi-user/auth | Medium | Delayed MVP | Non-goal list is explicit; defer to v2 |
| Accessibility regressions | Medium | Compliance failure | axe-core in CI pipeline; block merge on violations |

## 12. Open Questions

| # | Question | Default if Unanswered |
|---|---------|----------------------|
| Q1 | What sport does CourtOS target? | Basketball (inferred from "court", "dead ball", "halftime") |
| Q2 | Is there any real telemetry source for MVP? | No. 100% simulation. |
| Q3 | Where does MVP deploy? | Docker Compose, local only. Cloud deferred. |
| Q4 | What are the correct kinematic thresholds? | Deceleration > 5g = warning, > 9g = critical (placeholder) |
| Q5 | What WCAG level? | WCAG 2.1 AA |
| Q6 | Should the audit log be queryable via UI? | API only (`GET /api/v1/audit`). No UI viewer in MVP. |

## 13. Deployment Constraints

1. All runtime configuration via environment variables. No hardcoded secrets.
2. `.env.example` committed with variable names and descriptions, no values.
3. Application must start and serve the dashboard with zero external dependencies in simulation mode (SQLite, built-in event generator).
4. Structured JSON logging with request IDs. No PII in logs.
5. `GET /api/v1/health` returns `200` when the service is ready.
6. Graceful shutdown on SIGTERM.
