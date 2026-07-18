import hmac
from typing import Optional
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import APIKeyHeader, HTTPBearer

# We import settings inside to avoid circular imports if needed, but it's better to pass it or import from courtos.app
# Actually, the user asked to add `auth_required` and `api_key` to config.py, so we can import Settings from courtos.config and instantiate or use the one from app.py.

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

class AuthenticatedUser:

    def __init__(self, identity: str, role: str, auth_type: str):
        self.identity = identity
        self.role = role
        self.auth_type = auth_type

def get_settings():
    from courtos.app import settings
    return settings

async def get_current_user_or_key(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    bearer: Optional[str] = Depends(bearer_scheme)
) -> Optional[AuthenticatedUser]:
    settings = get_settings()

    if not getattr(settings, 'auth_required', False):
        return AuthenticatedUser(identity="anonymous", role="admin", auth_type="none")

    expected_key = getattr(settings, 'api_key', 'courtos-secret-api-key').encode("utf-8")

    if api_key:
        if hmac.compare_digest(api_key.encode("utf-8"), expected_key):
            return AuthenticatedUser(identity="api_client", role="admin", auth_type="api_key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )

    if bearer and bearer.credentials:
        if hmac.compare_digest(bearer.credentials.encode("utf-8"), expected_key):
            return AuthenticatedUser(identity="jwt_client", role="admin", auth_type="bearer")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Token"
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated"
    )
