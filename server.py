from fastmcp import FastMCP
from app.tools import register_all

mcp = FastMCP("eodhd-datasets")
register_all(mcp)

if __name__ == "__main__":
    import logging, sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", stream=sys.stderr)
    logger = logging.getLogger("eodhd-mcp")
    logger.info("Starting EODHD MCP HTTP Server...")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000, path="/mcp")
    logger.info("Server stopped")
