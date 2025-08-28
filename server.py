from fastmcp import FastMCP

mcp = FastMCP("eodhd-datasets")

if __name__ == "__main__":
    logger.info("Starting EODHD MCP HTTP Server...")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000, path="/mcp")
    logger.info("Server stopped")
