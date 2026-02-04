# This module registers all test cases in one place.

def register(add_test, COMMON):
    # --- Intraday ---
    add_test({
        "name": "Intraday: 1m range",
        "tool": "get_intraday_historical_data",
        "use_common": ["fmt", "api_token", "ticker"],
        "params": {
            "interval": "1m",
            "from_timestamp": 1627896900,  # 2021-08-02 09:35:00 UTC
            "to_timestamp": 1628069700,    # 2021-08-04 09:35:00 UTC
            "split_dt": False,
        },
    })

    # --- End of Day API ---
    add_test({
        "name": "EOD: AAPL Jan-Feb 2023",
        "tool": "get_historical_stock_prices",
        "use_common": ["api_token", "fmt", "start_date", "end_date", "ticker"],
        "params": {},
    })

    # --- Live (Delayed) ---
    add_test({
        "name": "Live: AAPL + extras",
        "tool": "get_live_price_data",
        "use_common": ["fmt", "api_token", "ticker"],
        "params": {
            "additional_symbols": ["VTI", "EUR.FOREX"],
        },
    })

    # --- News by ticker ---
    add_test({
        "name": "News: by ticker AAPL",
        "tool": "get_company_news",
        "use_common": ["fmt", "api_token"],
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
        "use_common": ["fmt", "api_token", "limit", "offset"],
        "params": {
            "tag": "ARTIFICIAL INTELLIGENCE",
        },
    })

    # --- Exchanges list ---
    add_test({
        "name": "Exchanges: list",
        "tool": "get_exchanges_list",
        "use_common": ["api_token"],
        "params": {},
    })

    # --- Exchange tickers ---
    add_test({
        "name": "Exchange tickers: US",
        "tool": "get_exchange_tickers",
        "use_common": ["api_token"],
        "params": {
            "exchange_code": "US",
            "delisted": False,
        },
    })

    # --- Search ---
    add_test({
        "name": "Search: by ticker",
        "tool": "get_stocks_from_search",
        "use_common": ["fmt", "api_token"],
        "params": {
            "query": "AAPL",
            "limit": 10,
        },
    })

    # --- User details ---
    add_test({
        "name": "User: details",
        "tool": "get_user_details",
        "use_common": ["api_token"],
        "params": {},
    })
