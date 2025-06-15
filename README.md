# EODHD MCP Server

**EODHD MCP Server** is a Python-based Microservice Communication Protocol (MCP) server designed to provide comprehensive access to financial and market data via the **EOD Historical Data (EODHD)** API. This MCP server enables users to easily fetch and manipulate financial datasets including income statements, balance sheets, cash flows, historical and intraday stock prices, and search for companies or stocks.

## Overview

This project provides easy-to-use MCP endpoints for retrieving various financial datasets using EODHD’s API. Users can leverage the server to integrate financial data into their applications or financial analysis workflows.

### Core Features:

- Income Statements
- Balance Sheets
- Cash Flow Statements
- Current Stock Prices
- Historical Stock Prices
- Intraday Historical Stock Data
- Company News
- Stock Search Functionality

## Setup and Installation

### 1. Clone the Repository

git clone https://github.com/yourusername/eodhd-mcp-server.git
cd eodhd-mcp-server

### 2. Install Dependencies

pip install fastmcp httpx python-dotenv

### 3. Configure Environment Variables

Create a `.env` file at the root of your project and include your EODHD API key:

EODHD_API_KEY=your_actual_eodhd_api_key

### 4. Running the Server

python server.py

This starts the MCP HTTP server on `http://127.0.0.1:8000/mcp`.

## MCP Tools & Endpoints

The following MCP tools are available:

| Tool Name                      | Description                             |
| ------------------------------ | --------------------------------------- |
| `get_income_statements`        | Fetch income statements for a ticker    |
| `get_balance_sheets`           | Fetch balance sheets for a ticker       |
| `get_cash_flow_statements`     | Fetch cash flow statements for a ticker |
| `get_current_stock_price`      | Fetch current stock price for a ticker  |
| `get_historical_stock_prices`  | Fetch historical prices for a ticker    |
| `get_intraday_historical_data` | Fetch intraday historical data          |
| `get_company_news`             | Fetch recent news for a ticker          |
| `search_stocks`                | Search for stocks or companies          |

## Example Client Usage

Here's a basic client-side example of using the MCP client to query data from the server:

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

## Project Structure

eodhd-mcp-server/
├── server.py                # MCP server implementation
├── .env                     # Environment variables (API keys)
├── requirements.txt         # Python dependencies
└── README.md                # Project documentation

## Dependencies

* Python 3.10+
* FastMCP
* httpx
* python-dotenv

Install dependencies with:

pip install -r requirements.txt

## License

This project is licensed under the MIT License.

## Contributing

Contributions are welcome! Please submit pull requests or open issues if you encounter problems or have enhancement suggestions.


