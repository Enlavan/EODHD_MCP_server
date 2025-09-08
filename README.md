# EODHD MCP Server

**EODHD MCP Server** is a Python-based Microservice Communication Protocol (MCP) server designed to provide comprehensive access to financial and market data via the **EOD Historical Data (EODHD)** API. This MCP server enables users to easily fetch and manipulate financial datasets including fundamentals, earnings, IPOs, splits, options, indices, historical and intraday stock prices, screeners, sentiment, and more.

## Overview

This project provides easy-to-use MCP endpoints for retrieving various financial datasets using EODHD’s API. Users can leverage the server to integrate financial data into their applications or financial analysis workflows.

### Core Features:

- Fundamentals (stocks, ETFs, funds, indices)
- Income Statements, Balance Sheets, Cash Flows
- Earnings, Upcoming Earnings & Trends
- IPOs and Splits (historical & upcoming)
- Current & Historical Stock Prices
- Intraday & Tick Data
- Market Cap History
- Exchange & Symbol Metadata
- Screener API
- Company News & Sentiment
- Economic Events
- Options (Marketplace endpoints)
- Indices & Index Components

## Setup and Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Enlavan/EODHD_MCP_server.git
cd EODHD_MCP_server
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file at the root of your project and include your EODHD API key:

```
EODHD_API_KEY=your_actual_eodhd_api_key
```

### 4. Running the Server

```bash
python server.py
```

This starts the MCP HTTP server on `http://127.0.0.1:8000/mcp`.

## MCP Tools & Endpoints

The following MCP tools are available:

### Main Endpoints
- `get_historical_stock_prices`
- `get_live_price_data`
- `get_intraday_historical_data`
- `get_current_stock_price`
- `get_us_tick_data`
- `get_historical_market_cap`
- `get_company_news`
- `get_sentiment_data`
- `get_news_word_weights`
- `get_exchanges_list`
- `get_exchange_tickers`
- `get_exchange_details`
- `get_macro_indicator`
- `get_economic_events`
- `get_symbol_change_history`
- `get_stocks_from_search`
- `get_user_details`
- `get_insider_transactions`
- `get_capture_realtime_ws`
- `get_stock_screener_data`
- `get_upcoming_earnings`
- `get_earnings_trends`
- `get_upcoming_ipos`
- `get_upcoming_splits`
- `get_fundamentals_data`

### Marketplace Endpoints
- `get_mp_us_options_contracts`
- `get_mp_us_options_eod`
- `get_mp_us_options_underlyings`
- `get_mp_indices_list`
- `get_mp_index_components`

## Example Client Usage

Here's a basic client-side example of using the MCP client to query data from the server:

```python
from fastmcp import Client
import asyncio
import json

async def main():
    async with Client("http://127.0.0.1:8000/mcp") as client:
        result = await client.call_tool(
            "get_historical_stock_prices",
            {
                "ticker": "AAPL.US",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31"
            }
        )
        data = json.loads(result.text)
        print(json.dumps(data, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
```

## Project Structure

```
eodhd-mcp-server/
├── app/
│   └── tools/                 # MCP tool implementations
├── server.py                  # MCP server implementation
├── .env                       # Environment variables (API keys)
├── requirements.txt           # Python dependencies
└── README.md                  # Project documentation
```

## Dependencies

* Python 3.10+
* FastMCP


Install dependencies with:

```bash
pip install -r requirements.txt
```

## License

This project is licensed under the Apache License 2.0. See the LICENSE file for details.

## Contributing

Contributions are welcome! Please submit pull requests or open issues if you encounter problems or have enhancement suggestions.
