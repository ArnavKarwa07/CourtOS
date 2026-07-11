# CourtOS — Technical Requirements (MVP)

## 1. Technical Summary

CourtOS is a Python/FastAPI backend with a React frontend. It processes telemetry events, maintains a canonical arena state, detects incidents via threshold rules, gates court overlays by play state, and displays simulated network-policy recommendations. The dashboard receives real-time updates via Server-Sent Events (SSE).

## 2. Required Stack

### Backend

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.11+ |
| Framework | FastAPI | latest stable |
| Validation | Pydantic v2 | latest stable |
| DB (dev) | SQLite | via aiosqlite |
| DB (prod) | PostgreSQL | 15+ via asyncpg |
| Real-time | SSE | via sse-starlette |

### Frontend

| Component | Technology |
|-----------|-----------|
| Framework | React 18+ (Vite) |
| HTTP | fetch API |
| SSE | EventSource API |
| Testing | Playwright |

### Tooling

| Tool | Purpose |
|------|---------|
| pytest | Unit + integration tests |
| Playwright | E2E + accessibility tests |
| ruff | Linter + formatter |
| Docker Compose | Local deployment |
| axe-core | Accessibility audit |

## 3. System Architecture

### 3.1 Module Boundaries

```
┌─────────────────────────────────────────────┐
│                  Frontend                    │
│  React SPA served at /                       │
│  Connects to /api/v1/* and /api/v1/events/stream │
└───────────────────┬─────────────────────────┘
                    │ HTTP + SSE
┌───────────────────┴─────────────────────────┐
│               FastAPI Backend                │
│                                              │
│  ┌──────────┐  ┌──────────────┐  ┌────────┐ │
│  │ API Layer│→ │ Event Router │→ │Services│ │
│  └──────────┘  └──────────────┘  └────┬───┘ │
│                                       │     │
│  ┌───────────────┐  ┌────────────────┐│     │
│  │ State Manager │← │ Audit Logger   ││     │
│  └───────┬───────┘  └────────────────┘│     │
│          │                             │     │
│  ┌───────┴───────┐  ┌────────────────┐│     │
│  │  DB Adapter   │  │ SSE Publisher  ││     │
│  │ SQLite / PG   │  └────────────────┘│     │
│  └───────────────┘                     │     │
└─────────────────────────────────────────┘
```

### 3.2 Data Flow

1. Event arrives at `POST /api/v1/telemetry`.
2. Pydantic validates the payload.
3. Event Router classifies by `event_type` and dispatches to the appropriate domain service.
4. Domain service updates canonical state and may produce incidents.
5. State change and any new incidents are written to the database.
6. Audit logger records the action.
7. SSE publisher pushes a `state_update` event to all connected clients.
8. API returns `201` with the stored event.

### 3.3 Frontend Serving

In development: Vite dev server proxies `/api` to FastAPI (port 8000). In production: FastAPI serves the built React app from `/static` and the SPA fallback at `/`.

CORS: In development, FastAPI allows `http://localhost:5173`. In production, same-origin (no CORS needed).

## 4. Data Models

All models use Pydantic v2 `BaseModel`.

### 4.1 Enums

```python
from enum import StrEnum

class EventType(StrEnum):
    KINEMATIC = "kinematic"
    GAME_STATE = "game_state"
    NETWORK = "network"
    REVIEW = "review"

class PlayState(StrEnum):
    PRE_GAME = "pre_game"
    LIVE = "live"
    DEAD_BALL = "dead_ball"
    TIMEOUT = "timeout"
    HALFTIME = "halftime"
    POST_GAME = "post_game"

class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class IncidentStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"
```

### 4.2 Telemetry Event

