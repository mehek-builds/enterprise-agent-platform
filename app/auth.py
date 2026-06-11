"""JWT authentication with role claims. Tokens are minted by /v1/auth/token
(demo: API-key exchange; production: G42's IdP issues the same claims)."""
import time

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import AuthConfig, ROLE_TOOL_ALLOWLIST

_bearer = HTTPBearer(auto_error=False)
_cfg = AuthConfig()

# Demo principal store: scoped API keys -> role. Production swaps this for
# the enterprise IdP; the JWT claim contract stays identical.
import os
API_KEYS = {
    os.getenv("ADMIN_API_KEY", "demo-admin-key"): ("admin", "admin@demo"),
    os.getenv("ANALYST_API_KEY", "demo-analyst-key"): ("analyst", "analyst@demo"),
    os.getenv("VIEWER_API_KEY", "demo-viewer-key"): ("viewer", "viewer@demo"),
}


def mint_token(api_key: str) -> str:
    if api_key not in API_KEYS:
        raise HTTPException(401, "unknown API key")
    role, sub = API_KEYS[api_key]
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "role": role, "iat": now, "exp": now + _cfg.token_ttl_seconds},
        _cfg.jwt_secret, algorithm=_cfg.jwt_algorithm,
    )


def current_principal(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if creds is None:
        raise HTTPException(401, "missing bearer token")
    try:
        claims = jwt.decode(creds.credentials, _cfg.jwt_secret, algorithms=[_cfg.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "invalid token")
    if claims.get("role") not in ROLE_TOOL_ALLOWLIST:
        raise HTTPException(403, "unknown role")
    return claims
