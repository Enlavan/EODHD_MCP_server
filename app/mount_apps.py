# app/mount_apps.py

"""
Multi-mount ASGI application for EODHD MCP Server with OAuth support.

Mounts (as requested):
1) Auth Server at /                   - OAuth endpoints + .well-known discovery (ROOT!)
2) Legacy MCP at /v1/mcp              - legacy token styles (apikey, x-api-key, etc, parsing them from query parameters)
3) OAuth MCP (protected resource) at /v2/mcp  - Bearer token protected resource (OAuth 2.1)

Why we keep the auth server at "/":
- OAuth discovery metadata MUST be under root well-known paths (RFC 8414 / RFC 9728),
  and FastMCP mounting under a prefix can otherwise "move" discovery routes.
- So we explicitly mount the auth server at "/" and the MCP resources under /v1 and /v2.

We configure FastMCP to serve at "/" so it works cleanly when mounted.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.requests import Request
from starlette.responses import Response

from fastmcp import FastMCP

from app.tools import register_all
from app.oauth.auth_server import create_auth_server_app
from app.oauth.resource_server import OAuthMiddleware

logger = logging.getLogger("eodhd-mcp.mount_apps")

# Public mounts requested
LEGACY_MCP_MOUNT = "/v1/mcp"
OAUTH_MCP_MOUNT = "/v2/mcp"


def _build_fastmcp_http_app(mcp: FastMCP, path: str = "/") -> Any:
    """
    Create the FastMCP streamable-http ASGI app.

    Args:
        mcp: The FastMCP instance
        path: The internal path where FastMCP will serve

    Note: FastMCP's http_app() creates an ASGI app that serves at an internal path.
    """
    try:
        return mcp.http_app(transport="streamable-http", path=path)
    except TypeError:
        try:
            return mcp.http_app(path=path)
        except TypeError:
            return mcp.http_app()


def _ensure_accept_header(app: Any) -> Any:
    """
    FastMCP streamable-http can return 406 if Accept is missing or too strict.
    This wrapper forces a sane default for MCP endpoints.
    """
    async def _asgi(scope, receive, send):
        if scope.get("type") == "http":
            headers = list(scope.get("headers") or [])
            # Remove any existing Accept to avoid overly strict values.
            headers = [(k, v) for (k, v) in headers if k.lower() != b"accept"]
            headers.append((b"accept", b"application/json, text/event-stream;q=0.9, */*;q=0.1"))
            scope = dict(scope)
            scope["headers"] = headers
        await app(scope, receive, send)

    return _asgi


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
    legacy_base_app = _build_fastmcp_http_app(legacy_mcp, path="/")
    legacy_app = _ensure_accept_header(legacy_base_app)
    logger.info("✓ Created legacy MCP app (mounted at %s)", LEGACY_MCP_MOUNT)

    # OAuth MCP (/v2/mcp)
    oauth_mcp = FastMCP("eodhd-datasets-oauth")
    register_all(oauth_mcp)
    oauth_base_app = _build_fastmcp_http_app(oauth_mcp, path="/")
    oauth_app = OAuthMiddleware(_ensure_accept_header(oauth_base_app), exclude_paths=[])
    logger.info("✓ Created OAuth MCP app (mounted at %s)", OAUTH_MCP_MOUNT)

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
            async with legacy_ls(legacy_base_app):
                async with oauth_ls(oauth_base_app):
                    yield
            return

        if legacy_ls:
            async with legacy_ls(legacy_base_app):
                yield
            return

        if oauth_ls:
            async with oauth_ls(oauth_base_app):
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

    proxy_headers = os.getenv("PROXY_HEADERS", "true").strip().lower() in {"1", "true", "yes"}
    forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "*").strip() or "*"

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        proxy_headers=proxy_headers,
        forwarded_allow_ips=forwarded_allow_ips,
    )