```python
from pydantic import BaseModel, Field
from datetime import datetime

class KinematicPayload(BaseModel):
    player_id: str
    deceleration_g: float = Field(ge=0)
    velocity_ms: float = Field(ge=0)
    position_x: float
    position_y: float

class GameStatePayload(BaseModel):
    play_state: PlayState
    game_clock: str = Field(pattern=r"^\d{2}:\d{2}$")
    period: int = Field(ge=1, le=4)

class NetworkPayload(BaseModel):
    channel: str
    bandwidth_mbps: float = Field(ge=0)
    latency_ms: float = Field(ge=0)

class ReviewPayload(BaseModel):
    review_type: str
    description: str
    requested_by: str

class TelemetryEvent(BaseModel):
    event_id: str = Field(min_length=1)
    event_type: EventType
    timestamp: datetime
    source: str = Field(min_length=1)
    payload: KinematicPayload | GameStatePayload | NetworkPayload | ReviewPayload
```

### 4.3 Incident

```python
class Incident(BaseModel):
    incident_id: str
    severity: Severity
    category: str
    message: str
    created_at: datetime
    source_event_id: str
    status: IncidentStatus = IncidentStatus.ACTIVE
    resolved_at: datetime | None = None
```

### 4.4 Canonical State

```python
class NetworkAllocation(BaseModel):
    broadcast: float = Field(ge=0, le=100)
    telemetry: float = Field(ge=0, le=100)
    operations: float = Field(ge=0, le=100)
    emergency: float = Field(ge=0, le=100)
    simulated: bool = True

class OverlayState(BaseModel):
    mode: str  # "static" or "dynamic"
    active_overlays: list[str]  # list of overlay IDs currently rendered

class CourtOSState(BaseModel):
    game_clock: str = "00:00"
    period: int = 1
    play_state: PlayState = PlayState.PRE_GAME
    network_allocation: NetworkAllocation
    overlay: OverlayState
    active_incidents: list[Incident] = []
    last_event_id: str | None = None
    updated_at: datetime
```

## 5. Storage Schema

### 5.1 Tables

#### `telemetry_events`

| Column | Type | Constraint |
|--------|------|-----------|
| event_id | TEXT | PRIMARY KEY |
| event_type | TEXT | NOT NULL |
| timestamp | TIMESTAMP | NOT NULL |
| source | TEXT | NOT NULL |
| payload | JSON | NOT NULL |
| received_at | TIMESTAMP | DEFAULT NOW() |

#### `incidents`

| Column | Type | Constraint |
|--------|------|-----------|
| incident_id | TEXT | PRIMARY KEY |
| severity | TEXT | NOT NULL |
| category | TEXT | NOT NULL |
| message | TEXT | NOT NULL |
| created_at | TIMESTAMP | NOT NULL |
| source_event_id | TEXT | FK → telemetry_events |
| status | TEXT | DEFAULT 'active' |
| resolved_at | TIMESTAMP | NULL |

#### `audit_log`

| Column | Type | Constraint |
|--------|------|-----------|
| log_id | TEXT | PRIMARY KEY |
| action | TEXT | NOT NULL |
| details | JSON | NOT NULL |
| created_at | TIMESTAMP | DEFAULT NOW() |
| source_event_id | TEXT | NULL |

### 5.2 Database Adapter

The application uses an async adapter interface (`DatabaseAdapter`) with two implementations:

- `SqliteAdapter`: uses aiosqlite, creates tables on startup, stores in `./data/courtos.db`.
- `PostgresAdapter`: uses asyncpg, expects tables to exist (migration via SQL scripts).

Selected by `COURTOS_DB_BACKEND` environment variable (`sqlite` or `postgres`).

## 6. Domain Services

### 6.1 Event Router

- Validates `event_type` is a known `EventType` enum value.
- Dispatches to the matching service: `kinematic` → KinematicService, `game_state` → GameStateService, `network` → NetworkService, `review` → ReviewService.
- Returns the service result (state diff + any incidents created).

### 6.2 Kinematic Service

Evaluates `KinematicPayload` against threshold rules:

| Metric | Warning Threshold | Critical Threshold | Configurable |
|--------|------------------|--------------------|-------------|
| `deceleration_g` | > 5.0 | > 9.0 | Yes, via env |
| `velocity_ms` | > 12.0 | > 18.0 | Yes, via env |

