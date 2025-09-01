# This module registers all your test cases in one place.
# You can split into multiple files later (e.g. tests/eod.py, tests/news.py)
# and add them to TEST_MODULES in test_client.py.

def register(add_test, COMMON):
    # --- End of Day API ---
    add_test({
        "name": "EOD: AAPL Jan-Feb 2023",
        "tool": "get_historical_stock_prices",
        "use_common": ["api_token", "fmt", "start_date", "end_date"],
        "params": {
            "ticker": "AAPL.US",

        },
    })

    # --- Live (Delayed) ---
    add_test({
        "name": "Live: AAPL + extras",
        "tool": "get_live_price_data",
        "use_common": ["fmt"],  # token optional; env works
        "params": {
            "ticker": "AAPL.US",
            "additional_symbols": ["VTI", "EUR.FOREX"],
        },
    })

    # --- Intraday ---
    add_test({
        "name": "Intraday: AAPL 1m range",
        "tool": "get_intraday_historical_data",
        "use_common": ["fmt"],
        "params": {
            "ticker": "AAPL.US",
            "interval": "1m",
            "from_timestamp": 1627896900,  # 2021-08-02 09:35:00 UTC
            "to_timestamp": 1628069700,    # 2021-08-04 09:35:00 UTC
            "split_dt": False,
        },
    })

    # --- News by ticker ---
    add_test({
        "name": "News: by ticker AAPL",
        "tool": "get_company_news",
        "use_common": ["fmt"],
        "params": {
            "ticker": "AAPL.US",
            "limit": 5,
            "offset": 0,
        },
    })

    # --- News by tag ---
    add_test({
        "name": "News: by tag AI",
        "tool": "get_company_news",
        "use_common": ["fmt", "api_token", "limit", "offset", "api_token"],
        "params": {
            "tag": "ARTIFICIAL INTELLIGENCE",

        },
    })

    # --- Sentiment ---
    add_test({
        "name": "Sentiment: BTC + AAPL Q1 2022",
        "tool": "get_sentiment_data",
        "use_common": ["fmt", "start_date", "end_date"],
        "params": {
            "symbols": "BTC-USD.CC,AAPL.US",

        },
    })

    # --- News Word Weights ---
    add_test({
        "name": "News Word Weights: AAPL top 10 words",
        "tool": "get_news_word_weights",
        "use_common": ["fmt"],
        "params": {
            "ticker": "AAPL.US",
            "start_date": "2025-04-08",
            "end_date": "2025-04-16",
            "limit": 10,
        },
    })

    # --- Search ---
    add_test({
        "name": "Search: by ticker",
        "tool": "get_stocks_from_search",
        "use_common": ["fmt"],
        "params": {
            "query": "AAPL",
            "limit": 10,
            "api_token": "demo",  # NOTE: Demo won't work for Search API in prod; override as needed
        },
    })
    add_test({
        "name": "Search: by name (filtered US stock)",
        "tool": "get_stocks_from_search",
        "use_common": ["fmt"],
        "params": {
            "query": "Apple Inc",
            "limit": 5,
            "exchange": "US",
            "type": "stock",
            "api_token": "demo",  # replace with real token
        },
    })
    add_test({
        "name": "Search: bonds-only ISIN",
        "tool": "get_stocks_from_search",
        "use_common": ["fmt"],
        "params": {
            "query": "US0378331005",
            "limit": 3,
            "bonds_only": True,
            "api_token": "demo",  # replace with real token
        },
    })

    # --- Exchanges list / tickers / details ---
    add_test({
        "name": "Exchanges: list",
        "tool": "get_exchanges_list",
        "use_common": ["fmt"],
        "params": {},
    })
    add_test({
        "name": "Exchange tickers: US unified",
        "tool": "get_exchange_tickers",
        "use_common": ["fmt"],
        "params": {
            "exchange_code": "US",
        },
    })
    add_test({
        "name": "Exchange tickers: WAR stock",
        "tool": "get_exchange_tickers",
        "use_common": ["fmt"],
        "params": {
            "exchange_code": "WAR",
            "type": "stock",
        },
    })
    add_test({
        "name": "Exchange details: US (default window)",
        "tool": "get_exchange_details",
        "use_common": ["fmt"],
        "params": {
            "exchange_code": "US",
        },
    })
    add_test({
        "name": "Exchange details: US (explicit window)",
        "tool": "get_exchange_details",
        "use_common": ["fmt"],
        "params": {
            "exchange_code": "US",
            "start_date": "2023-04-01",
            "end_date": "2024-02-28",
        },
    })

    # --- Macro Indicators ---
    add_test({
        "name": "Macro: USA default (gdp_current_usd)",
        "tool": "get_macro_indicator",
        "use_common": ["fmt"],
        "params": {
            "country": "USA",
        },
    })
    add_test({
        "name": "Macro: FRA inflation_consumer_prices_annual",
        "tool": "get_macro_indicator",
        "use_common": ["fmt"],
        "params": {
            "country": "FRA",
            "indicator": "inflation_consumer_prices_annual",
        },
    })

    # --- User details ---
    add_test({
        "name": "User details (env or override token)",
        "tool": "get_user_details",
        "use_common": [],  # token taken from env by default
        "params": {
            # "api_token": "YOUR_REAL_API_TOKEN",
        },
    })

    # --- Symbol Change History ---
    add_test({
        "name": "Symbol Change History: Oct–Nov 2022",
        "tool": "get_symbol_change_history",
        "use_common": ["fmt"],
        "params": {
            "start_date": "2022-10-01",
            "end_date": "2022-11-01",
        },
    })

    # --- Historical Market Cap ---
    add_test({
        "name": "Historical Market Cap: AAPL weekly (demo window)",
        "tool": "get_historical_market_cap",
        "use_common": ["fmt"],
        "params": {
            "ticker": "AAPL.US",
            "start_date": "2025-03-01",
            "end_date": "2025-04-01",
        },
    })

    # --- Insider Transactions ---
    add_test({
        "name": "Insider Transactions: general window",
        "tool": "get_insider_transactions",
        "use_common": ["fmt"],
        "params": {
            "start_date": "2024-03-01",
            "end_date": "2024-03-02",
            "limit": 20,
        },
    })
    add_test({
        "name": "Insider Transactions: AAPL filter",
        "tool": "get_insider_transactions",
        "use_common": ["fmt"],
        "params": {
            "symbol": "AAPL.US",
            "start_date": "2024-03-01",
            "end_date": "2024-03-15",
            "limit": 10,
        },
    })
