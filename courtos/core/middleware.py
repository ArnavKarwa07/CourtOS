import time
import uuid
from typing import Dict, Tuple
from fastapi import Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Inject correlation ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Apply secure response headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # CSP is strict by default.
        # Swagger UI (FastAPI /docs) uses assets from swagger-ui-dist CDN and inline scripts,
        # so we allow those only for the docs routes.
        path = request.url.path or ""
        if path.startswith("/docs") or path.startswith("/redoc") or path.startswith("/openapi.json"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.jsdelivr.net; "
                "font-src 'self' data: https://cdn.jsdelivr.net; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            )
        else:
            response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"

        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-memory Sliding Window Rate Limiting middleware.
    Limits high-frequency endpoints (e.g. /api/v1/telemetry) to prevent DoS.
    """
    def __init__(self, app, max_requests: int = 200, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.client_records: Dict[str, list] = {}

    async def dispatch(self, request: Request, call_next):
        # Apply rate limiting specifically to POST telemetry endpoint
        if request.method == "POST" and request.url.path == "/api/v1/telemetry":
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            
            # Retrieve or initialize client timestamps
            timestamps = self.client_records.get(client_ip, [])
            # Evict timestamps outside window
            timestamps = [t for t in timestamps if now - t < self.window_seconds]
            
            if len(timestamps) >= self.max_requests:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": f"Too many requests. Limit is {self.max_requests} requests per {self.window_seconds}s."
                    },
                    headers={"Retry-After": str(self.window_seconds)}
                )
            
            timestamps.append(now)
            self.client_records[client_ip] = timestamps
            
        return await call_next(request)

class CSRFShieldMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Enforce X-Requested-With header on all state-mutating requests (POST, PUT, DELETE, PATCH)
        # to defend against CSRF attacks in unauthenticated MVP dashboard
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            path = request.url.path
            # Allow Swagger UI paths to bypass header check for developer testing convenience
            if not (path.startswith("/docs") or path.startswith("/openapi.json") or path.startswith("/redoc")):
                if request.headers.get("X-Requested-With") != "CourtOS-Client":
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "error": "CSRF protection triggered",
                            "message": "State-mutating actions require X-Requested-With header matching 'CourtOS-Client'"
                        }
                    )
        return await call_next(request)

