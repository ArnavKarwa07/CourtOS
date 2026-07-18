import asyncio
import logging
from typing import Optional
from fastapi import FastAPI, Request, status, Query, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from courtos.config import Settings
from courtos.db.sqlite import SqliteAdapter
from courtos.db.postgres import PostgresAdapter
from courtos.models import TelemetryEvent
import uuid
from datetime import datetime, timezone
from courtos.models.state import OverlayState, NetworkAllocation
from courtos.models.enums import PlayState
from courtos.services import KinematicService, GameStateService, OverlayService, NetworkPolicyService, EventRouter
from courtos.core import StateManager, SSEPublisher, RequestIdMiddleware, SecurityHeadersMiddleware, CSRFShieldMiddleware, RateLimitMiddleware, configure_logging
from courtos.simulation import SimulationRunner

# Instantiate configuration
settings = Settings()
configure_logging(settings.log_level)
logger = logging.getLogger("courtos.app")

# Initialize database adapter
if settings.db_backend == "sqlite":
    db_adapter = SqliteAdapter(settings.db_url)
else:
    db_adapter = PostgresAdapter(settings.db_url)

# Initialize core publishers and services
sse_publisher = SSEPublisher()
overlay_service = OverlayService()
kinematic_service = KinematicService(
    decel_warn=settings.decel_warn,
    decel_crit=settings.decel_crit,
    velocity_warn=settings.velocity_warn,
    velocity_crit=settings.velocity_crit
)
game_state_service = GameStateService(overlay_service)
network_service = NetworkPolicyService()
event_router = EventRouter(kinematic_service, game_state_service, network_service)

# Initialize State Manager
state_manager = StateManager(db_adapter, sse_publisher, event_router, network_service)

# Instantiate background simulation runner
sim_runner: Optional[SimulationRunner] = None

# Initialize AI Assist engines
import json
from pydantic import BaseModel
from courtos.ai.assistant import OperatorAssistant
from courtos.ai.summarizer import IncidentSummarizer
from courtos.ai.commentator import SportsCommentator

assistant = OperatorAssistant(db_adapter)
summarizer = IncidentSummarizer()
commentator = SportsCommentator()

app = FastAPI(
    title="CourtOS API",
    version="0.1.0",
    description="Arena operations dashboard telemetry and incident gating engine"
)

# Apply CORS middleware config based on mode
cors_origins = []
if settings.mode == "simulation":
    # Development origins allowed
    cors_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.mode == "simulation" else cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Requested-With", "X-Request-ID"]
)

# Apply custom middlewares
app.add_middleware(RateLimitMiddleware, max_requests=300, window_seconds=60)
app.add_middleware(CSRFShieldMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)

@app.on_event("startup")
async def startup_event():
    # 1. Initialize DB adapter
    await db_adapter.initialize()
    
    # 2. Start SSE keepalives
    await sse_publisher.start()
    
    # 3. Load snapshot & replay logs to rebuild canonical state
    await state_manager.initialize()
    
    # 4. Start simulation runner if mode is simulation
    global sim_runner
    if settings.mode == "simulation":
        # Use PORT env var (Cloud Run sets this to 8080) rather than settings.port
        import os as _os
        actual_port = int(_os.environ.get("PORT", settings.port))
        sim_runner = SimulationRunner(actual_port, settings.sim_interval)
        # Give server a half second to bind port before launching http client loop
        await asyncio.sleep(0.5)
        await sim_runner.start()
        
    # 5. Append catchall route at the end of routing stack so standard API / docs routes match first
    if os.path.exists(frontend_dist):
        app.router.add_api_route("/{catchall:path}", serve_spa, methods=["GET"])
        
    logger.info("Application startup completed", extra={"details": {"mode": settings.mode, "db": settings.db_backend}})

@app.on_event("shutdown")
async def shutdown_event():
    # 1. Stop simulation runner
    global sim_runner
    if sim_runner:
        await sim_runner.stop()
        
    # 2. Stop SSE publisher queues
    await sse_publisher.stop()
    
    # 3. Close database pools
    await db_adapter.close()
    
    logger.info("Application shutdown completed")

