# app/oauth/resource_server.py

"""
OAuth Protected Resource middleware for EODHD MCP Server.

What this module does:
- Exposes OAuthMiddleware that protects the OAuth MCP resource (mounted at /v2/mcp).
- On missing/invalid Bearer token, returns **401** with a WWW-Authenticate header
  that points clients (e.g., Claude Web) to Protected Resource Metadata discovery:
    /.well-known/oauth-protected-resource/<resource-path>
- On valid Bearer token, injects the real user's EODHD API key into:
    request.state.eodhd_api_key
  so app/api_client.py can transparently use it.

Important:
- When the MCP ASGI app is mounted (e.g. Mount("/v2/mcp", app=...)), the child request path
  is typically "/" at the mount root. FastMCP commonly serves MCP at an internal path like "/mcp".
  mount_apps.py handles this via a rewrite wrapper, while this middleware must see the ORIGINAL
  mount-root request so it can return the correct 401 challenge for Claude Web.
"""

import inspect
import logging
import os
import time
from typing import Any, Callable, Dict, Iterable, Optional, Union

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("eodhd-mcp.resource_server")

# Default scope advertised in challenges for now (you said "grant all").
DEFAULT_CHALLENGE_SCOPE = os.getenv("DEFAULT_SCOPE", "full-access")


def _clean_base_url(url: str) -> str:
    return (url or "").rstrip("/")


def _server_base_url(request: Request) -> str:
    """
    Canonical external base URL.

    Prefer MCP_SERVER_URL (recommended behind proxies),
    otherwise infer from request headers.
    """
    env = os.getenv("MCP_SERVER_URL") or os.getenv("SERVER_BASE_URL") or os.getenv("PUBLIC_BASE_URL")
    if env:
        return _clean_base_url(env)

    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return _clean_base_url(f"{proto}://{host}")


def _normalize_path(p: str) -> str:
    if not p:
        return "/"
    if not p.startswith("/"):
        p = "/" + p
    if p != "/" and p.endswith("/"):
        p = p[:-1]
    return p


def _resource_base_path(request: Request) -> str:
    """
    Returns the mounted resource base path (e.g. "/v2/mcp").

    In Starlette mounts, the mounted base is in scope["root_path"].
    That is the path we want to reference in RFC9728 "path insertion" discovery,
    and the path we expect in token audience/resource binding.
    """
    root = (request.scope.get("root_path") or "").strip()
    root = _normalize_path(root) if root else "/"
    return root


def _resource_url(request: Request) -> str:
    """
    Absolute resource URL for the protected resource base (e.g. https://mcp.eodhd.dev/v2/mcp).
    """
    base = _server_base_url(request)
    return f"{base}{_resource_base_path(request)}".rstrip("/")


def _resource_metadata_url(request: Request) -> str:
    """
    Protected Resource Metadata "path insertion" form:
      /.well-known/oauth-protected-resource/<resource-path-without-leading-slash>

    Example:
      resource: https://mcp.eodhd.dev/v2/mcp
      metadata: https://mcp.eodhd.dev/.well-known/oauth-protected-resource/v2/mcp
    """
    base = _server_base_url(request)

    rp = _resource_base_path(request).lstrip("/")
    if not rp:
        return f"{base}/.well-known/oauth-protected-resource"
    return f"{base}/.well-known/oauth-protected-resource/{rp}"


def _bearer_challenge_headers(
    request: Request,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    scope: Optional[str] = None,
) -> Dict[str, str]:
    """
    WWW-Authenticate per RFC 6750 with a pointer to Protected Resource Metadata discovery.

    Claude Web expects a 401 from the protected resource and then reads the metadata.
    """
    meta = _resource_metadata_url(request)

    parts = [
        'Bearer realm="eodhd-mcp"',
        f'resource_metadata="{meta}"',
    ]

    # MCP clients tend to look for "scope" on the challenge; we default to full-access for now.
    use_scope = (scope or DEFAULT_CHALLENGE_SCOPE or "").strip()
    if use_scope:
        parts.append(f'scope="{use_scope}"')

    if error:
        parts.append(f'error="{error}"')

    if error_description:
        safe_desc = error_description.replace('"', "'")[:200]
        parts.append(f'error_description="{safe_desc}"')

    return {
        "WWW-Authenticate": ", ".join(parts),
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
    }


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _load_jwt_settings() -> Dict[str, Any]:
    """
    Load JWT settings lazily. Prefer auth_server constants if present,
    else fall back to env vars so resource middleware can run even if imports change.
    """
    jwt_secret = os.getenv("JWT_SECRET", "") or None
    jwt_alg = os.getenv("JWT_ALGORITHM", "HS256")

    try:
        from . import auth_server  # runtime import intentional

        jwt_secret = getattr(auth_server, "JWT_SECRET", None) or jwt_secret
        jwt_alg = getattr(auth_server, "JWT_ALGORITHM", jwt_alg)
    except Exception:
        pass

    return {"JWT_SECRET": jwt_secret, "JWT_ALGORITHM": jwt_alg}


async def _get_storage():
    """
    Prefer FastMCP-compatible TokenStorage (app/oauth/token_storage.py).
    Fall back to auth_server.get_storage() if you keep that API surface.
    """
    try:
        from .token_storage import get_storage  # runtime import intentional

        return get_storage()
    except Exception:
        from .auth_server import get_storage  # runtime import intentional

        return get_storage()


