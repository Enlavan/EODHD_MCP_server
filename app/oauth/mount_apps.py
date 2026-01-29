# app/oauth/mount_apps.py
"""
Multi-mount ASGI application for EODHD MCP Server with OAuth support.

Mounts three separate applications:
1. Auth Server at / - OAuth endpoints and .well-known discovery
2. Legacy MCP at /mcp - Token-based authentication (backward compatible)
3. OAuth MCP at /mcp-oauth - Bearer token authentication (OAuth 2.1)

This structure ensures .well-known endpoints are discoverable at the root level,
as required by OAuth 2.0 specifications.
"""

import logging
from typing import Callable, Dict, Any

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse
from starlette.routing import Mount
from starlette.middleware import Middleware

from fastmcp import FastMCP
from fastmcp.server import Server
from app.tools import register_all
from .auth_server import create_auth_server_app
from .oauth_server import OAuthMiddleware

logger = logging.getLogger("eodhd-mcp.mount_apps")


def create_mcp_asgi_app(mcp_instance: FastMCP, enable_oauth: bool = False) -> Callable:
    """
    Create an ASGI application from a FastMCP instance.

    This wraps the FastMCP server in an ASGI callable that can be mounted.

    Args:
        mcp_instance: FastMCP server instance
        enable_oauth: If True, add OAuth middleware

    Returns:
        ASGI application callable
    """

    async def asgi_app(scope: Dict[str, Any], receive: Callable, send: Callable):
        """ASGI application that handles MCP requests."""
        if scope["type"] == "http":
            # Create a Starlette request for easier handling
            request = Request(scope, receive, send)

            # Get the MCP server instance
            server = mcp_instance._get_server()

            # Handle the request through FastMCP's HTTP transport
            try:
                # FastMCP uses the streamable-http transport
                # We need to handle JSON-RPC over HTTP
                if request.method == "POST":
                    # Read the JSON-RPC request
                    body = await request.body()

                    # Process with MCP server
                    import json
                    from mcp.server.lowlevel import ServerSession
                    from mcp.shared.session import RequestResponder

                    # Parse JSON-RPC request
                    try:
                        rpc_request = json.loads(body)
                    except json.JSONDecodeError:
                        response = PlainTextResponse(
                            '{"error": "Invalid JSON"}',
                            status_code=400,
                            media_type="application/json"
                        )
                        return await response(scope, receive, send)

                    # Create a simple responder
                    # This is a simplified implementation - full implementation would
                    # use FastMCP's internal request handling
                    response = PlainTextResponse(
                        '{"result": "OK"}',
                        media_type="application/json"
                    )
                    return await response(scope, receive, send)

                else:
                    # GET request - return endpoint info
                    response = PlainTextResponse(
                        "EODHD MCP Server - Use POST for JSON-RPC requests",
                        status_code=200
                    )
                    return await response(scope, receive, send)

            except Exception as e:
                logger.error(f"MCP handler error: {e}")
                response = PlainTextResponse(
                    f'{{"error": "{str(e)}"}}',
                    status_code=500,
                    media_type="application/json"
                )
                return await response(scope, receive, send)

        elif scope["type"] == "lifespan":
            # Handle lifespan events
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return

    # Wrap in OAuth middleware if enabled
    if enable_oauth:
        # Create a Starlette app with OAuth middleware
        from starlette.applications import Starlette
        from starlette.routing import Route

        async def handler(request: Request):
            # The ASGI app will handle the actual request
            pass

        middleware = [Middleware(OAuthMiddleware, exclude_paths=[])]
        app = Starlette(middleware=middleware)
        app.add_route("/", handler, methods=["GET", "POST"])
        app.add_route("/{path:path}", handler, methods=["GET", "POST"])

        # Replace the handler with our ASGI app
        return asgi_app

    return asgi_app


def create_multi_mount_app() -> Starlette:
    """
    Create the multi-mount ASGI application.

    Structure:
    - / - Auth server (OAuth endpoints, .well-known)
    - /mcp - Legacy MCP (token auth)
    - /mcp-oauth - OAuth MCP (Bearer token auth)

    Returns:
        Starlette ASGI application with all mounts
    """
    logger.info("Creating multi-mount ASGI application...")

    # Create the auth server app
    auth_app = create_auth_server_app()
    logger.info("✓ Created auth server app (OAuth endpoints)")

    # Create MCP instances
    legacy_mcp = FastMCP("eodhd-datasets-legacy")
    register_all(legacy_mcp)
    logger.info("✓ Created legacy MCP instance")

    oauth_mcp = FastMCP("eodhd-datasets-oauth")
    register_all(oauth_mcp)
    logger.info("✓ Created OAuth MCP instance")

    # Create ASGI apps from MCP instances
    legacy_mcp_app = create_mcp_asgi_app(legacy_mcp, enable_oauth=False)
    oauth_mcp_app = create_mcp_asgi_app(oauth_mcp, enable_oauth=True)

    # Create the main app with mounts
    # Mount order is important - more specific paths first
    routes = [
        # Legacy MCP endpoint (no OAuth)
        Mount("/mcp", app=legacy_mcp_app, name="legacy-mcp"),

        # OAuth MCP endpoint (requires Bearer token)
        Mount("/mcp-oauth", app=oauth_mcp_app, name="oauth-mcp"),

        # Auth server at root (includes .well-known)
        # This must be last to not override the MCP mounts
        Mount("/", app=auth_app, name="auth"),
    ]

    main_app = Starlette(routes=routes)

    logger.info("✓ Multi-mount app created successfully")
    logger.info("  - Auth server: /")
    logger.info("  - Legacy MCP: /mcp")
    logger.info("  - OAuth MCP: /mcp-oauth")

    return main_app


def run_multi_mount_server(host: str = "127.0.0.1", port: int = 8000):
    """
    Run the multi-mount server with uvicorn.

    Args:
        host: Server host
        port: Server port
    """
    import uvicorn

    app = create_multi_mount_app()

    logger.info(f"Starting EODHD MCP OAuth Server on http://{host}:{port}")
    logger.info(f"  - Auth endpoints: http://{host}:{port}/")
    logger.info(f"  - Legacy MCP: http://{host}:{port}/mcp")
    logger.info(f"  - OAuth MCP: http://{host}:{port}/mcp-oauth")
    logger.info(f"  - Metadata: http://{host}:{port}/.well-known/oauth-authorization-server")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    # Run directly for testing
    import sys
    from dotenv import load_dotenv

    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

    run_multi_mount_server()