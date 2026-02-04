# app/oauth/auth_server.py
"""
OAuth 2.1 Authorization Server for EODHD MCP Server.

Implements:
- Authorization Server Metadata (.well-known/oauth-authorization-server) (RFC 8414)
- Protected Resource Metadata (.well-known/oauth-protected-resource/...) (RFC 9728 + MCP draft)
- Dynamic Client Registration (POST /register) (RFC 7591 - minimal)
- Authorization Code flow with PKCE (S256)
- Token endpoint (POST /token)
- Token introspection (POST /introspect) (RFC 7662 - minimal)

Plus (critical):
- Client ID Metadata Document support (OAuth Client ID Metadata Document draft)
  - Allows client_id to be an HTTPS URL pointing to a JSON metadata document
  - Authorization server fetches metadata as needed and caches it (bounded, respects HTTP caching)

Since eodhd.com doesn't provide OAuth, this server implements the full
authorization flow internally. Users authenticate using their EODHD API key
(via EODHD internal-user API) and this server issues OAuth access tokens
(JWTs) for /v2/mcp.
"""

import base64
import hashlib
import ipaddress
import logging
import os
import re
import secrets
import socket
import time
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

import httpx
import jwt
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from .token_storage import (
    get_storage,
    TokenStorage,
    OAuthClient,
    AuthorizationCode,
    AccessToken,
    User,
)

logger = logging.getLogger("eodhd-mcp.auth_server")

# -----------------------------
# Configuration
# -----------------------------

JWT_SECRET = (os.getenv("JWT_SECRET") or "").strip() or None
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRES = int(os.getenv("ACCESS_TOKEN_EXPIRES", "3600"))  # seconds
AUTH_CODE_EXPIRES = int(os.getenv("AUTH_CODE_EXPIRES", "600"))  # seconds
SESSION_SECRET = os.getenv("SESSION_SECRET") or secrets.token_urlsafe(32)

DEFAULT_SCOPE = os.getenv("DEFAULT_SCOPE", "full-access")
DEFAULT_RESOURCE_PATH = os.getenv("MCP_OAUTH_RESOURCE_PATH", "/v2/mcp").strip() or "/v2/mcp"

# ---- Client ID Metadata Document support ----
CLIENT_ID_METADATA_DOCUMENT_SUPPORTED = True

CLIENT_META_HTTP_TIMEOUT = float(os.getenv("CLIENT_META_HTTP_TIMEOUT", "5.0"))
CLIENT_META_MAX_BYTES = int(os.getenv("CLIENT_META_MAX_BYTES", "1048576"))  # 1 MiB
CLIENT_META_DEFAULT_TTL = int(os.getenv("CLIENT_META_DEFAULT_TTL", "3600"))  # 1h
CLIENT_META_MIN_TTL = int(os.getenv("CLIENT_META_MIN_TTL", "60"))  # 1m
CLIENT_META_MAX_TTL = int(os.getenv("CLIENT_META_MAX_TTL", "86400"))  # 24h

# In-memory cache: client_id_url -> (metadata_dict, expires_at_epoch)
_CLIENT_META_CACHE: Dict[str, Tuple[Dict[str, Any], float]] = {}

_SECRET_BASED_AUTH_METHODS = {
    "client_secret_post",
    "client_secret_basic",
    "client_secret_jwt",
    "tls_client_auth",
}


# -----------------------------
# Utilities
# -----------------------------

