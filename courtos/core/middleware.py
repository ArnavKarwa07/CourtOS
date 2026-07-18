import time
import uuid
from typing import Dict
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class RequestIdMiddleware(BaseHTTPMiddleware):
    """Class description.\n"""

    async def dispatch(self, request: Request, call_next):
        """Method description.

        Args:
        *args: Arguments.
        **kwargs: Keyword arguments.

        Returns:
        Any: Return value.

        Raises:
        Exception: If an error occurs.

        """
        # Inject correlation ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Class description.\n"""

    async def dispatch(self, request: Request, call_next):
        """Method description.

        Args:
        *args: Arguments.
        **kwargs: Keyword arguments.

        Returns:
        Any: Return value.

        Raises:
        Exception: If an error occurs.

        """
        response = await call_next(request)

        # Apply secure response headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), display-capture=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

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
    """In-memory Sliding Window Rate Limiting middleware.
    Limits high-frequency endpoints (e.g. /api/v1/telemetry) to prevent DoS.
    """

    def __init__(self, app, max_requests: int = 200, window_seconds: int = 60):
        """Method description.

        Args:
        *args: Arguments.
        **kwargs: Keyword arguments.

        Returns:
        Any: Return value.

        Raises:
        Exception: If an error occurs.

        """
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.client_records: Dict[str, list] = {}

    async def dispatch(self, request: Request, call_next):
        """Method description.

        Args:
        *args: Arguments.
        **kwargs: Keyword arguments.

        Returns:
        Any: Return value.

        Raises:
        Exception: If an error occurs.

        """
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
    """Class description.\n"""

    async def dispatch(self, request: Request, call_next):
        """Method description.

        Args:
        *args: Arguments.
        **kwargs: Keyword arguments.

        Returns:
        Any: Return value.

        Raises:
        Exception: If an error occurs.

        """
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

class PayloadSizeLimitMiddleware:
    """Class description.\n"""

    def __init__(self, app, max_upload_size: int = 1_048_576):
        """Method description.

        Args:
        *args: Arguments.
        **kwargs: Keyword arguments.

        Returns:
        Any: Return value.

        Raises:
        Exception: If an error occurs.

        """
        self.app = app
        self.max_upload_size = max_upload_size

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        if scope["method"] not in ("POST", "PUT", "PATCH"):
            return await self.app(scope, receive, send)

        # Check Content-Length header first
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    content_length = int(value)
                    if content_length > self.max_upload_size:
                        response = JSONResponse(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            content={"error": "payload_too_large", "message": "Request body exceeds maximum size limit"}
                        )
                        return await response(scope, receive, send)
                except ValueError:
                    pass

        # Stream body and count
        body_bytes = b""
        more_body = True
        messages = []

        while more_body:
            message = await receive()
            messages.append(message)
            body_bytes += message.get("body", b"")
            
            if len(body_bytes) > self.max_upload_size:
                response = JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"error": "payload_too_large", "message": "Request body exceeds maximum size limit"}
                )
                return await response(scope, receive, send)
                
            more_body = message.get("more_body", False)

        # Re-inject consumed body
        async def receive_wrapper():
            """Method description.

            Args:
            *args: Arguments.
            **kwargs: Keyword arguments.

            Returns:
            Any: Return value.

            Raises:
            Exception: If an error occurs.

            """
            if messages:
                return messages.pop(0)
            return await receive()

        await self.app(scope, receive_wrapper, send)
