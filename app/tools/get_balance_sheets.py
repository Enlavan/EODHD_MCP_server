import json
from fastmcp import FastMCP
from app.config import EODHD_API_BASE
from app.api_client import make_request

def register(mcp: FastMCP):
    @mcp.tool()
    async def get_balance_sheets(ticker: str, period: str = "annual", limit: int = 4) -> str:
        url = f"{EODHD_API_BASE}/fundamentals/{ticker}?fmt=json"
        data = await make_request(url)
        try:
            financials = data.get("Financials", {}).get("Balance_Sheet", {}).get(period, {})
            return json.dumps(list(financials.values())[:limit], indent=2)
        except Exception:
            return "Unable to fetch or parse balance sheets."