def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _pkce_s256(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return _base64url(digest)


def _clean_base_url(url: str) -> str:
    return (url or "").rstrip("/")


def _server_base_url(request: Request) -> str:
    """
    Canonical external base URL for metadata documents and redirects.

    Prefer MCP_SERVER_URL env (recommended in production behind proxies),
    otherwise infer from request headers.
    """
    env = os.getenv("MCP_SERVER_URL") or os.getenv("SERVER_BASE_URL") or os.getenv("PUBLIC_BASE_URL")
    if env:
        return _clean_base_url(env)

    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return _clean_base_url(f"{proto}://{host}")


def _resource_url_for_path(request: Request, resource_path: str) -> str:
    base = _server_base_url(request)
    rp = (resource_path or "").strip("/")
    return f"{base}/{rp}" if rp else base


def _add_params(url: str, params: Dict[str, str]) -> str:
    parsed = urlparse(url)
    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    q.update({k: v for k, v in params.items() if v is not None})
    new_query = urlencode(q, doseq=True)
    return str(urlunparse(parsed._replace(query=new_query)))


def _safe_redirect_uri(url: str) -> bool:
    """
    Minimal safety check: only allow http(s) redirect targets.
    """
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def _oauth_error_redirect(
    redirect_uri: str,
    error: str,
    error_description: Optional[str] = None,
    state: Optional[str] = None,
) -> RedirectResponse:
    params: Dict[str, str] = {"error": error}
    if error_description:
        params["error_description"] = error_description
    if state:
        params["state"] = state
    return RedirectResponse(url=_add_params(redirect_uri, params), status_code=303)


def _error_page(message: str, status_code: int = 400) -> HTMLResponse:
    return HTMLResponse(f"<h1>Error</h1><p>{message}</p>", status_code=status_code)


# -----------------------------
# Client ID Metadata Document helpers
# -----------------------------

def _is_global_ip(ip: ipaddress._BaseAddress) -> bool:
    try:
        return bool(getattr(ip, "is_global"))
    except Exception:
        return False


def _hostname_is_public(hostname: str) -> bool:
    """
    SSRF guard: deny localhost/private/reserved/etc.

    Require *all* resolved A/AAAA to be globally routable.
    """
    if not hostname:
        return False

    h = hostname.strip().lower()
    if h in {"localhost", "localhost.localdomain"}:
        return False

    # IP-literal?
    try:
        ip = ipaddress.ip_address(h.strip("[]"))
        return _is_global_ip(ip)
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(hostname, None)
    except Exception:
        return False

    if not infos:
        return False

    for family, _type, _proto, _canonname, sockaddr in infos:
        try:
            addr = sockaddr[0]
            ip = ipaddress.ip_address(addr)
            if not _is_global_ip(ip):
                return False
        except Exception:
            return False

    return True


def _validate_client_id_url(client_id_url: str) -> Optional[str]:
    """
    Validate client_id URL constraints.

    Enforced:
    - https only
    - host required
    - path required and not "/"
    - no fragment
    - no userinfo
    - no dot segments
    - host must be publicly routable (SSRF guard)
    """
    if not client_id_url or not isinstance(client_id_url, str):
        return "client_id is required"

    try:
        p = urlparse(client_id_url)
    except Exception:
        return "client_id is not a valid URL"

    if p.scheme.lower() != "https":
        return "client_id must use https scheme"

    if not p.netloc:
        return "client_id must include a host"

    if not p.path or p.path == "/":
        return "client_id must contain a path component"

    if p.fragment:
        return "client_id must not contain a fragment"

    if p.username or p.password:
        return "client_id must not contain username/password"

    segments = [seg for seg in p.path.split("/") if seg]
    if any(seg in {".", ".."} for seg in segments):
        return "client_id must not contain dot path segments"

    host = p.hostname or ""
    if not _hostname_is_public(host):
        return "client_id host is not publicly routable"

    return None


def _ttl_from_response_headers(resp: httpx.Response) -> int:
    ttl = CLIENT_META_DEFAULT_TTL
    cc = resp.headers.get("cache-control") or resp.headers.get("Cache-Control") or ""
    m = re.search(r"max-age\s*=\s*(\d+)", cc)
    if m:
        try:
            ttl = int(m.group(1))
        except Exception:
            ttl = CLIENT_META_DEFAULT_TTL

    ttl = max(CLIENT_META_MIN_TTL, min(ttl, CLIENT_META_MAX_TTL))
    return ttl


async def _fetch_client_metadata_document(client_id_url: str) -> Dict[str, Any]:
    err = _validate_client_id_url(client_id_url)
    if err:
        raise ValueError(err)

    cached = _CLIENT_META_CACHE.get(client_id_url)
    if cached:
        meta, exp = cached
        if time.time() < exp:
            return meta
        _CLIENT_META_CACHE.pop(client_id_url, None)

    headers = {"Accept": "application/json", "User-Agent": "eodhd-mcp-oauth/1.0"}

    async with httpx.AsyncClient(timeout=CLIENT_META_HTTP_TIMEOUT, follow_redirects=False) as client:
        resp = await client.get(client_id_url, headers=headers)

    if resp.status_code != 200:
        raise ValueError(f"Unable to fetch client metadata document (status={resp.status_code})")

    content = resp.content or b""
    if len(content) > CLIENT_META_MAX_BYTES:
        raise ValueError("Client metadata document is too large")

    try:
        meta = resp.json()
    except Exception:
        raise ValueError("Client metadata document is not valid JSON")

    if not isinstance(meta, dict):
        raise ValueError("Client metadata document must be a JSON object")

    doc_client_id = meta.get("client_id")
    if not doc_client_id or not isinstance(doc_client_id, str) or doc_client_id != client_id_url:
        raise ValueError("client_id in metadata document does not match the document URL")

    redirect_uris = meta.get("redirect_uris")
    if (
        not isinstance(redirect_uris, list)
        or not redirect_uris
        or not all(isinstance(u, str) and u.strip() for u in redirect_uris)
    ):
        raise ValueError("Client metadata document must include non-empty redirect_uris list")

    tam = meta.get("token_endpoint_auth_method", "none")
    tam = "none" if tam is None else str(tam).strip()

    if tam in _SECRET_BASED_AUTH_METHODS:
        raise ValueError("token_endpoint_auth_method must not be shared-secret based for client_id documents")

    if tam not in {"none", ""}:
        raise ValueError(f"Unsupported token_endpoint_auth_method for client_id document: {tam}")

    ttl = _ttl_from_response_headers(resp)
    _CLIENT_META_CACHE[client_id_url] = (meta, time.time() + ttl)
    return meta


async def _load_or_discover_client(client_id: str) -> Optional[OAuthClient]:
    storage: TokenStorage = get_storage()

    # Storage load
    existing = await storage.get_client(client_id)
    if existing:
        return existing

    # Discovery only for https URL client_id
    if not isinstance(client_id, str) or not client_id.lower().startswith("https://"):
        return None

    try:
        meta = await _fetch_client_metadata_document(client_id)
    except Exception as e:
        logger.warning("Client metadata discovery failed for client_id=%s: %s", client_id, e)
        return None

    discovered = OAuthClient(
        client_id=meta["client_id"],
        client_secret=None,
        redirect_uris=[u.strip() for u in meta.get("redirect_uris", []) if isinstance(u, str) and u.strip()],
        client_name=str(meta.get("client_name") or "MCP Client").strip() or "MCP Client",
        token_endpoint_auth_method="none",
    )
    await storage.register_client(discovered)
    return discovered


# -----------------------------
# Endpoints
# -----------------------------

async def register_client_endpoint(request: Request) -> JSONResponse:
    """
    Dynamic Client Registration (minimal).
    """
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_request", "error_description": "Expected JSON body"}, status_code=400)

    client_name = (data.get("client_name") or "MCP Client").strip()
    redirect_uris = data.get("redirect_uris") or []
    token_endpoint_auth_method = (data.get("token_endpoint_auth_method") or "client_secret_post").strip()

    if not isinstance(redirect_uris, list) or not redirect_uris:
        return JSONResponse({"error": "invalid_request", "error_description": "redirect_uris must be a non-empty list"}, status_code=400)

    norm_redirects: list[str] = []
    for u in redirect_uris:
        if not isinstance(u, str) or not u.strip():
            continue
        uu = u.strip()
        p = urlparse(uu)
        if p.scheme not in ("http", "https"):
            return JSONResponse({"error": "invalid_redirect_uri", "error_description": "redirect_uris must be http(s) URLs"}, status_code=400)
        norm_redirects.append(uu)

    if not norm_redirects:
        return JSONResponse({"error": "invalid_redirect_uri", "error_description": "No valid redirect_uris provided"}, status_code=400)

    client_id = data.get("client_id") or secrets.token_urlsafe(16)

    if token_endpoint_auth_method == "none":
        client_secret = None
        token_endpoint_auth_method = "none"
    else:
        client_secret = data.get("client_secret") or secrets.token_urlsafe(32)
        # keep it simple: we accept either post/basic and store the secret
        if token_endpoint_auth_method not in ("client_secret_post", "client_secret_basic"):
            token_endpoint_auth_method = "client_secret_post"

    client = OAuthClient(
        client_id=str(client_id),
        client_secret=client_secret,
        redirect_uris=norm_redirects,
        client_name=client_name,
        token_endpoint_auth_method=token_endpoint_auth_method,
    )

    storage: TokenStorage = get_storage()
    await storage.register_client(client)

    logger.info("Registered OAuth client: %s (id=%s, auth_method=%s)", client_name, client.client_id, token_endpoint_auth_method)

    resp: Dict[str, Any] = {
        "client_id": client.client_id,
        "client_id_issued_at": int(client.created_at),
        "client_name": client.client_name,
        "redirect_uris": client.redirect_uris,
        "grant_types": client.grant_types,
        "response_types": client.response_types,
        "token_endpoint_auth_method": client.token_endpoint_auth_method,
    }
    if client.client_secret:
        resp["client_secret"] = client.client_secret
        resp["client_secret_expires_at"] = 0

    return JSONResponse(resp)


async def login_page(request: Request) -> HTMLResponse:
    html = """
    <!DOCTYPE html>
    <html>
    <head>
      <title>EODHD MCP Server - Login</title>
      <style>
        body { font-family: Arial, sans-serif; max-width: 520px; margin: 50px auto; padding: 20px; }
        .info { background:#e3f2fd; padding:15px; border-radius:6px; border-left:4px solid #2196F3; margin-bottom:18px;}
        .error { background:#ffebee; padding:10px; border-radius:6px; margin-bottom:12px; color:#b71c1c;}
        label { display:block; font-weight:bold; margin-bottom:6px; }
        input { width:100%; padding:10px; box-sizing:border-box; font-family: monospace; }
        button { width:100%; padding:12px; margin-top:14px; background:#4CAF50; color:white; border:0; cursor:pointer; font-size:16px;}
        button:hover { background:#45a049; }
        .help { font-size: 12px; color:#666; margin-top:6px; }
      </style>
    </head>
    <body>
      <h2>EODHD MCP Server Login</h2>
      <div class="info">
        <strong>Authentication Required</strong><br>
        Enter your EODHD API key to authorize access.
      </div>
      {error_block}
      <form method="POST" action="/login">
        <label for="api_key">EODHD API Key</label>
        <input type="password" id="api_key" name="api_key" required autocomplete="off" placeholder="e.g. 6807d463ab9b07.32643224">
        <div class="help">Find your API key at https://eodhd.com/cp/settings</div>
        <button type="submit">Login</button>
      </form>
    </body>
    </html>
    """
    err = request.query_params.get("error")
    error_block = f"<div class='error'>{err}</div>" if err else ""
    return HTMLResponse(html.format(error_block=error_block))


async def login_submit(request: Request) -> RedirectResponse:
    try:
        form = await request.form()
        api_key = (form.get("api_key") or "").strip()
    except Exception:
        api_key = ""

    if not api_key:
        return RedirectResponse(url="/login?error=API+key+is+required", status_code=303)

    storage: TokenStorage = get_storage()

    # fast path: already known
    existing = await storage.get_user_by_api_key(api_key)
    if existing:
        request.session["user_id"] = existing.email
        request.session["logged_in"] = True
        logger.info("User logged in (cached): %s", existing.email)
        return RedirectResponse(url=request.session.pop("oauth_return_to", "/"), status_code=303)

    # validate via EODHD internal-user
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://eodhd.com/api/internal-user", params={"api_token": api_key})
    except httpx.TimeoutException:
        return RedirectResponse(url="/login?error=Service+timeout.+Please+try+again", status_code=303)
    except Exception:
        return RedirectResponse(url="/login?error=Unable+to+validate+API+key", status_code=303)

    if resp.status_code != 200:
        return RedirectResponse(url="/login?error=Invalid+API+key+or+service+unavailable", status_code=303)

    try:
        user_data = resp.json()
    except Exception:
        return RedirectResponse(url="/login?error=Invalid+API+response", status_code=303)

    email = (user_data.get("email") or "").strip()
    if not email:
        return RedirectResponse(url="/login?error=API+response+missing+email", status_code=303)

    user = User(
        email=email,
        eodhd_api_key=api_key,
        name=(user_data.get("name") or "").strip(),
        subscription_type=(user_data.get("subscriptionType") or "").strip(),
        scopes=[DEFAULT_SCOPE],
    )
    await storage.add_user(user)

    request.session["user_id"] = email
    request.session["logged_in"] = True
    logger.info("New user registered and logged in: %s", email)

    return RedirectResponse(url=request.session.pop("oauth_return_to", "/"), status_code=303)


async def authorize_endpoint(request: Request) -> Response:
    """
    GET /authorize?response_type=code&client_id=...&redirect_uri=...&state=...&scope=...&code_challenge=...&code_challenge_method=S256
    """
    if not request.session.get("logged_in"):
        request.session["oauth_return_to"] = str(request.url)
        return RedirectResponse(url="/login", status_code=303)

    response_type = request.query_params.get("response_type")
    client_id = request.query_params.get("client_id")
    redirect_uri = request.query_params.get("redirect_uri")
    state = request.query_params.get("state")
    scope = request.query_params.get("scope") or DEFAULT_SCOPE
    code_challenge = request.query_params.get("code_challenge")
    code_challenge_method = request.query_params.get("code_challenge_method")

    if response_type != "code":
        if redirect_uri and _safe_redirect_uri(str(redirect_uri)):
            return _oauth_error_redirect(str(redirect_uri), "unsupported_response_type", "Only response_type=code is supported", state)
        return _error_page("Only response_type=code is supported", 400)

    if not client_id or not redirect_uri:
        return _error_page("Missing required parameters", 400)

    client = await _load_or_discover_client(str(client_id))
    if not client:
        # IMPORTANT: do not redirect to untrusted redirect_uri when client is unknown
        return _error_page("Unknown client_id (and metadata discovery failed or is unsupported)", 400)

    if str(redirect_uri) not in client.redirect_uris:
        return _oauth_error_redirect(str(redirect_uri), "invalid_request", "Invalid redirect_uri", state)

    if code_challenge_method:
        if code_challenge_method != "S256":
            return _oauth_error_redirect(str(redirect_uri), "invalid_request", "Only code_challenge_method=S256 is supported", state)
        if not code_challenge:
            return _oauth_error_redirect(str(redirect_uri), "invalid_request", "code_challenge is required when code_challenge_method is provided", state)

    resource = _resource_url_for_path(request, DEFAULT_RESOURCE_PATH)
    user_id = request.session.get("user_id") or ""
    scopes = scope.split() if scope else [DEFAULT_SCOPE]

    code_str = secrets.token_urlsafe(32)
    auth_code = AuthorizationCode(
        code=code_str,
        client_id=client.client_id,
        redirect_uri=str(redirect_uri),
        user_id=str(user_id),
        scopes=scopes,
        resource=resource,
        expires_at=time.time() + AUTH_CODE_EXPIRES,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )

    storage: TokenStorage = get_storage()
    await storage.store_auth_code(auth_code)

    logger.info("Issued auth code for client=%s user=%s resource=%s", client.client_id, user_id, resource)

    params = {"code": code_str}
    if state:
        params["state"] = str(state)
    return RedirectResponse(url=_add_params(str(redirect_uri), params), status_code=303)


def _extract_basic_client_credentials(request: Request) -> Tuple[Optional[str], Optional[str]]:
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("basic "):
        return None, None
    try:
        raw = base64.b64decode(auth.split(" ", 1)[1].strip()).decode("utf-8")
        if ":" not in raw:
            return None, None
        cid, csec = raw.split(":", 1)
        return cid, csec
    except Exception:
        return None, None


async def token_endpoint(request: Request) -> JSONResponse:
    """
    POST /token
      grant_type=authorization_code
      code=...
      redirect_uri=...
      client_id=...
      client_secret=... (if applicable)
      code_verifier=... (if PKCE was used)
      resource=... (optional)
    """
    try:
        form = await request.form()
    except Exception:
        return JSONResponse({"error": "invalid_request", "error_description": "Expected form-encoded body"}, status_code=400)

    grant_type = form.get("grant_type")
    code = form.get("code")
    redirect_uri = form.get("redirect_uri")

    client_id = form.get("client_id")
    client_secret = form.get("client_secret")
    basic_id, basic_secret = _extract_basic_client_credentials(request)
    if not client_id and basic_id:
        client_id = basic_id
    if not client_secret and basic_secret:
        client_secret = basic_secret

    code_verifier = form.get("code_verifier")
    requested_resource = form.get("resource")

    if grant_type != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type", "error_description": "Only authorization_code is supported"}, status_code=400)

    if not code or not redirect_uri or not client_id:
        return JSONResponse({"error": "invalid_request", "error_description": "Missing required parameters"}, status_code=400)

    client = await _load_or_discover_client(str(client_id))
    if not client:
        return JSONResponse({"error": "invalid_client", "error_description": "Unknown client_id"}, status_code=401)

    if client.token_endpoint_auth_method != "none":
        if not client.client_secret or not client_secret or str(client_secret) != str(client.client_secret):
            return JSONResponse({"error": "invalid_client", "error_description": "Invalid client credentials"}, status_code=401)

    storage: TokenStorage = get_storage()

    auth_code = await storage.consume_auth_code(str(code))
    if not auth_code:
        return JSONResponse({"error": "invalid_grant", "error_description": "Invalid or expired authorization code"}, status_code=400)

    if auth_code.client_id != client.client_id:
        return JSONResponse({"error": "invalid_grant", "error_description": "Authorization code was issued to a different client"}, status_code=400)

    if auth_code.redirect_uri != str(redirect_uri):
        return JSONResponse({"error": "invalid_grant", "error_description": "Redirect URI mismatch"}, status_code=400)

    expected_resource = _resource_url_for_path(request, DEFAULT_RESOURCE_PATH)
    resource = str(requested_resource) if requested_resource else expected_resource
    if resource != expected_resource:
        return JSONResponse({"error": "invalid_target", "error_description": "Token is not intended for this resource"}, status_code=400)

    # PKCE validation
    if auth_code.code_challenge:
        if auth_code.code_challenge_method != "S256":
            return JSONResponse({"error": "invalid_grant", "error_description": "Unsupported PKCE method"}, status_code=400)
        if not code_verifier:
            return JSONResponse({"error": "invalid_request", "error_description": "code_verifier is required"}, status_code=400)
        if _pkce_s256(str(code_verifier)) != auth_code.code_challenge:
            return JSONResponse({"error": "invalid_grant", "error_description": "Invalid code_verifier"}, status_code=400)

    now = time.time()
    expires_at = now + ACCESS_TOKEN_EXPIRES

    token_claims: Dict[str, Any] = {
        "iss": _server_base_url(request),
        "sub": auth_code.user_id,
        "aud": resource,
        "client_id": client.client_id,
        "scope": " ".join(auth_code.scopes),
        "iat": int(now),
        "exp": int(expires_at),
        "jti": secrets.token_urlsafe(12),
    }
    access_token = jwt.encode(token_claims, JWT_SECRET, algorithm=JWT_ALGORITHM)

    tok = AccessToken(
        token=access_token,
        client_id=client.client_id,
        user_id=auth_code.user_id,
        scopes=auth_code.scopes,
        expires_at=expires_at,
        issued_at=now,
    )
    await storage.store_access_token(tok)

    logger.info("Issued access token for user=%s client=%s aud=%s", auth_code.user_id, client.client_id, resource)

    return JSONResponse(
        {"access_token": access_token, "token_type": "Bearer", "expires_in": ACCESS_TOKEN_EXPIRES, "scope": " ".join(auth_code.scopes)}
    )


async def introspect_endpoint(request: Request) -> JSONResponse:
    try:
        form = await request.form()
    except Exception:
        form = {}

    token = form.get("token")
    if not token:
        return JSONResponse({"active": False})

    try:
        payload = jwt.decode(str(token), JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_aud": False})
    except jwt.InvalidTokenError:
        return JSONResponse({"active": False})

    exp = int(payload.get("exp", 0) or 0)
    if exp and exp < int(time.time()):
        return JSONResponse({"active": False})

    storage: TokenStorage = get_storage()
    tok = await storage.get_access_token(str(token))
    if not tok:
        return JSONResponse({"active": False})

    return JSONResponse(
        {
            "active": True,
            "iss": payload.get("iss"),
            "sub": payload.get("sub"),
            "aud": payload.get("aud"),
            "client_id": payload.get("client_id"),
            "scope": payload.get("scope", ""),
            "exp": payload.get("exp"),
            "iat": payload.get("iat"),
        }
    )


async def well_known_oauth_server(request: Request) -> JSONResponse:
    base = _server_base_url(request)

    metadata: Dict[str, Any] = {
        "issuer": base,
        "authorization_endpoint": f"{base}/authorize",
        "token_endpoint": f"{base}/token",
        "introspection_endpoint": f"{base}/introspect",
        "registration_endpoint": f"{base}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic", "none"],
        "scopes_supported": [
            "read:eod",
            "read:intraday",
            "read:live",
            "read:fundamentals",
            "read:news",
            "read:technicals",
            "read:options",
            "read:marketplace",
            "read:screener",
            "read:macro",
            "read:user",
            "full-access",
        ],
        "client_id_metadata_document_supported": bool(CLIENT_ID_METADATA_DOCUMENT_SUPPORTED),
    }
    return JSONResponse(metadata)


async def well_known_protected_resource_default(request: Request) -> JSONResponse:
    return await well_known_protected_resource(request)


async def well_known_protected_resource(request: Request, resource_path: str = "") -> JSONResponse:
    base = _server_base_url(request)

    rp = (resource_path or "").strip("/")
    if not rp:
        rp = DEFAULT_RESOURCE_PATH.strip("/")

    resource = f"{base}/{rp}"

    metadata: Dict[str, Any] = {
        "resource": resource,
        "authorization_servers": [base],
        "bearer_methods_supported": ["header"],
        "scopes_supported": [
            "read:eod",
            "read:intraday",
            "read:live",
            "read:fundamentals",
            "read:news",
            "read:technicals",
            "read:options",
            "read:marketplace",
            "read:screener",
            "read:macro",
            "read:user",
            "full-access",
        ],
        "resource_documentation": f"{base}/",
    }
    return JSONResponse(metadata)


def create_auth_server_app() -> Starlette:
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET must be set for OAuth mode.")
    routes = [
        Route("/register", register_client_endpoint, methods=["POST"]),
        Route("/login", login_page, methods=["GET"]),
        Route("/login", login_submit, methods=["POST"]),
        Route("/authorize", authorize_endpoint, methods=["GET"]),
        Route("/token", token_endpoint, methods=["POST"]),
        Route("/introspect", introspect_endpoint, methods=["POST"]),
        Route("/.well-known/oauth-authorization-server", well_known_oauth_server, methods=["GET"]),
        Route("/.well-known/oauth-protected-resource", well_known_protected_resource_default, methods=["GET"]),
        Route("/.well-known/oauth-protected-resource/{resource_path:path}", well_known_protected_resource, methods=["GET"]),
    ]

    middleware = [Middleware(SessionMiddleware, secret_key=SESSION_SECRET)]
    return Starlette(routes=routes, middleware=middleware)