When a threshold is breached:
1. Create an `Incident` with appropriate severity.
2. `category`: `"kinematic_threshold"`.
3. `message`: `"Player {player_id}: deceleration {value}g exceeds {threshold} threshold"`.

### 6.3 Game State Service

Processes `GameStatePayload`:
1. Updates `play_state`, `game_clock`, and `period` on canonical state.
2. Triggers overlay state re-evaluation (calls Overlay Service).
3. Writes audit log entry for play-state transitions.

### 6.4 Overlay Service

Enforces the overlay gating rules:
- `play_state == "live"` → set `overlay.mode = "static"`, clear `active_overlays`.
- Any other `play_state` → set `overlay.mode = "dynamic"`, allow overlays.
- Every mode transition is logged to `audit_log`.

### 6.5 Network Policy Service

Maintains a `NetworkAllocation` with 4 channels summing to 100%.

**Default allocation (no critical incidents):**

| Channel | Percentage |
|---------|-----------|
| broadcast | 40 |
| telemetry | 30 |
| operations | 20 |
| emergency | 10 |

**Emergency allocation (any active critical incident):**

| Channel | Percentage |
|---------|-----------|
| broadcast | 20 |
| telemetry | 20 |
| operations | 10 |
| emergency | 50 |

`simulated` is always `true` in MVP. All allocations are recommendations only.

## 7. API Specification

All endpoints are prefixed with `/api/v1`.

### 7.1 Health

`GET /api/v1/health`

Response `200`:
```json
{"status": "ok", "mode": "simulation", "version": "0.1.0"}
```

### 7.2 State

`GET /api/v1/state`

Response `200`: Returns the full `CourtOSState` JSON.

### 7.3 Telemetry Ingest

`POST /api/v1/telemetry`

Request body: `TelemetryEvent` JSON.

Response `201`:
```json
{"event_id": "...", "incidents_created": 0, "state_updated": true}
```

Response `422`:
```json
{"error": "validation_error", "details": [{"field": "event_type", "message": "..."}]}
```

### 7.4 List Incidents

`GET /api/v1/incidents?status=active|resolved|all`

Response `200`:
```json
{"incidents": [...], "total": 5}
```

### 7.5 Resolve Incident

`POST /api/v1/incidents/{incident_id}/resolve`

Response `200`:
```json
{"incident_id": "...", "status": "resolved", "resolved_at": "..."}
```

Response `404`:
```json
{"error": "not_found", "message": "Incident {id} not found"}
```

### 7.6 Court Overlay

`POST /api/v1/court/overlay`

Request body:
```json
{"action": "add" | "remove" | "clear", "overlay_id": "..."}
```

Response `200`: Updated `OverlayState`.

Response `409` (if `play_state` is `live` and action is `add`):
```json
{"error": "overlay_blocked", "message": "Cannot add overlays during live play"}
```

### 7.7 Network Allocation

`GET /api/v1/network/allocation`

Response `200`: Returns `NetworkAllocation` JSON.

### 7.8 Network Recalculate

`POST /api/v1/network/recalculate`

Response `200`: Returns updated `NetworkAllocation` JSON.

### 7.9 Audit Log

`GET /api/v1/audit?limit=50&offset=0`

Response `200`:
```json
{"entries": [...], "total": 120}
```

## 8. Real-Time Updates (SSE)

### 8.1 Endpoint

`GET /api/v1/events/stream`

Returns `text/event-stream`. Connection stays open.

### 8.2 Event Format

```
event: state_update
data: {"game_clock": "05:32", "play_state": "live", ...}

event: incident_created
data: {"incident_id": "...", "severity": "critical", ...}

event: incident_resolved
data: {"incident_id": "...", "resolved_at": "..."}

event: overlay_changed
data: {"mode": "static", "active_overlays": []}
```

### 8.3 Client Behavior

- Frontend uses `EventSource` API.
- On connection drop: reconnect with exponential backoff (1s, 2s, 4s, max 30s).
- `Last-Event-Id` header supported for resumption (using `last_event_id`).

