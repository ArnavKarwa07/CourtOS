# CourtOS

CourtOS is an arena operations dashboard for telemetry, incidents, court overlays, and network policy review. The current implementation target is a usable, accessible, production-deployable web application with a real data flow and a clear simulation path for any integrations that do not exist yet.

## What CourtOS Does

- Accepts structured telemetry events
- Updates a canonical arena state
- Detects and displays incidents
- Enforces court overlay rules based on play state
- Shows network policy recommendations for normal and emergency conditions

## What CourtOS Is Not

- It is not a promise of direct control over physical arena hardware
- It is not a speculative showcase with fake buttons
- It is not a demo-only app with no deployment path

## Product Rules

1. The UI must be accessible, keyboard navigable, and mobile friendly.
2. All important states must be understandable without color alone.
3. Validation must happen on the backend, not only in the browser.
4. Errors must be clear, actionable, and non-technical.
5. Simulation mode must work end to end without missing services.

## Core Workflow

1. Receive telemetry.
2. Validate and store the event.
3. Update state and derive incidents or overlay changes.
4. Surface the result in the dashboard and audit log.
5. Let the operator resolve or review the outcome.

## Documentation Map

- [PRD.md](./PRD.md): product goals, users, workflows, acceptance criteria
- [TRD.md](./TRD.md): architecture, data model, API surface, validation, tests
- [PROMPTS.md](./PROMPTS.md): project-specific prompt order for AI-assisted work

## Project-Specific Prompt Order

Use this order for CourtOS work. It is different from the generic prompt library order because CourtOS needs implementation clarity, accessibility, and deployment readiness early.

1. `00-format-rules.md` - establish output conventions and placeholder discipline
2. `10-documentation-standards.md` - rewrite/maintain the docs before coding
3. `09-api-design.md` - lock down the telemetry and operations API surface
4. `08-database-design.md` - define the canonical state, events, and audit history
5. `02-uiux-research-design.md` - design the operator flows and accessibility requirements
6. `11-frontend-quality-system.md` - standardize feedback copy, typography, and titles
7. `01-security-comprehensive.md` - review auth, validation, secrets, and exposure risks
8. `07-testing-qa.md` - define unit, integration, E2E, and accessibility tests
9. `06-performance-optimization.md` - check render speed, API latency, and dependency resilience
10. `04-pre-deployment-checklists.md` - verify release readiness before shipping
11. `05-saas-launch-checklist.md` - only if CourtOS ships as a SaaS product with billing or public launch requirements
12. `03-3d-web-building.md` - only if a marketing site or hero visualization needs cinematic assets

## CourtOS Prompt Packs

### Phase 1: Spec and Structure

- docs rewrite
- API design
- database design

### Phase 2: Experience and Accessibility

- UX review
- frontend quality system
- documentation standards

### Phase 3: Hardening

- security review
- testing and QA
- performance optimization

### Phase 4: Release

- pre-deployment checklist
- launch checklist if applicable

## Prompt Order Notes

- Run security and testing prompts again after major code changes.
- Keep simulation and real integration prompts separate.
- Do not treat visual polish as complete until accessibility is verified.

## Next Build Decision

If the next step is implementation, start with the telemetry API and the dashboard state model. If the next step is product review, use the docs above as the source of truth.