def _aud_matches(aud_claim: Union[str, list, tuple, None], expected: str) -> bool:
    """
    Compare JWT 'aud' claim against expected resource URL (best-effort).
    Accept both string and array audiences; compare with trailing-slash normalization.
    """
    exp = (expected or "").rstrip("/")
    if not exp:
        return False

    if isinstance(aud_claim, str):
        return aud_claim.rstrip("/") == exp

    if isinstance(aud_claim, (list, tuple)):
        for a in aud_claim:
            if isinstance(a, str) and a.rstrip("/") == exp:
                return True
        return False

    return False


async def _resolve_eodhd_key_from_token(request: Request, token: str) -> Optional[str]:
    """
    Validate the access token and resolve the user's EODHD API key.

    Strategy:
    1) Verify JWT signature + exp using shared JWT_SECRET (preferred; internal AS-issued JWTs).
    2) Confirm token exists in storage and is not expired (so we only accept tokens we issued).
    3) Resolve user via storage and extract eodhd_api_key.

    Notes:
    - Audience/resource binding is enforced best-effort: aud must match the protected resource URL.
    - If storage was cleared, tokens will be rejected even if signature is valid (intended).
    """
    settings = await _load_jwt_settings()
    jwt_secret = settings.get("JWT_SECRET")
    jwt_alg = settings.get("JWT_ALGORITHM", "HS256")

    if not jwt_secret:
        logger.error("JWT_SECRET is not configured; cannot validate access tokens")
        return None

    try:
        # We validate signature + exp; we validate aud manually (because aud form varies).
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=[jwt_alg],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

    # Enforce resource binding (MCP expects resource indicators / aud binding).
    expected_resource = _resource_url(request)
    aud = payload.get("aud")
    if aud is not None and not _aud_matches(aud, expected_resource):
        logger.debug("Token aud mismatch: aud=%s expected=%s", aud, expected_resource)
        return None

    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        return None

    storage = await _get_storage()

    # Confirm token exists in storage (so we only accept issued tokens).
    # TokenStorage in app/oauth/token_storage.py supports get_access_token(token) (raw token input).
    tok_obj = None
    get_access = getattr(storage, "get_access_token", None)
    if callable(get_access):
        try:
            tok_obj = await _maybe_await(get_access(token))
        except Exception:
            tok_obj = None
        if not tok_obj:
            return None
        exp_at = getattr(tok_obj, "expires_at", None)
        if exp_at and float(exp_at) < time.time():
            return None

    # Resolve user via storage
    get_user_by_email = getattr(storage, "get_user_by_email", None)
    if callable(get_user_by_email):
        try:
            user = await _maybe_await(get_user_by_email(sub))
            if user and getattr(user, "eodhd_api_key", None):
                return str(user.eodhd_api_key).strip()
        except Exception:
            pass

    # Compatibility fallback for alternate storage API shapes
    load_user_by_email = getattr(storage, "load_user_by_email", None)
    if callable(load_user_by_email):
        try:
            user = await _maybe_await(load_user_by_email(sub))
            if user and getattr(user, "eodhd_api_key", None):
                return str(user.eodhd_api_key).strip()
        except Exception:
            pass

    return None


class OAuthMiddleware(BaseHTTPMiddleware):
    """
    Protect an MCP resource with Bearer token validation and metadata discovery.

    - If missing/invalid Bearer token -> 401 + WWW-Authenticate (resource_metadata=...)
    - If valid -> inject request.state.eodhd_api_key and pass downstream
    """

    def __init__(
        self,
        app: Callable,
        exclude_paths: Optional[Iterable[str]] = None,
    ):
        super().__init__(app)
        self.exclude_paths = set(exclude_paths or [])

    def _is_excluded(self, request: Request) -> bool:
        if not self.exclude_paths:
            return False
        root = _resource_base_path(request)
        path = request.url.path or "/"
        full = f"{root.rstrip('/')}{path if path.startswith('/') else '/' + path}"
        full = full.rstrip("/") if full != "/" else full
        return full in self.exclude_paths or path in self.exclude_paths

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.scope.get("type") != "http":
            return await call_next(request)

        # Allow CORS preflight to pass through (common in browser contexts)
        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        if self._is_excluded(request):
            return await call_next(request)

        auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
        if not auth.lower().startswith("bearer "):
            return JSONResponse(
                {"error": "unauthorized", "message": "Missing Bearer token"},
                status_code=401,
                headers=_bearer_challenge_headers(
                    request,
                    error="invalid_token",
                    error_description="Missing Bearer token",
                    scope=DEFAULT_CHALLENGE_SCOPE,
                ),
            )

        token = auth.split(" ", 1)[1].strip()
        if not token:
            return JSONResponse(
                {"error": "unauthorized", "message": "Empty Bearer token"},
                status_code=401,
                headers=_bearer_challenge_headers(
                    request,
                    error="invalid_token",
                    error_description="Empty Bearer token",
                    scope=DEFAULT_CHALLENGE_SCOPE,
                ),
            )

        eodhd_key = await _resolve_eodhd_key_from_token(request, token)
        if not eodhd_key:
            return JSONResponse(
                {"error": "unauthorized", "message": "Invalid or expired token"},
                status_code=401,
                headers=_bearer_challenge_headers(
                    request,
                    error="invalid_token",
                    error_description="Invalid or expired token",
                    scope=DEFAULT_CHALLENGE_SCOPE,
                ),
            )

        # Inject for app/api_client.py
        try:
            request.state.eodhd_api_key = eodhd_key
            request.state.oauth_subject = None  # optional; set if you want
        except Exception:
            # If state is not writable for some reason, still proceed (downstream may fall back)
            pass

        return await call_next(request)


# Optional: backward-compatible re-export for any code that imports get_storage from here.
def get_storage():
    try:
        from .token_storage import get_storage as _gs  # runtime import intentional

        return _gs()
    except Exception:
        from .auth_server import get_storage as _gs  # runtime import intentional

        return _gs()