## 9. Simulation Layer

### 9.1 Architecture

The simulation layer is a background async task that generates realistic telemetry events at a configurable interval (default: 1 event/sec).

```python
class SimulationRunner:
    async def run(self, interval_sec: float = 1.0):
        """Generate and ingest events on a loop."""
```

### 9.2 Event Generation

The simulator cycles through a scripted game scenario:

1. `pre_game` → generate network telemetry.
2. `live` → generate kinematic events (with occasional threshold breaches).
3. `dead_ball` / `timeout` → generate review events.
4. `halftime` → pause, then resume.
5. `post_game` → stop.

All generated events use `source: "simulation"` for filtering.

### 9.3 Seed Data

`python -m courtos.seed --count N` generates N deterministic events and ingests them. Used for testing and demos.

## 10. Validation Rules

| Rule | Field | Constraint | Error Code |
|------|-------|-----------|------------|
| V-1 | `event_id` | Non-empty string | 422 |
| V-2 | `event_type` | Must be a valid `EventType` | 422 |
| V-3 | `timestamp` | Valid ISO 8601 datetime | 422 |
| V-4 | `source` | Non-empty string | 422 |
| V-5 | `payload` | Must match the schema for the given `event_type` | 422 |
| V-6 | `deceleration_g` | >= 0 | 422 |
| V-7 | `game_clock` | Matches `MM:SS` format | 422 |
| V-8 | `period` | 1–4 | 422 |
| V-9 | `overlay action` | Cannot `add` during `live` play | 409 |
| V-10 | `incident_id` | Must exist for resolve | 404 |

## 11. Error Handling

### 11.1 Standard Error Response

All errors return this shape:

```json
{
  "error": "error_code",
  "message": "Human-readable description",
  "details": [{"field": "...", "message": "..."}]
}
```

`details` is only present for validation errors (422).

### 11.2 Status Code Usage

| Code | Meaning |
|------|---------|
| 200 | Success (read, update) |
| 201 | Created (telemetry ingest) |
| 400 | Bad request (malformed JSON) |
| 404 | Resource not found |
| 409 | Conflict (overlay during live play) |
| 422 | Validation error |
| 500 | Internal server error (no stack trace in response) |

### 11.3 Logging

- Structured JSON logs to stdout.
- Every request gets a `request_id` (UUID v4) added to all log entries.
- Errors log the full traceback server-side but return only `error` + `message` to the client.
- No PII or raw payload data in logs.

## 12. Frontend Requirements

### 12.1 Dashboard Panels

| Panel | Content | Update Mechanism |
|-------|---------|-----------------|
| Game Status | Clock, period, play state badge | SSE `state_update` |
| Active Incidents | Cards with severity, message, resolve button | SSE `incident_created` / `incident_resolved` |
| Court Overlay | Static/dynamic mode indicator, active overlay list | SSE `overlay_changed` |
| Network Policy | 4-channel bar chart with percentages, `[SIMULATED]` badge | SSE `state_update` |
| Telemetry Feed | Scrolling list of recent events (last 20) | SSE `state_update` |

### 12.2 Accessibility

| Requirement | Implementation |
|------------|---------------|
| Keyboard navigation | All interactive elements in tab order. Escape closes modals. |
| Focus indicators | 2px solid outline on `:focus-visible`, contrast ≥ 3:1 |
| Severity indicators | Icon + text label + color. Never color alone. |
| Live region | `aria-live="polite"` on incidents panel and game status |
| Headings | Each panel has `<h2>`. Heading hierarchy: `h1` (page) → `h2` (panel) → `h3` (card) |
| Minimum viewport | 1024 × 768. No horizontal scrollbar at this size. |

## 13. Testing Matrix

### 13.1 Unit Tests (pytest)

