import json
from fastmcp import FastMCP
from app.config import EODHD_API_BASE
from app.api_client import make_request

def register(mcp: FastMCP):
    @mcp.tool()
    async def get_current_stock_price(ticker: str) -> str:
        url = f"{EODHD_API_BASE}/real-time/{ticker}?fmt=json"
        data = await make_request(url)
        return json.dumps(data, indent=2) if data else "Unable to fetch current price."


