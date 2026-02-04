# app/mount_apps.py

"""
Multi-mount ASGI application for EODHD MCP Server with OAuth support.

Mounts (as requested):
1) Auth Server at /                   - OAuth endpoints + .well-known discovery (ROOT!)
2) Legacy MCP at /v1/mcp              - legacy token styles (apikey, x-api-key, etc.)
3) OAuth MCP (protected resource) at /v2/mcp  - Bearer token protected resource (OAuth 2.1)

Why we keep the auth server at "/":
- OAuth discovery metadata MUST be under root well-known paths (RFC 8414 / RFC 9728),
  and FastMCP mounting under a prefix can otherwise "move" discovery routes.
- So we explicitly mount the auth server at "/" and the MCP resources under /v1 and /v2.

Why path rewriting exists:
- FastMCP's http_app() commonly exposes MCP under an internal sub-path (often "/mcp").
- When you Mount("/v2/mcp", app=fastmcp_app), the child app sees request as path "/".
- If FastMCP doesn't serve MCP at "/", it returns 404.
- We rewrite child "/" -> "/mcp" (or whatever FastMCP uses internally).
- IMPORTANT ordering: OAuth middleware runs BEFORE rewriting so it can challenge on "/".
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.routing import Mount as StarletteMount  # for isinstance checks
from starlette.requests import Request
from starlette.responses import Response

from fastmcp import FastMCP

from app.tools import register_all
from .auth_server import create_auth_server_app
from .resource_server import OAuthMiddleware

logger = logging.getLogger("eodhd-mcp.mount_apps")

# Public mounts requested
LEGACY_MCP_MOUNT = "/v1/mcp"
OAUTH_MCP_MOUNT = "/v2/mcp"


def _normalize_path(p: str) -> str:
    if not p:
        return "/"
    if not p.startswith("/"):
        p = "/" + p
    # keep "/" as-is, otherwise remove trailing slash
    if p != "/" and p.endswith("/"):
        p = p[:-1]
    return p


def _detect_fastmcp_internal_mcp_path(app: Any) -> str:
    """
    Best-effort detection of the internal MCP path exposed by the FastMCP http_app().

    Common cases:
      - app.routes has Mount("/mcp", ...)
      - env MCP_PATH is set (e.g. "/mcp")
      - fallback "/mcp"
    """
    env_path = os.getenv("MCP_PATH")
    env_path = _normalize_path(env_path) if env_path else None

    routes = getattr(app, "routes", None)
    if isinstance(routes, list):
        # Prefer mounted "/mcp" if present
        for r in routes:
            try:
                if isinstance(r, StarletteMount):
                    p = getattr(r, "path", None)
                    if isinstance(p, str):
                        np = _normalize_path(p)
                        if np == "/mcp":
                            return np
            except Exception:
                continue

        # Otherwise, look for any mount containing "mcp"
        for r in routes:
            try:
                p = getattr(r, "path", None)
                if isinstance(p, str):
                    np = _normalize_path(p)
                    if "mcp" in np:
                        return np
            except Exception:
                continue

    if env_path:
        return env_path

    return "/mcp"


class _RewriteToInternalMcpPath:
    """
    ASGI wrapper that rewrites child-paths so the MCP endpoint is reachable at the mount root.

    Inside a Mount("/v2/mcp", ...), the child scope['path'] is usually "/" for requests to "/v2/mcp".
    If FastMCP serves MCP at "/mcp", we rewrite:
        "/"  -> "/mcp"
        ""   -> "/mcp"
    For any other path, we leave it alone unless it doesn't start with the internal prefix,
    in which case we prefix it (best-effort).
    """

    def __init__(self, app: Any, internal_prefix: str):
        self.app = app
        self.internal_prefix = _normalize_path(internal_prefix)

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        if not path.startswith("/"):
            path = "/" + path

        new_path: Optional[str] = None

        if path in ("", "/"):
            new_path = self.internal_prefix
        else:
            # If caller already hits the internal path (e.g., /v2/mcp/mcp), don't double-prefix.
            if self.internal_prefix != "/" and not (
                path == self.internal_prefix or path.startswith(self.internal_prefix + "/")
            ):
                new_path = self.internal_prefix + path

        if new_path and new_path != path:
            new_scope = dict(scope)
            new_scope["path"] = new_path
            try:
                new_scope["raw_path"] = new_path.encode("ascii", "ignore")
            except Exception:
                pass
            await self.app(new_scope, receive, send)
            return

        await self.app(scope, receive, send)


def _build_fastmcp_http_app(mcp: FastMCP, path: str = "/mcp") -> Any:
    """
    Create the FastMCP streamable-http ASGI app.

    Args:
        mcp: The FastMCP instance
        path: The internal path where FastMCP will serve (default: /mcp)

    Note: FastMCP's http_app() creates an ASGI app that serves at an internal path.
    """
    try:
        # Try with both transport and path parameters
        return mcp.http_app(transport="streamable-http", path=path)
    except TypeError:
        try:
            # Fallback: try with just path
            return mcp.http_app(path=path)
        except TypeError:
            # Final fallback: no parameters
            return mcp.http_app()


def _wrap_oauth_and_rewrite(
    base_fastmcp_app: Any,
    internal_mcp_path: str,
    enable_oauth: bool,
) -> Any:
    """
    IMPORTANT: ordering for /v2/mcp (OAuth-protected resource):
      1) OAuthMiddleware FIRST (so it sees the original "/")
      2) rewrite SECOND (so FastMCP receives "/mcp")

    This ensures the protected resource base (/v2/mcp) returns the correct 401 + WWW-Authenticate
    challenge instead of 404 from FastMCP.
    """
    rewritten = _RewriteToInternalMcpPath(base_fastmcp_app, internal_prefix=internal_mcp_path)

    if not enable_oauth:
        return rewritten

    # BaseHTTPMiddleware can be used as a standalone ASGI wrapper
    return OAuthMiddleware(rewritten, exclude_paths=[])


def create_multi_mount_app() -> Starlette:
    logger.info("Creating multi-mount ASGI application...")

    # Validate OAuth resource path configuration matches mount path
    configured_resource_path = os.getenv("MCP_OAUTH_RESOURCE_PATH", "/v2/mcp").strip() or "/v2/mcp"
    if configured_resource_path != OAUTH_MCP_MOUNT:
        logger.error(
            "CRITICAL CONFIGURATION ERROR: OAuth resource path mismatch!\n"
            "  Configured resource path (MCP_OAUTH_RESOURCE_PATH): %s\n"
            "  Actual mount path (OAUTH_MCP_MOUNT): %s\n"
            "  This will cause OAuth token validation to fail due to audience mismatch.\n"
            "  Please update MCP_OAUTH_RESOURCE_PATH environment variable to match %s",
            configured_resource_path,
            OAUTH_MCP_MOUNT,
            OAUTH_MCP_MOUNT,
        )
        raise ValueError(
            f"OAuth resource path mismatch: configured={configured_resource_path} vs mount={OAUTH_MCP_MOUNT}"
        )

    # Auth server (root) — MUST stay at root for .well-known routes
    auth_app = create_auth_server_app()
    logger.info("✓ Created auth server app (root /)")

    # Legacy MCP (/v1/mcp)
    legacy_mcp = FastMCP("eodhd-datasets-legacy")
    register_all(legacy_mcp)
    # Try to configure FastMCP to serve at "/" so it works when mounted
    legacy_base_app = _build_fastmcp_http_app(legacy_mcp, path="/")
    legacy_internal = _detect_fastmcp_internal_mcp_path(legacy_base_app)
    # If FastMCP still serves at /mcp internally, we need rewriting
    if legacy_internal != "/":
        legacy_app = _wrap_oauth_and_rewrite(legacy_base_app, legacy_internal, enable_oauth=False)
        logger.info("✓ Created legacy MCP app (mounted at %s, internal=%s, with rewrite)", LEGACY_MCP_MOUNT, legacy_internal)
    else:
        legacy_app = legacy_base_app
        logger.info("✓ Created legacy MCP app (mounted at %s, no rewrite needed)", LEGACY_MCP_MOUNT)

    # OAuth MCP (/v2/mcp)
    oauth_mcp = FastMCP("eodhd-datasets-oauth")
    register_all(oauth_mcp)
    # Try to configure FastMCP to serve at "/" so it works when mounted
    oauth_base_app = _build_fastmcp_http_app(oauth_mcp, path="/")
    oauth_internal = _detect_fastmcp_internal_mcp_path(oauth_base_app)
    # If FastMCP still serves at /mcp internally, we need rewriting and OAuth
    if oauth_internal != "/":
        oauth_app = _wrap_oauth_and_rewrite(oauth_base_app, oauth_internal, enable_oauth=True)
        logger.info("✓ Created OAuth MCP app (mounted at %s, internal=%s, with rewrite)", OAUTH_MCP_MOUNT, oauth_internal)
    else:
        oauth_app = OAuthMiddleware(oauth_base_app, exclude_paths=[])
        logger.info("✓ Created OAuth MCP app (mounted at %s, no rewrite needed)", OAUTH_MCP_MOUNT)

    # Create a wrapper to handle the OAuth app as both Route and Mount
    # This is needed because Starlette's Mount redirects paths without trailing slashes
    async def oauth_route_handler(request: Request) -> Response:
        """Handle requests to /v2/mcp without trailing slash by forwarding to the OAuth app"""
        scope = dict(request.scope)
        scope["path"] = "/"  # The OAuth app expects "/" when mounted
        scope["root_path"] = OAUTH_MCP_MOUNT

        # Call the OAuth app directly
        response_started = False
        status_code = 200
        headers = []
        body_parts = []

        async def receive():
            return await request.receive()

        async def send(message):
            nonlocal response_started, status_code, headers
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = message.get("headers", [])
            elif message["type"] == "http.response.body":
                body_parts.append(message.get("body", b""))

        await oauth_app(scope, receive, send)

        # Build the response
        body = b"".join(body_parts)
        # Convert headers from list of tuples to dict for Starlette Response
        response_headers = {
            (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
            for k, v in headers
        }
        return Response(content=body, status_code=status_code, headers=response_headers)

    async def legacy_route_handler(request: Request) -> Response:
        """Handle requests to /v1/mcp without trailing slash by forwarding to the legacy app"""
        scope = dict(request.scope)
        scope["path"] = "/"
        scope["root_path"] = LEGACY_MCP_MOUNT

        response_started = False
        status_code = 200
        headers = []
        body_parts = []

        async def receive():
            return await request.receive()

        async def send(message):
            nonlocal response_started, status_code, headers
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = message.get("headers", [])
            elif message["type"] == "http.response.body":
                body_parts.append(message.get("body", b""))

        await legacy_app(scope, receive, send)

        body = b"".join(body_parts)
        # Convert headers from list of tuples to dict for Starlette Response
        response_headers = {
            (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
            for k, v in headers
        }
        return Response(content=body, status_code=status_code, headers=response_headers)

    # IMPORTANT: nested lifespans are NOT automatically managed; run FastMCP lifespans here.
    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        legacy_ls = getattr(legacy_base_app, "lifespan", None)
        oauth_ls = getattr(oauth_base_app, "lifespan", None)

        if legacy_ls and oauth_ls:
            async with legacy_ls(app):
                async with oauth_ls(app):
                    yield
            return

        if legacy_ls:
            async with legacy_ls(app):
                yield
            return

        if oauth_ls:
            async with oauth_ls(app):
                yield
            return

        yield

    # Build routes list: MCP mounts first (most specific), then auth routes
    # Extract auth server routes and middleware to integrate them directly
    auth_routes = getattr(auth_app, 'routes', [])
    auth_middleware = getattr(auth_app, 'user_middleware', [])

    routes = [
        # Add exact-path routes BEFORE mounts to handle requests without trailing slash
        # This prevents Starlette's automatic 307 redirect from Mount
        Route(OAUTH_MCP_MOUNT, endpoint=oauth_route_handler, methods=["GET", "POST", "OPTIONS"], name="oauth-mcp-exact"),
        Route(LEGACY_MCP_MOUNT, endpoint=legacy_route_handler, methods=["GET", "POST", "OPTIONS"], name="legacy-mcp-exact"),
        # Mounts handle paths with trailing slashes and sub-paths
        Mount(OAUTH_MCP_MOUNT, app=oauth_app, name="oauth-mcp"),
        Mount(LEGACY_MCP_MOUNT, app=legacy_app, name="legacy-mcp"),
    ]

    # Add auth server routes directly to avoid "/" mount conflicts
    routes.extend(auth_routes)

    # Create main app with auth server middleware for session management
    main_app = Starlette(routes=routes, middleware=auth_middleware, debug=True, lifespan=lifespan)

    logger.info("✓ Multi-mount app created successfully")
    logger.info("  - Auth server: %s", "/")
    logger.info("  - Legacy MCP:  %s", LEGACY_MCP_MOUNT)
    logger.info("  - OAuth MCP:   %s", OAUTH_MCP_MOUNT)

    return main_app


def run_multi_mount_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """
    NOTE about 127.0.0.1:
    - This is only the *bind address* for the local listener.
    - It does NOT determine what URLs are published in OAuth metadata.
    - OAuth metadata should use MCP_SERVER_URL (e.g. https://mcp.eodhd.dev) or
      X-Forwarded-* headers from your reverse proxy.

    In production, you typically want:
      host="0.0.0.0"
    and you MUST set:
      MCP_SERVER_URL="https://mcp.eodhd.dev"
    """
    import uvicorn

    app = create_multi_mount_app()
    public = os.getenv("MCP_SERVER_URL", "").rstrip("/")
    if public:
        logger.info("Public MCP_SERVER_URL: %s", public)

    logger.info("Starting EODHD MCP OAuth Server (bind) on http://%s:%s", host, port)
    logger.info("  - Auth endpoints: (root) /")
    logger.info("  - Legacy MCP:     %s", LEGACY_MCP_MOUNT)
    logger.info("  - OAuth MCP:      %s", OAUTH_MCP_MOUNT)

    uvicorn.run(app, host=host, port=port, log_level="info")
