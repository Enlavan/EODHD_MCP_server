# EODHD MCP Server

A Model Context Protocol (MCP) server that exposes the [EOD Historical Data](https://eodhistoricaldata.com/) (EODHD) API through MCP-compatible clients (Claude Desktop, ChatGPT, etc.). It provides convenient tools for market data, fundamentals, technicals, news/sentiment, screeners, options, indices, and illio insights.

## Highlights

* End-of-day, intraday & tick data
* Live (delayed) quotes & extended US quotes (Live v2)
* Fundamentals (financials, filings, earnings)
* News, sentiment & topic weights
* Screener & discovery endpoints
* Corporate actions (dividends, splits, IPOs)
* Options markets (contracts, EOD, underlyings)
* Macro indicators, exchanges & listings
* Marketplace endpoints

---

## Requirements

* Python **3.10+**
* An EODHD API key (`EODHD_API_KEY`)
* An MCP-compatible client (Claude Desktop, ChatGPT, etc.)

---

## Installation & Setup

### 1) Clone & install

```bash
git clone https://github.com/Enlavan/EODHD_MCP_server.git
cd EODHD_MCP_server
pip install -r requirements.txt
```

Create a `.env` at the repo root (used by HTTP + stdio entrypoints):

```env
EODHD_API_KEY=YOUR_EODHD_API_KEY
# Optional (HTTP server):
MCP_HOST=127.0.0.1
MCP_PORT=8000
```

---

### 2) Run as a local HTTP server

**Option A (root entrypoint):**

```bash
python server.py
# → http://127.0.0.1:8000/mcp (defaults; override with MCP_HOST/MCP_PORT)
```

**Option B (module entrypoint):**

```bash
python -m entrypoints.server_http
# uses .env for key/host/port
```

---

### 3) Run as an MCP stdio server

For clients that launch the server via stdio:

```bash
# Pass API key from CLI, useful for dev or when no .env
python -m entrypoints.server_stdio --apikey YOUR_EODHD_API_KEY
```

(If `--apikey` is set, it overrides `EODHD_API_KEY` from the environment.)

---

## Using with Claude Desktop

### A) Install via MCP bundle (`.mcpb`)

1. Download the `.mcpb` from Releases.
2. Claude Desktop → **Settings → Extensions → Advanced → Install Extension**.
3. Select the `.mcpb`, approve, enter your API key, enable the extension.

### B) Use source checkout (developer config)

1. Clone this repo anywhere.
2. Claude Desktop → **Developer → Edit config**, add:

```json
{
  "mcpServers": {
    "eodhd-mcp": {
      "command": "python3",
      "args": [
        "/home/user/EODHD_MCP_server/server.py",
        "--stdio"
      ],
       "env": {
           "EODHD_API_KEY": "YOUR_EODHD_API_KEY"
         }
    }
  }
}
```

Restart Claude Desktop. The server will be launched on demand via stdio.

---

## Using with ChatGPT (beta MCP support)

1. Open ChatGPT **Settings** → ensure your plan supports **Connectors / MCP**.
2. Enable developer/connectors features.
3. Add a custom MCP **HTTP** source:

   * URL: `http://127.0.0.1:8000/mcp` (or your deployed URL)
   * Provide your EODHD API key as required by your gateway or set it in `.env` on the server.
4. Start a new chat → **Add sources** → select your MCP server.

> If your ChatGPT workspace supports hosted connectors with query params, you can deploy the HTTP server and expose a URL like:
> `https://YOUR_HOST/mcp` (API key handled server-side via env).

---

## Testing

### HTTP client test

```bash
python test/test_client.py
# uses http://127.0.0.1:8000/mcp by default
```

### STDIO client test

```bash
python test/test_client_stdio.py --cmd "python3 -m entrypoints.server_stdio --apikey YOUR_EODHD_API_KEY"
```

Both clients load `test/all_tests.py` which registers a suite of calls against the server’s tools.

---

## MCP Tools

### Main tools

* `get_historical_stock_prices`
* `get_live_price_data`
* `get_us_live_extended_quotes` (Live v2, US extended quotes)
* `get_intraday_historical_data`
* `get_us_tick_data`
* `capture_realtime_ws`
* `get_company_news`
* `get_sentiment_data`
* `get_news_word_weights`
* `get_stock_screener_data`
* `get_fundamentals_data`
* `get_macro_indicator`
* `get_economic_events`
* `get_historical_market_cap`
* `get_insider_transactions`
* `get_exchange_details`
* `get_exchanges_list`
* `get_exchange_tickers`
* `get_symbol_change_history`
* `get_stocks_from_search`
* `get_upcoming_earnings`
* `get_earnings_trends`
* `get_upcoming_ipos`
* `get_upcoming_splits`
* `get_upcoming_dividends`
* `get_technical_indicators`

### Marketplace tools

* `get_mp_us_options_contracts`
* `get_mp_us_options_eod`
* `get_mp_us_options_underlyings`
* `get_mp_indices_list`
* `get_mp_index_components`

### Third-party tools

* `get_mp_illio_performance_insights`
* `get_mp_illio_risk_insights`
* `get_mp_illio_market_insights_performance`
* `get_mp_illio_market_insights_best_worst`
* `get_mp_illio_market_insights_volatility`

---

## Minimal HTTP example (Python)

```python
import asyncio, json
from fastmcp import Client

async def main():
    async with Client("http://127.0.0.1:8000/mcp") as client:
        res = await client.call_tool(
            "get_historical_stock_prices",
            {"ticker": "AAPL.US", "start_date": "2024-01-01", "end_date": "2024-03-31"}
        )
        print(json.dumps(json.loads(res), indent=2))

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Project Structure

```
EODHD_MCP_server/
├─ app/
│  ├─ api_client.py
│  ├─ config.py
│  └─ tools/
│     ├─ __init__.py
│     ├─ capture_realtime_ws.py
│     ├─ get_company_news.py
│     ├─ get_earnings_trends.py
│     ├─ get_economic_events.py
│     ├─ get_exchange_details.py
│     ├─ get_exchanges_list.py
│     ├─ get_exchange_tickers.py
│     ├─ get_fundamentals_data.py
│     ├─ get_historical_market_cap.py
│     ├─ get_historical_stock_prices.py
│     ├─ get_insider_transactions.py
│     ├─ get_intraday_historical_data.py
│     ├─ get_live_price_data.py
│     ├─ get_macro_indicator.py
│     ├─ get_mp_illio_market_insights_best_worst.py
│     ├─ get_mp_illio_market_insights_performance.py
│     ├─ get_mp_illio_market_insights_volatility.py
│     ├─ get_mp_illio_performance_insights.py
│     ├─ get_mp_illio_risk_insights.py
│     ├─ get_mp_index_components.py
│     ├─ get_mp_indices_list.py
│     ├─ get_mp_us_options_contracts.py
│     ├─ get_mp_us_options_eod.py
│     ├─ get_mp_us_options_underlyings.py
│     ├─ get_news_word_weights.py
│     ├─ get_sentiment_data.py
│     ├─ get_stock_screener_data.py
│     ├─ get_stocks_from_search.py
│     ├─ get_symbol_change_history.py
│     ├─ get_technical_indicators.py
│     ├─ get_upcoming_dividends.py
│     ├─ get_upcoming_earnings.py
│     ├─ get_upcoming_ipos.py
│     ├─ get_upcoming_splits.py
│     ├─ get_us_live_extended_quotes.py
│     └─ get_us_tick_data.py
├─ assets/
├─ entrypoints/
│  ├─ server_http.py
│  └─ server_stdio.py
├─ test/
│  ├─ all_tests.py
│  ├─ test_client.py
│  └─ test_client_stdio.py
├─ LICENSE
├─ manifest.json
├─ requirements.txt
├─ server.py
└─ README.md
```

**Entry points**

* `server.py` – production HTTP entrypoint (reads `.env` for host/port and key)
* `entrypoints/server_http.py` – HTTP (module form)
* `entrypoints/server_stdio.py` – stdio server (supports `--apikey`)

---

## License

MIT. See `LICENSE`.

## Contributing

Issues and PRs welcome. Please include clear reproduction steps and logs where possible.