| Test | Input | Expected Output | Pass Criterion |
|------|-------|----------------|---------------|
| Valid kinematic event | `deceleration_g: 3.0` | No incident | Zero incidents returned |
| Warning threshold | `deceleration_g: 6.0` | Warning incident | Incident with `severity: "warning"` |
| Critical threshold | `deceleration_g: 10.0` | Critical incident | Incident with `severity: "critical"` |
| Play state transition | `game_state` with `play_state: "live"` | Overlay mode → static | `overlay.mode == "static"` |
| Network emergency mode | Active critical incident | Emergency allocation | `emergency == 50` |
| Invalid event type | `event_type: "bogus"` | ValidationError | Pydantic raises |
| Invalid game clock | `game_clock: "99:99"` is fine, but `"abc"` fails | ValidationError | Pydantic raises |

### 13.2 Integration Tests (pytest + test client)

| Test | Steps | Pass Criterion |
|------|-------|---------------|
| Ingest → state update | POST event, GET state | `last_event_id` matches |
| Ingest → incident → audit | POST kinematic (> 9g), GET incidents, GET audit | Incident exists, audit entry exists |
| Overlay gating | POST game_state `live`, POST overlay `add` | 409 response |
| Incident resolve | POST resolve, GET incidents | Status is `resolved` |

### 13.3 E2E Tests (Playwright)

| Test | Steps | Pass Criterion |
|------|-------|---------------|
| Dashboard loads | Navigate to `/` | All 5 panels visible |
| Telemetry flow | Submit event via UI or API, check dashboard | New event in feed within 2s |
| Incident card | Trigger threshold, check panel | Card with severity badge appears |
| Resolve incident | Click resolve button | Card moves to resolved |
| Keyboard navigation | Tab through entire page | All interactive elements reachable |
| Accessibility audit | Run axe-core | Zero critical/serious violations |

## 14. Deployment

### 14.1 Environment Variables

| Variable | Default | Description |
|----------|---------|------------|
| `COURTOS_MODE` | `simulation` | `simulation` or `real` |
| `COURTOS_DB_BACKEND` | `sqlite` | `sqlite` or `postgres` |
| `COURTOS_DB_URL` | `./data/courtos.db` | Database connection string |
| `COURTOS_HOST` | `0.0.0.0` | Server bind host |
| `COURTOS_PORT` | `8000` | Server bind port |
| `COURTOS_LOG_LEVEL` | `info` | Logging level |
| `COURTOS_SIM_INTERVAL` | `1.0` | Simulation event interval (seconds) |
| `COURTOS_DECEL_WARN` | `5.0` | Deceleration warning threshold (g) |
| `COURTOS_DECEL_CRIT` | `9.0` | Deceleration critical threshold (g) |
| `COURTOS_VELOCITY_WARN` | `12.0` | Velocity warning threshold (m/s) |
| `COURTOS_VELOCITY_CRIT` | `18.0` | Velocity critical threshold (m/s) |

### 14.2 Docker Compose

```yaml
# docker-compose.yml
services:
  courtos:
    build: .
    ports:
      - "8000:8000"
    environment:
      - COURTOS_MODE=simulation
      - COURTOS_DB_BACKEND=sqlite
    volumes:
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 10s
      timeout: 5s
      retries: 3
```

### 14.3 CI Pipeline

1. `ruff check .` — lint passes.
2. `ruff format --check .` — format passes.
3. `pytest` — all tests pass.
4. `npx playwright test` — E2E + accessibility passes.
5. `docker compose build` — image builds.

## 15. Open Technical Questions

| # | Question | Default |
|---|---------|---------|
| Q1 | Should SSE use `Last-Event-Id` for full resumption or just reconnect to latest state? | Reconnect to latest state (simpler). |
| Q2 | Should the simulation runner be a separate process or an async task in the main server? | Async task in the main server. |
| Q3 | What's the maximum number of concurrent SSE connections to support? | 10 (single operator + dev tools). |
| Q4 | Should we use Alembic for database migrations? | Not in MVP. Manual SQL scripts. |
| Q5 | Should the frontend use a state management library (Redux, Zustand)? | React Context + useReducer (minimal). |