# Exception handling for validation errors matching TRD JSON shape
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = []
    for error in exc.errors():
        loc = [str(x) for x in error.get("loc", [])]
        if loc and loc[0] == "body":
            loc = loc[1:]
        # Prepend payload prefix to field mapping if error is from sub-model level
        if loc and loc[0] not in ("event_id", "event_type", "timestamp", "source", "payload"):
            loc = ["payload"] + loc
        field_path = ".".join(loc)
        details.append({
            "field": field_path,
            "message": error.get("msg", "Value is invalid")
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "Request validation failed",
            "details": details
        }
    )

# REST Endpoint Handlers
@app.get("/api/v1/health")
async def get_health():
    # Verify DB health
    try:
        if settings.db_backend == "sqlite":
            import aiosqlite
            async with aiosqlite.connect(settings.db_url) as conn:
                await conn.execute("SELECT 1;")
        else:
            async with db_adapter._pool.acquire() as conn:
                await conn.execute("SELECT 1;")
        db_ok = True
    except Exception as e:
        logger.error("Healthcheck DB failure", exc_info=e)
        db_ok = False
        
    if not db_ok:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "degraded",
                "mode": settings.mode,
                "version": "0.1.0",
                "db_backend": settings.db_backend,
                "error": "Database connection failed"
            }
        )
        
    return {
        "status": "ok",
        "mode": settings.mode,
        "version": "0.1.0",
        "db_backend": settings.db_backend,
        "uptime_seconds": 0  # Simplified for MVP
    }

@app.get("/api/v1/state")
async def get_state():
    return state_manager.get_state()

@app.post("/api/v1/telemetry", status_code=status.HTTP_201_CREATED)
async def ingest_telemetry(event: TelemetryEvent, request: Request):
    try:
        count, new_incidents = await state_manager.process_event(event)
        
        incidents_data = []
        for incident in new_incidents:
            incidents_data.append({
                "incident_id": incident.incident_id,
                "severity": incident.severity,
                "category": incident.category,
                "message": incident.message
            })
            
        # Execute LangGraph sports commentator
        try:
            event_dict = {
                "event_id": event.event_id,
                "event_type": event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
                "timestamp": event.timestamp.isoformat() if hasattr(event.timestamp, "isoformat") else str(event.timestamp),
                "source": event.source,
                "payload": event.payload.model_dump() if hasattr(event.payload, "model_dump") else event.payload
            }
            commentary_text = await commentator.commentate(event_dict)
            await sse_publisher.broadcast("commentary_event", {"commentary": commentary_text, "timestamp": event_dict["timestamp"]})
        except Exception as ai_err:
            logger.error("Failed to generate AI sports commentary", exc_info=ai_err)

        return {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "state_updated": True,
            "incidents_created": count,
            "incidents": incidents_data
        }
    except ValueError as e:
        if str(e) == "DuplicateEvent":
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "error": "duplicate_event",
                    "message": f"Event {event.event_id} already exists"
                }
            )
        raise e

@app.get("/api/v1/incidents")
async def list_incidents(
    status_filter: str = Query("all", alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    filt = None if status_filter == "all" else status_filter
    incidents = await db_adapter.get_incidents(status=filt)
    
    # Calculate offset slice
    start = offset
    end = offset + limit
    sliced = incidents[start:end]
    
    return {
        "incidents": sliced,
        "total": len(incidents),
        "limit": limit,
        "offset": offset
    }

@app.post("/api/v1/incidents/{incident_id}/resolve")
async def resolve_incident(incident_id: str, request: Request):
    try:
        req_id = getattr(request.state, "request_id", None)
        resolved = await state_manager.resolve_incident(incident_id, request_id=req_id)
        
        # Compile incident metadata and execute LangGraph summarizer
        try:
            incident_dict = {
                "incident_id": resolved.incident_id,
                "severity": resolved.severity.value if hasattr(resolved.severity, "value") else str(resolved.severity),
                "category": resolved.category,
                "message": resolved.message,
                "created_at": resolved.created_at.isoformat() if hasattr(resolved.created_at, "isoformat") else str(resolved.created_at),
                "status": "resolved"
            }
            summary = await summarizer.summarize(incident_dict)
            await db_adapter.log_audit(
                action="incident_summarized",
                actor="system_ai",
                details={"summary": summary, "incident_id": incident_id},
                request_id=req_id
            )
        except Exception as ai_err:
            logger.error("Failed to generate AI incident summary", exc_info=ai_err)

        return {
            "incident_id": resolved.incident_id,
            "status": "resolved",
            "resolved_at": resolved.resolved_at.isoformat() if resolved.resolved_at else None
        }
    except ValueError as e:
        if str(e) == "NotFound":
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": "not_found",
                    "message": f"Incident {incident_id} not found"
                }
            )
        raise e

