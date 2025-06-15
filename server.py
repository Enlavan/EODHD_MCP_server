import json
import os
import httpx
import logging
import sys
from fastmcp import FastMCP
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("eodhd-mcp")

# Initialize FastMCP server
mcp = FastMCP("eodhd-datasets")

# Constants
EODHD_API_BASE = "https://eodhd.com/api"

# Helper function to make API requests
async def make_request(url: str) -> dict | None:
    load_dotenv()
    api_token = os.environ.get("EODHD_API_KEY", "demo")
    if "api_token=" not in url:
        url += f"&api_token={api_token}" if "?" in url else f"?api_token={api_token}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

@mcp.tool()
async def get_income_statements(ticker: str, period: str = "annual", limit: int = 4) -> str:
    url = f"{EODHD_API_BASE}/fundamentals/{ticker}?fmt=json"
    data = await make_request(url)
    try:
        financials = data.get("Financials", {}).get("Income_Statement", {}).get(period, {})
        return json.dumps(list(financials.values())[:limit], indent=2)
    except Exception:
        return "Unable to fetch or parse income statements."

@mcp.tool()
async def get_balance_sheets(ticker: str, period: str = "annual", limit: int = 4) -> str:
    url = f"{EODHD_API_BASE}/fundamentals/{ticker}?fmt=json"
    data = await make_request(url)
    try:
        financials = data.get("Financials", {}).get("Balance_Sheet", {}).get(period, {})
        return json.dumps(list(financials.values())[:limit], indent=2)
    except Exception:
        return "Unable to fetch or parse balance sheets."

@mcp.tool()
async def get_cash_flow_statements(ticker: str, period: str = "annual", limit: int = 4) -> str:
    url = f"{EODHD_API_BASE}/fundamentals/{ticker}?fmt=json"
    data = await make_request(url)
    try:
        financials = data.get("Financials", {}).get("Cash_Flow", {}).get(period, {})
        return json.dumps(list(financials.values())[:limit], indent=2)
    except Exception:
        return "Unable to fetch or parse cash flow statements."

@mcp.tool()
async def get_current_stock_price(ticker: str) -> str:
    url = f"{EODHD_API_BASE}/real-time/{ticker}?fmt=json"
    data = await make_request(url)
    return json.dumps(data, indent=2) if data else "Unable to fetch current price."

@mcp.tool()
async def get_historical_stock_prices(ticker: str, start_date: str, end_date: str, period: str = "d") -> str:
    url = f"{EODHD_API_BASE}/eod/{ticker}?from={start_date}&to={end_date}&period={period}&fmt=json"
    data = await make_request(url)
    return json.dumps(data, indent=2) if data else "Unable to fetch historical prices."

@mcp.tool()
async def get_company_news(ticker: str, limit: int = 5) -> str:
    url = f"{EODHD_API_BASE}/news?s={ticker}&limit={limit}&fmt=json"
    data = await make_request(url)
    news = data if isinstance(data, list) else data.get("news", [])
    return json.dumps(news[:limit], indent=2) if news else "No news found."

@mcp.tool()
async def get_stocks_from_search(query: str, limit: int = 5) -> str:
    url = f"{EODHD_API_BASE}/search/{query}?fmt=json&limit={limit}"
    data = await make_request(url)
    if isinstance(data, dict) and data.get('error'):
        return json.dumps({"error": data["error"]}, indent=2)
    return json.dumps(data, indent=2) if data else "No results found."


@mcp.tool()
async def get_intraday_historical_data(ticker: str,
        interval: str,
        from_timestamp: int = None,
        to_timestamp: int = None,
        fmt: str = "json" ) -> str:
    url = f"{EODHD_API_BASE}/intraday/{ticker}?interval={interval}&fmt={fmt}"
    if from_timestamp:
        url += f"&from={from_timestamp}"
    if to_timestamp:
        url += f"&to={to_timestamp}"

    data = await make_request(url)

    if isinstance(data, dict) and "error" in data:
        return json.dumps({"error": data["error"]}, indent=2)
    return json.dumps(data, indent=2) if data else "No intraday historical data found."


if __name__ == "__main__":
    logger.info("Starting EODHD MCP HTTP Server...")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000, path="/mcp")
    logger.info("Server stopped")
