from fastmcp import Client
import asyncio
import json

async def main():
    # Connect via HTTP to the running MCP server
    async with Client("http://127.0.0.1:8000/mcp") as client:
        tools = await client.list_tools()
        #print(f"Available tools: {tools}")
        print("Available tools:", [t["name"] if isinstance(t, dict) else t for t in tools])

        # End of Day API test call
        result = await client.call_tool(
            "get_historical_stock_prices",
            {
                "api_token" : "demo",
                "ticker": "AAPL.US",
                "start_date": "2023-01-01",
                "end_date": "2023-02-01"
            }
        )
        print(f"End of Day API call result:\n{result}")

        # Live (Delayed) price data — single + multiple tickers test call
        live_result = await client.call_tool(
            "get_live_price_data",
            {
                "ticker": "AAPL.US",
                "additional_symbols": ["VTI", "EUR.FOREX"],  # becomes s=VTI,EUR.FOREX
                "fmt": "json",
                # "api_token": "YOUR_TOKEN",  # optional override
            }
        )
        print("Live API call result:\n", live_result)

        # Intraday historical data (1m) with explicit time window
        # Example window: 2021-08-02 09:35:00 UTC to 2021-09-02 09:35:00 UTC
        intraday_result = await client.call_tool(
            "get_intraday_historical_data",
            {
                "ticker": "AAPL.US",
                "interval": "1m",
                "from_timestamp": 1627896900,
                "to_timestamp": 1628069700,
                "fmt": "json",
                "split_dt": False,
                # "api_token": "YOUR_TOKEN",  # optional override
            }
        )
        print("Intraday Result:\n", intraday_result)

        # --- News by ticker ---
        news_by_ticker = await client.call_tool(
            "get_company_news",
            {
                "ticker": "AAPL.US",  # maps to s=AAPL.US
                "limit": 5,
                "offset": 0,
                "fmt": "json",
                # "start_date": "2025-08-01",  # optional
                # "end_date": "2025-08-20",    # optional
                # "api_token": "YOUR_TOKEN",   # optional override
            }
        )
        print("News (ticker):\n", news_by_ticker)

        # --- News by tag ---
        news_by_tag = await client.call_tool(
            "get_company_news",
            {
                "tag": "ARTIFICIAL INTELLIGENCE",  # maps to t=ARTIFICIAL%20INTELLIGENCE
                "limit": 5,
                "offset": 0,
                "fmt": "json",
                "api_token": "demo",
            }
        )
        print("News (tag):\n", news_by_tag)

        # --- Sentiment data test: multiple symbols, date window ---
        sentiment_result = await client.call_tool(
            "get_sentiment_data",
            {
                "symbols": "BTC-USD.CC,AAPL.US",
                "start_date": "2022-01-01",
                "end_date": "2022-04-22",
                "fmt": "json",
                # "api_token": "YOUR_TOKEN",  # optional override
            }
        )
        print("Sentiment Result:\n", sentiment_result)

        # --- News word weights test: AAPL over a short window, top 10 words ---
        nww_result = await client.call_tool(
            "get_news_word_weights",
            {
                "ticker": "AAPL.US",
                "start_date": "2025-04-08",
                "end_date": "2025-04-16",
                "limit": 10,
                "fmt": "json",
                # "api_token": "YOUR_TOKEN",  # optional override
            }
        )
        print("News Word Weights Result:\n", nww_result)

        # --- Search by ticker ---
        search_by_ticker = await client.call_tool(
            "get_stocks_from_search",
            {
                "query": "AAPL",
                "limit": 10,
                "fmt": "json",
                "api_token": "demo",
            }
        )
        print("Search by ticker:\n", search_by_ticker)

        # --- Search by company name with filters ---
        search_by_name = await client.call_tool(
            "get_stocks_from_search",
            {
                "query": "Apple Inc",
                "limit": 5,
                "exchange": "US",
                "type": "stock",
                "fmt": "json",
                "api_token": "demo",
            }
        )
        print("Search by name (filtered):\n", search_by_name)

        # --- Bonds-only example (shows bonds by ISIN/company text) ---
        search_bonds = await client.call_tool(
            "get_stocks_from_search",
            {
                "query": "US0378331005",  # ISIN example
                "limit": 3,
                "bonds_only": True,
                "fmt": "json",
                "api_token": "demo",
            }
        )
        print("Search bonds-only:\n", search_bonds)

        # --- Get list of exchanges ---
        exchanges_result = await client.call_tool(
            "get_exchanges_list",
            {
                "fmt": "json",
                # "api_token": "YOUR_TOKEN",  # optional override
            }
        )
        print("Exchanges List:\n", exchanges_result)

        # --- Get tickers for an exchange (US unified) ---
        us_tickers = await client.call_tool(
            "get_exchange_tickers",
            {
                "exchange_code": "US",
                "fmt": "json",
                # "type": "stock",          # optional filter
                # "delisted": True,         # include delisted
                # "api_token": "YOUR_TOKEN"
            }
        )
        print("US Tickers (sample):\n", us_tickers)

        # --- Get tickers for WAR exchange (example) with type filter ---
        war_tickers = await client.call_tool(
            "get_exchange_tickers",
            {
                "exchange_code": "WAR",
                "type": "stock",
                "fmt": "json",
                # "api_token": "YOUR_TOKEN"
            }
        )
        print("WAR Tickers (stock):\n", war_tickers)

        # --- Macro Indicators: default indicator (GDP current USD) for USA ---
        macro_gdp = await client.call_tool(
            "get_macro_indicator",
            {
                "country": "USA",
                "fmt": "json",
                # "api_token": "YOUR_TOKEN",  # optional override
            }
        )
        print("Macro (USA, default gdp_current_usd):\n", macro_gdp)

        # --- Macro Indicators: inflation consumer prices annual for France ---
        macro_infl_fr = await client.call_tool(
            "get_macro_indicator",
            {
                "country": "FRA",
                "indicator": "inflation_consumer_prices_annual",
                "fmt": "json",
            }
        )
        print("Macro (FRA, inflation_consumer_prices_annual):\n", macro_infl_fr)

        # --- User details using API token (EODHD_API_KEY) ---
        user_details = await client.call_tool(
            "get_user_details",
            {
                # Replace with a real token if you want to override the env one:
                # "api_token": "YOUR_REAL_API_TOKEN"
            }
        )
        print("User (token):\n", user_details)

        # --- Exchange details: US (with holidays default window) ---
        us_details = await client.call_tool(
            "get_exchange_details",
            {
                "exchange_code": "US",
                "fmt": "json",
                # "api_token": "YOUR_TOKEN",  # optional override
            }
        )
        print("Exchange Details (US):\n", us_details)

        # --- Exchange details: US (with explicit holidays range) ---
        us_details_window = await client.call_tool(
            "get_exchange_details",
            {
                "exchange_code": "US",
                "start_date": "2023-04-01",  # maps to from=
                "end_date": "2024-02-28",  # maps to to=
                "fmt": "json",
            }
        )
        print("Exchange Details (US, with date window):\n", us_details_window)

        # --- Symbol Change History (US-only): Oct 1–Nov 1, 2022 (docs example) ---
        symchg = await client.call_tool(
            "get_symbol_change_history",
            {
                "start_date": "2022-10-01",  # maps to from=
                "end_date": "2022-11-01",  # maps to to=
                "fmt": "json",
                # "api_token": "YOUR_TOKEN",  # optional override; otherwise uses env EODHD_API_KEY
            }
        )
        print("Symbol Change History:\n", symchg)

        # --- Historical Market Cap: AAPL demo window (weekly points) ---
        mcap_result = await client.call_tool(
            "get_historical_market_cap",
            {
                "ticker": "AAPL.US",
                "start_date": "2025-03-01",
                "end_date": "2025-04-01",
                "fmt": "json",
                # "api_token": "YOUR_TOKEN",  # optional override; demo works for AAPL.US
            }
        )
        print("Historical Market Cap:\n", mcap_result)

        # --- Insider Transactions: general window (docs-like example dates) ---
        insiders_all = await client.call_tool(
            "get_insider_transactions",
            {
                "start_date": "2024-03-01",
                "end_date": "2024-03-02",
                "limit": 20,
                "fmt": "json",
                # "api_token": "YOUR_TOKEN",  # optional override
            }
        )
        print("Insider Transactions (general):\n", insiders_all)

        # --- Insider Transactions: filtered for AAPL with a limit ---
        insiders_aapl = await client.call_tool(
            "get_insider_transactions",
            {
                "symbol": "AAPL.US",  # maps to code=AAPL.US (or just "AAPL")
                "start_date": "2024-03-01",
                "end_date": "2024-03-15",
                "limit": 10,
                "fmt": "json",
            }
        )
        print("Insider Transactions (AAPL):\n", insiders_aapl)


if __name__ == "__main__":
    asyncio.run(main())