@app.post("/api/v1/court/overlay")
async def update_court_overlay(request: Request):
    body = await request.json()
    action = body.get("action")
    overlay_id = body.get("overlay_id", "")
    
    if action not in ("add", "remove", "clear"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "validation_error",
                "message": "Action must be add, remove, or clear"
            }
        )
        
    try:
        req_id = getattr(request.state, "request_id", None)
        new_overlay = await state_manager.update_overlay_state(action, overlay_id, request_id=req_id)
        return new_overlay
    except ValueError as e:
        err_str = str(e)
        if err_str == "OverlayBlocked":
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "error": "overlay_blocked",
                    "message": "Cannot add overlays during live play"
                }
            )
        elif "not active" in err_str:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": "not_found",
                    "message": err_str
                }
            )
        raise e

class AIAssistantRequest(BaseModel):
    query: str

@app.post("/api/v1/ai/assistant")
async def ai_assistant(req: AIAssistantRequest):
    try:
        reply = await assistant.ask(req.query)
        return {"reply": reply}
    except Exception as e:
        logger.error("AI Assistant failure", exc_info=e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "ai_error", "message": f"AI Assistant failed: {str(e)}"}
        )


@app.get("/api/v1/network/allocation")
async def get_network_allocation():
    state = state_manager.get_state()
    has_critical = any(
        i.severity == "critical" and i.status == "active"
        for i in state.active_incidents
    )
    return {
        "broadcast": state.network_allocation.broadcast,
        "telemetry": state.network_allocation.telemetry,
        "operations": state.network_allocation.operations,
        "emergency": state.network_allocation.emergency,
        "simulated": state.network_allocation.simulated,
        "mode": "emergency" if has_critical else "normal"
    }

@app.post("/api/v1/network/recalculate")
async def post_network_recalculate(request: Request):
    req_id = getattr(request.state, "request_id", None)
    allocation = await state_manager.force_network_recalculate(request_id=req_id)
    
    state = state_manager.get_state()
    has_critical = any(
        i.severity == "critical" and i.status == "active"
        for i in state.active_incidents
    )
    return {
        "broadcast": allocation.broadcast,
        "telemetry": allocation.telemetry,
        "operations": allocation.operations,
        "emergency": allocation.emergency,
        "simulated": allocation.simulated,
        "mode": "emergency" if has_critical else "normal"
    }

@app.get("/api/v1/audit")
async def get_audit_log(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    entries = await db_adapter.get_audit_entries(limit=limit, offset=offset)
    
    total_count = 0
    if settings.db_backend == "sqlite":
        import aiosqlite
        async with aiosqlite.connect(settings.db_url) as conn:
            async with conn.execute("SELECT COUNT(*) FROM audit_log;") as cursor:
                row = await cursor.fetchone()
                if row:
                    total_count = row[0]
    else:
        async with db_adapter._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) as count FROM audit_log;")
            if row:
                total_count = row["count"]
                    
    return {
        "entries": entries,
        "total": total_count,
        "limit": limit,
        "offset": offset
    }

@app.get("/api/v1/events/stream")
async def get_events_stream(request: Request):
    async def sse_event_generator():
        # First send the initial state snapshot on connect
        state_json = state_manager.get_state().model_dump_json()
        yield {
            "event": "state_snapshot",
            "data": state_json,
            "id": state_manager.get_state().last_event_id or "init"
        }
        
        # Subscribe to new updates
        async for sse_event in sse_publisher.subscribe():
            yield sse_event
            
    return EventSourceResponse(sse_event_generator())



# Serve frontend static assets same-origin in production
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
frontend_assets = os.path.join(frontend_dist, "assets")
if os.path.exists(frontend_assets):
    app.mount("/assets", StaticFiles(directory=frontend_assets), name="assets")

async def serve_spa(catchall: str):
    # Prevent intercepting API routes that are 404
    if catchall.startswith("api/v1") or catchall.startswith("api"):
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "message": "Endpoint not found"}
        )
    
    # Check if requested file exists, otherwise fallback to SPA index.html
    local_path = os.path.join(frontend_dist, catchall)
    if os.path.exists(local_path) and os.path.isfile(local_path):
        return FileResponse(local_path)
        
    return FileResponse(os.path.join(frontend_dist, "index.html"))
