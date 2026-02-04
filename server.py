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

    # OAuth is ON by default; disable only if --no-oauth is passed.
    p.add_argument(
        "--oauth",
        dest="oauth",
        action="store_true",
        default=True,
        help="Enable OAuth 2.1 mode (default).",
    )
    p.add_argument(
        "--no-oauth",
        dest="oauth",
        action="store_false",
        help="Disable OAuth mode.",
    )
    # We should use local session parameters (like API key) only if we set it explicitly

    p.add_argument(
        "--use-local",
        dest="use_local",
        action="store_true",
        default=False,

    )
    # we should use API key from this argument only if --use-local set.
    # The API key obtained from the OAuth server store and passed via the "api_key" request parameter must overwrite this parameter.
    p.add_argument(
        "--apikey", "--api-key",
        dest="api_key",
        help="EODHD API key, used only if the API key is not in the request or via OAUth",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    # Load .env before parsing so env defaults are available to argparse
    load_dotenv()
    parser = build_parser()
    args, unknown = parser.parse_known_args(argv)


    if args.use-local and args.api_key:
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
            if args.oauth:
                logger.info("=" * 70)
                logger.info("EODHD MCP Server - OAuth 2.1 Mode")
                logger.info("=" * 70)
                logger.info("Starting multi-mount server on http://%s:%s", args.host, args.port)
                logger.info("  - Auth Server: http://%s:%s/", args.host, args.port)
                logger.info("  - Legacy MCP:  http://%s:%s/v1/mcp (apikey auth)", args.host, args.port)
                logger.info("  - OAuth MCP:   http://%s:%s/v2/mcp (Bearer token)", args.host, args.port)
                logger.info("=" * 70)

                # If no canonical public URL is provided, default for local dev.
                # In production you SHOULD set MCP_SERVER_URL to the externally-reachable HTTPS origin.

                if not os.getenv("MCP_SERVER_URL"):
                    scheme = os.getenv("MCP_SERVER_SCHEME", "http")
                    os.environ["MCP_SERVER_URL"] = f"{scheme}://{args.host}:{args.port}"

                # Import and run the multi-mount server
                from app.oauth.mount_apps import run_multi_mount_server

                run_multi_mount_server(host=args.host, port=args.port)
                return 0

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
