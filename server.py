import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from fastmcp import FastMCP
from app.tools import register_all


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="EODHD MCP Server")

    # Transport selection (mutually exclusive):
    # - default is HTTP unless --stdio or --sse is provided
    transport = p.add_mutually_exclusive_group()
    transport.add_argument(
        "--http",
        action="store_true",
        help="Run HTTP transport (default if no other transport is selected).",
    )
    transport.add_argument(
        "--stdio",
        action="store_true",
        help="Run STDIO transport (only if explicitly requested).",
    )
    transport.add_argument(
        "--sse",
        action="store_true",
        help="Run SSE transport (Server-Sent Events).",
    )

    # OAuth support
    p.add_argument(
        "--oauth",
        action="store_true",
        help="Enable OAuth 2.1 mode (mounts /mcp, /mcp-oauth, and auth server).",
    )

    # Defaults come from environment variables (loaded from .env), but CLI overrides env
    p.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "127.0.0.1"),
        help="HTTP/SSE host (default: 127.0.0.1 or $MCP_HOST).",
    )
    p.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8000")),
        help="HTTP/SSE port (default: 8000 or $MCP_PORT).",
    )
    p.add_argument(
        "--path",
        default=os.getenv("MCP_PATH", "/mcp"),
        help="HTTP path for streamable-http (default: /mcp or $MCP_PATH).",
    )
    p.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Logging level (default: INFO or $LOG_LEVEL).",
    )

    p.add_argument(
        "--apikey", "--api-key",
        dest="api_key",
        help="EODHD API key",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    # Load .env before parsing so env defaults are available to argparse
    load_dotenv()
    parser = build_parser()
    args, unknown = parser.parse_known_args(argv)

    # If provided, override env so make_request() picks it up
    if args.api_key:
        os.environ["EODHD_API_KEY"] = args.api_key

    if unknown:
        # Don’t print secrets; just show shapes
        print(f"Ignoring extra args from client: {len(unknown)} item(s)", file=sys.stderr)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )
    logger = logging.getLogger("eodhd-mcp")

    mcp = FastMCP("eodhd-datasets")
    register_all(mcp)

    # Determine transport:
    # - If --stdio: stdio
    # - If --sse: SSE
    # - Else: HTTP (streamable-http)
    run_stdio = args.stdio
    run_sse = args.sse
    run_http = args.http or not (args.stdio or args.sse)

    try:
        if run_stdio:
            logger.info("Starting EODHD MCP (STDIO)...")
            mcp.run(transport="stdio")
            logger.info("STDIO server stopped.")
            return 0

        if run_sse:
            logger.info(
                "Starting EODHD MCP **SSE** Server on http://%s:%s ...",
                args.host,
                args.port,
            )
            # Note: SSE transport does not use the 'path' argument in your standalone version,
            # so we keep that behavior here.
            mcp.run(
                transport="sse",
                host=args.host,
                port=args.port,
            )
            logger.info("SSE server stopped.")
            return 0

        if run_http:
            # Check if OAuth mode is enabled
            if args.oauth or os.getenv("OAUTH_ENABLED", "").lower() == "true":
                logger.info("=" * 70)
                logger.info("EODHD MCP Server - OAuth 2.1 Mode")
                logger.info("=" * 70)
                logger.info("Starting multi-mount server on http://%s:%s", args.host, args.port)
                logger.info("  - Auth Server: http://%s:%s/", args.host, args.port)
                logger.info("  - Legacy MCP:  http://%s:%s/mcp", args.host, args.port)
                logger.info("  - OAuth MCP:   http://%s:%s/mcp-oauth", args.host, args.port)
                logger.info("=" * 70)

                # Import and run the multi-mount server
                from app.oauth.mount_apps import run_multi_mount_server
                run_multi_mount_server(host=args.host, port=args.port)
                return 0
            else:
                logger.info(
                    "Starting EODHD MCP HTTP Server on http://%s:%s%s ...",
                    args.host,
                    args.port,
                    args.path,
                )
                mcp.run(
                    transport="streamable-http",
                    host=args.host,
                    port=args.port,
                    path=args.path,
                )
                logger.info("HTTP server stopped.")
                return 0

        logger.error("No transport selected.")
        return 2

    except KeyboardInterrupt:
        logger.info("Shutdown requested (Ctrl+C).")
        return 0
    except Exception:
        logger.exception("Fatal error while running MCP server.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
