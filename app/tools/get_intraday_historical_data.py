import json
from typing import Optional

from fastmcp import FastMCP
from app.config import EODHD_API_BASE
from app.api_client import make_request

ALLOWED_INTERVALS = {"1m", "5m", "1h"}   # per docs
ALLOWED_FMT = {"json", "csv"}

# Max allowed “from->to” span per docs (in days)
MAX_RANGE_DAYS = {
    "1m": 120,
    "5m": 600,
    "1h": 7200,
}

def _err(msg: str) -> str:
    return json.dumps({"error": msg}, indent=2)

def _validate_ts(name: str, value: Optional[int]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, int):
        return f"'{name}' must be an integer Unix timestamp (UTC seconds)."
    if value <= 0:
        return f"'{name}' must be a positive Unix timestamp."
    return None

def register(mcp: FastMCP):
    @mcp.tool()
    async def get_intraday_historical_data(
        ticker: str,
        interval: str = "5m",
        from_timestamp: Optional[int] = None,
        to_timestamp: Optional[int] = None,
        fmt: str = "json",
        split_dt: Optional[bool] = False,
        api_token: Optional[str] = None,
    ) -> str:
        """
        Intraday Historical Stock Price Data API (spec-aligned).

        Args:
            ticker (str): SYMBOL.EXCHANGE_ID, e.g. 'AAPL.US'.
            interval (str): One of {'1m','5m','1h'}. Default '5m'.
            from_timestamp (int, optional): Start Unix timestamp (UTC seconds).
            to_timestamp (int, optional): End Unix timestamp (UTC seconds).
            fmt (str): 'json' or 'csv'. Default 'json'.
            split_dt (bool, optional): If True, adds 'split-dt=1' to split date/time fields.
            api_token (str, optional): Per-call token override; env token used if omitted.

        Notes:
            - If no 'from'/'to' provided, API returns last 120 days by default (per docs).
            - Max span depends on interval:
                1m -> 120 days, 5m -> 600 days, 1h -> 7200 days.
        """

        # --- Validate required/typed params ---
        if not ticker or not isinstance(ticker, str):
            return _err("Parameter 'ticker' is required (e.g., 'AAPL.US').")

        if interval not in ALLOWED_INTERVALS:
            return _err(f"Invalid 'interval'. Allowed: {sorted(ALLOWED_INTERVALS)}")

        if fmt not in ALLOWED_FMT:
            return _err(f"Invalid 'fmt'. Allowed: {sorted(ALLOWED_FMT)}")

        msg = _validate_ts("from_timestamp", from_timestamp)
        if msg:
            return _err(msg)
        msg = _validate_ts("to_timestamp", to_timestamp)
        if msg:
            return _err(msg)

        if from_timestamp is not None and to_timestamp is not None:
            if from_timestamp > to_timestamp:
                return _err("'from_timestamp' cannot be greater than 'to_timestamp'.")

            # Enforce documented maximum range
            span_seconds = to_timestamp - from_timestamp
            max_days = MAX_RANGE_DAYS[interval]
            if span_seconds > max_days * 86400:
                return _err(
                    f"Requested range exceeds maximum for interval '{interval}'. "
                    f"Max is {max_days} days."
                )

        # --- Build URL ---
        # Base: /api/intraday/{ticker}?fmt=...&interval=...&from=...&to=...&split-dt=1
        url = f"{EODHD_API_BASE}/intraday/{ticker}?fmt={fmt}&interval={interval}"

        if from_timestamp is not None:
            url += f"&from={from_timestamp}"
        if to_timestamp is not None:
            url += f"&to={to_timestamp}"
        if split_dt:
            url += "&split-dt=1"

        # Per-call token override; make_request() will append env token if none present.
        if api_token:
            url += f"&api_token={api_token}"

        # --- Request ---
        data = await make_request(url)

        # --- Normalize errors / outputs ---
        if data is None:
            return _err("No response from API.")

        if isinstance(data, dict) and data.get("error"):
            return json.dumps({"error": data["error"]}, indent=2)

        # For csv: if you later adapt make_request to return text for fmt='csv',
        # we wrap it as {"csv": "..."} so the MCP tool consistently returns a JSON string.
        try:
            return json.dumps(data, indent=2)
        except Exception:
            if isinstance(data, str):
                return json.dumps({"csv": data}, indent=2)
            return _err("Unexpected response format from API.")
