# CourtOS

CourtOS is an arena operations dashboard for telemetry ingest, incident detection, court-overlay gating, and network-policy display. It runs in simulation mode by default and is designed for a single operator with no authentication in the MVP.

## Inspiration & NBA Technology Context

CourtOS is inspired by the next-generation technologies currently transforming the **NBA** and modern sports arenas (such as optical tracking cameras like Second Spectrum, real-time LED court projections, dynamic player biometrics, and software-defined venue networks). 

The platform acts as an operational extension designed to sit between the high-frequency tracking cameras and the physical court infrastructure. It ensures that as high-tech LED overlays (like visual lines, player stats, or advertisements) are projected onto the court, they are strictly gated by the game state (e.g. suppressed during live play to avoid distracting players, per NBA guidelines) and backed by intelligent safety limits.

## What CourtOS Does

- Accepts structured telemetry events via REST API
- Maintains a canonical arena state (game clock, play state, incidents, overlays, network allocation)
- Detects incidents when kinematic thresholds are breached
- Gates court overlays by play state (suppressed during live play)
- Displays simulated network-policy recommendations
- Pushes real-time state updates to the dashboard via SSE

## What CourtOS Is Not

- Not a hardware controller (all arena hardware interaction is simulated and labeled)
- Not a multi-user platform (single operator, no auth in MVP)
- Not a mobile app (minimum viewport: 1024 × 768)

## MVP Boundaries

| Feature | Simulation | Real Integration |
|---------|-----------|-----------------|
| Telemetry source | Built-in generator (1 event/sec) | External API callers |
| Network policy | `[SIMULATED]` label, recommendations only | SDN integration (future) |
| Court overlay | State-gated rendering, no projection | Projection adapter (future) |
| Storage | SQLite | PostgreSQL |
| Auth | None | RBAC (future) |

## Quick Start

```bash
docker compose up
# Dashboard: http://localhost:8000
# API docs: http://localhost:8000/docs
# Health: http://localhost:8000/api/v1/health
```

## Documentation

- [PRD.md](./PRD.md) — product requirements, MVP scope, acceptance criteria, risks, open questions
- [TRD.md](./TRD.md) — architecture, data models, API contracts, testing matrix, deployment config

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| Frontend | React 18+ (Vite) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Real-time | Server-Sent Events |
| Testing | pytest, Playwright, axe-core |

## Project Structure

```
courtos/               # Backend Python package
├── core/              # StateManager, SSE, logging, middlewares
├── db/                # Database adapters & migrations
├── models/            # Pydantic schemas and enums
├── services/          # Kinematic, game state, overlay, network, router
├── simulation/        # Scripted event generator loop
├── app.py             # FastAPI application and routes
├── config.py          # Settings config loader
└── seed.py            # Database seeding script
frontend/              # React TypeScript Vite client SPA
tests/                 # pytest suites (domain, integration, API validation)
```
