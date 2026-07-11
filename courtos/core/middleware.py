import uuid
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
