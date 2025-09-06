# This module registers all your test cases in one place.
# You can split into multiple files later (e.g. tests/eod.py, tests/news.py)
# and add them to TEST_MODULES in test_client.py.

def register(add_test, COMMON):
    # --- End of Day API ---
    add_test({
        "name": "EOD: AAPL Jan-Feb 2023",
        "tool": "get_historical_stock_prices",
        "use_common": ["api_token", "fmt", "start_date", "end_date", "ticker"],
        "params": {
            #"ticker": "AAPL.US",

        },
    })

    # --- Live (Delayed) ---
    add_test({
        "name": "Live: AAPL + extras",
        "tool": "get_live_price_data",
        "use_common": ["fmt", "api_token", "ticker"],  # token optional; env works
        "params": {
            #"ticker": "AAPL.US",
            "additional_symbols": ["VTI", "EUR.FOREX"],
        },
    })

    # --- Intraday ---
    add_test({
        "name": "Intraday: 1m range",
        "tool": "get_intraday_historical_data",
        "use_common": ["fmt", "api_token", "ticker"],
        "params": {
            #"ticker": "AAPL.US",
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

    # --- Sentiment ---
    add_test({
        "name": "Sentiment: BTC + AAPL Q1 2022",
        "tool": "get_sentiment_data",
        "use_common": ["fmt", "start_date", "end_date", "api_token"],
        "params": {
            "symbols": "BTC-USD.CC,AAPL.US",

        },
    })

    # --- News Word Weights ---
    add_test({
        "name": "News Word Weights: AAPL top 10 words",
        "tool": "get_news_word_weights",
        "use_common": ["fmt", "api_token"],
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
        "use_common": ["fmt", "api_token"],
        "params": {
            "query": "AAPL",
            "limit": 10,
            #"api_token": "demo",  # NOTE: Demo won't work for Search API in prod; override as needed
        },
    })
    add_test({
        "name": "Search: by name (filtered US stock)",
        "tool": "get_stocks_from_search",
        "use_common": ["fmt", "api_token"],
        "params": {
            "query": "Apple Inc",
            "limit": 5,
            "exchange": "US",
            "type": "stock",
           # "api_token": "demo",  # replace with real token
        },
    })
    add_test({
        "name": "Search: bonds-only ISIN",
        "tool": "get_stocks_from_search",
        "use_common": ["fmt", "api_token"],
        "params": {
            "query": "US0378331005",
            "limit": 3,
            "bonds_only": True,
            #"api_token": "demo",  # replace with real token
        },
    })

    # --- Exchanges list / tickers / details ---
    add_test({
        "name": "Exchanges: list",
        "tool": "get_exchanges_list",
        "use_common": ["fmt", "api_token"],
        "params": {},
    })
    add_test({
        "name": "Exchange tickers: US unified",
        "tool": "get_exchange_tickers",
        "use_common": ["fmt", "api_token"],
        "params": {
            "exchange_code": "US",
        },
    })
    add_test({
        "name": "Exchange tickers: WAR stock",
        "tool": "get_exchange_tickers",
        "use_common": ["fmt", "api_token"],
        "params": {
            "exchange_code": "WAR",
            "type": "stock",
        },
    })
    add_test({
        "name": "Exchange details: US (default window)",
        "tool": "get_exchange_details",
        "use_common": ["fmt", "api_token"],
        "params": {
            "exchange_code": "US",
        },
    })
    add_test({
        "name": "Exchange details: US (explicit window)",
        "tool": "get_exchange_details",
        "use_common": ["fmt", "api_token"],
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
        "use_common": ["fmt", "api_token"],
        "params": {
            "country": "USA",
        },
    })
    add_test({
        "name": "Macro: FRA inflation_consumer_prices_annual",
        "tool": "get_macro_indicator",
        "use_common": ["fmt", "api_token"],
        "params": {
            "country": "FRA",
            "indicator": "inflation_consumer_prices_annual",
        },
    })

    # --- User details ---
    add_test({
        "name": "User details (env or override token)",
        "tool": "get_user_details",
        "use_common": ["api_token"],  # token taken from env by default
        "params": {
            # "api_token": "YOUR_REAL_API_TOKEN",
        },
    })

    # --- Symbol Change History ---
    add_test({
        "name": "Symbol Change History: Oct–Nov 2022",
        "tool": "get_symbol_change_history",
        "use_common": ["fmt", "api_token"],
        "params": {
            "start_date": "2022-10-01",
            "end_date": "2022-11-01",
        },
    })

    # --- Historical Market Cap ---
    add_test({
        "name": "Historical Market Cap: AAPL weekly (demo window)",
        "tool": "get_historical_market_cap",
        "use_common": ["fmt", "api_token"],
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
        "use_common": ["fmt", "api_token"],
        "params": {
            "start_date": "2024-03-01",
            "end_date": "2024-03-02",
            "limit": 20,
        },
    })
    add_test({
        "name": "Insider Transactions: AAPL filter",
        "tool": "get_insider_transactions",
        "use_common": ["fmt", "api_token" ,"symbol"],
        "params": {
            "start_date": "2024-03-01",
            "end_date": "2024-03-15",
            "limit": 10,
        },
    })

    # --- WebSockets: US trades (AAPL, MSFT, TSLA) ---
    add_test({
        "name": "WS: US trades AAPL,MSFT,TSLA (demo)",
        "tool": "capture_realtime_ws",
        "use_common": ["api_token"],
        "params": {
            "feed": "us_trades",
            "symbols": ["AAPL", "MSFT", "TSLA"],  # demo supports these
            "duration_seconds": 4,
            #"max_messages": 200,  # optional safety cap
        },
    })

    # --- WebSockets: Crypto (ETH-USD, BTC-USD) ---
    add_test({
        "name": "WS: Crypto ETH-USD,BTC-USD (demo)",
        "tool": "capture_realtime_ws",
        "use_common": ["api_token"],
        "params": {
            "feed": "crypto",
            "symbols": ["ETH-USD", "BTC-USD"],
            "duration_seconds": 4,
        },
    })

    # --- WebSockets: Forex (EURUSD) ---
    add_test({
        "name": "WS: Forex EURUSD (demo)",
        "tool": "capture_realtime_ws",
        "use_common": ["api_token"],
        "params": {
            "feed": "forex",
            "symbols": "EURUSD",
            "duration_seconds": 4,
        },
    })

    # --- US Tick Data: AAPL sample window (docs example times) ---
    add_test({
        "name": "US Ticks: AAPL 2023-09-11 18:00 → 2023-09-12 18:00 (limit 5)",
        "tool": "get_us_tick_data",
        "use_common": ["fmt" , "api_token" ,  "ticker"],  # token via env or override in params
        "params": {
            "from_timestamp": 1694455200,  # 2023-09-11 18:00:00 UTC
            "to_timestamp": 1694541600,  # 2023-09-12 18:00:00 UTC
            "limit": 5,
        },
    })

    # Optional: another quick tick sample (TSLA) if you have a paid token
    add_test({
        "name": "US Ticks: TSLA short window (limit 5)",
        "tool": "get_us_tick_data",
        "use_common": ["fmt", "api_token"],
        "params": {
            "ticker": "TSLA",
            "from_timestamp": 1694455200,
            "to_timestamp": 1694462400,  # +2h
            "limit": 5,
            # "api_token": "YOUR_TOKEN",
        },
    })

    # 1) OPTIONS: Get contracts — narrow filter, fields subset, limit 5
    add_test({
        "name": "Options: contracts (AAPL, strike=450 put, exp=2027-01-15, fields subset, limit=5)",
        "tool": "get_us_options_contracts",
        "use_common": ["api_token", "fmt"],
        "params": {
            "underlying_symbol": "AAPL",
            "strike_eq": 450,
            "type": "put",
            "exp_date_eq": "2027-01-15",
            "fields": ["contract", "bid_date", "open", "high", "low", "last"],
            "page_limit": 5,
            "sort": "-exp_date",
            # "api_token": "demo",  # demo works for AAPL
        },
    })

    # Broader contracts query to exercise pagination/meta/links
    add_test({
        "name": "Options: contracts (AAPL, limit=4)",
        "tool": "get_us_options_contracts",
        "use_common": ["api_token", "fmt"],
        "params": {
            "underlying_symbol": "AAPL",
            "page_limit": 4,
            # "api_token": "demo",
        },
    })

    # 2) OPTIONS EOD: by contract with field subset, limit=5, compact off
    add_test({
        "name": "Options: EOD (AAPL270115P00450000, fields subset, limit=5, compact=0)",
        "tool": "get_us_options_eod",
        "use_common": ["api_token", "fmt"],
        "params": {
            "contract": "AAPL270115P00450000",
            "strike_eq": 450,
            "type": "put",
            "exp_date_eq": "2027-01-15",
            "fields": ["contract", "bid_date", "open", "high", "low", "last"],
            "page_limit": 5,
            "sort": "-exp_date",
            "compact": False,
            # "api_token": "demo",
        },
    })

    # OPTIONS EOD: minimal filter by contract only, default fields, limit=5
    add_test({
        "name": "Options: EOD (contract only, limit=5)",
        "tool": "get_us_options_eod",
        "use_common": ["api_token", "fmt"],
        "params": {
            "contract": "AAPL270115P00450000",
            "page_limit": 5,
            # "api_token": "demo",
        },
    })

    # 3) OPTIONS: underlying symbols list
    add_test({
        "name": "Options: underlying symbols list",
        "tool": "get_us_options_underlyings",
        "use_common": ["api_token", "fmt"],
        "params": {
            # You can add page_offset/page_limit if you want smaller page sizes:
             "page_limit": 50,
            # "api_token": "demo",
        },
    })

    # Economic Events: US, 2025-01-05 to 2025-01-06 (docs-like example), large limit
    add_test({
        "name": "Economic Events: US window (2025-01-05..2025-01-06, limit=1000)",
        "tool": "get_economic_events",
        "use_common": ["fmt", "api_token"],  # use COMMON defaults for fmt/json if you defined them
        "params": {
            "start_date": "2025-01-05",
            "end_date": "2025-01-06",
            "country": "US",
            "limit": 1000,
            # "api_token": "YOUR_TOKEN",  # or rely on env EODHD_API_KEY
        },
    })

    # Economic Events: filter by comparison + type (illustrative)
    add_test({
        "name": "Economic Events: comparison=mom + type='Factory Orders'",
        "tool": "get_economic_events",
        "use_common": ["fmt", "api_token"],
        "params": {
            "start_date": "2025-01-05",
            "end_date": "2025-01-06",
            "country": "US",
            "comparison": "mom",
            "type": "Factory Orders",
            "limit": 200,
        },
    })

    # Earnings by date window (docs-style example)
    add_test({
        "name": "Upcoming Earnings: window 2018-12-02..2018-12-03 (json)",
        "tool": "get_upcoming_earnings",
        "use_common": ["fmt", "api_token"],  # will default to json if COMMON sets it
        "params": {
            "start_date": "2018-12-02",
            "end_date": "2018-12-03",
            #"fmt": "json",
            # "api_token": "YOUR_TOKEN",  # or rely on env EODHD_API_KEY
        },
    })

    # Earnings for specific symbols (AAPL.US, MSFT.US, AI.PA) — from/to ignored by API when symbols present
    add_test({
        "name": "Upcoming Earnings: symbols AAPL.US,MSFT.US,AI.PA (json)",
        "tool": "get_upcoming_earnings",
        "use_common": ["fmt", "api_token"],
        "params": {
            "symbols": ["AAPL.US", "MSFT.US", "AI.PA"],
            "start_date": "2018-01-01",  # will be ignored by API when symbols present
            "end_date": "2018-04-04",  # will be ignored by API when symbols present
            #"fmt": "json",
        },
    })
    # --- Earnings Trends: single symbol (AAPL.US) ---
    add_test({
        "name": "Earnings Trends: AAPL.US",
        "tool": "get_earnings_trends",
        "use_common": ["fmt", "api_token"],  # COMMON["fmt"] typically "json"
        "params": {
            "symbols": "AAPL.US",
            #"fmt": "json",
            # "api_token": "YOUR_TOKEN",  # optional; default env EODHD_API_KEY
        },
    })

    # --- Earnings Trends: multiple symbols (AAPL.US, MSFT.US, AI.PA) ---
    add_test({
        "name": "Earnings Trends: AAPL.US,MSFT.US,AI.PA",
        "tool": "get_earnings_trends",
        "use_common": ["fmt", "api_token"],
        "params": {
            "symbols": ["AAPL.US", "MSFT.US", "AI.PA"],
            #"fmt": "json",
        },
    })
    # --- Upcoming IPOs: windowed, JSON ---
    add_test({
        "name": "Upcoming IPOs: 2018-12-02..2018-12-06 (JSON)",
        "tool": "get_upcoming_ipos",
        "use_common": ["api_token", "fmt"],
        "params": {
            "from_date": "2018-12-02",
            "to_date": "2018-12-06",
            # "api_token": "YOUR_TOKEN",  # optional, else env EODHD_API_KEY
        },
    })

    # --- Upcoming IPOs: default server window (today..+7) ---
    add_test({
        "name": "Upcoming IPOs: default window (server)",
        "tool": "get_upcoming_ipos",
        "use_common": ["fmt", "api_token"],
        "params": {
            #"fmt": "json",
        },
    })

    # --- Upcoming IPOs: CSV sample (optional) ---
    add_test({
        "name": "Upcoming IPOs: CSV sample window",
        "tool": "get_upcoming_ipos",
        "use_common": ["api_token"],
        "params": {
            "from_date": "2018-12-02",
            "to_date": "2018-12-06",
            "fmt": "csv",
        },
    })

    # --- Upcoming Splits: explicit window, JSON ---
    add_test({
        "name": "Upcoming Splits: 2018-12-02..2018-12-06 (JSON)",
        "tool": "get_upcoming_splits",
        "use_common": ["fmt", "api_token"],
        "params": {
            "from_date": "2018-12-02",
            "to_date": "2018-12-06",
           # "fmt": "json",
            # "api_token": "YOUR_TOKEN",  # optional; else env EODHD_API_KEY
        },
    })

    # --- Upcoming Splits: server default window (today..+7) ---
    add_test({
        "name": "Upcoming Splits: default window (server)",
        "tool": "get_upcoming_splits",
        "use_common": ["fmt", "api_token"],
        "params": {
            #"fmt": "json",
        },
    })

    # --- Upcoming Splits: CSV sample ---
    add_test({
        "name": "Upcoming Splits: CSV (2018-12-02..2018-12-06)",
        "tool": "get_upcoming_splits",
        "use_common": ["api_token"],
        "params": {
            "from_date": "2018-12-02",
            "to_date": "2018-12-06",
            "fmt": "csv",
        },
    })
    # --- mp_indices_list: happy path JSON ---
    add_test({
        "name": "MP Indices List: JSON basics",
        "tool": "mp_indices_list",
        "use_common": ["fmt", "api_token"],  # if COMMON has fmt='json'
        "params": {
            #"fmt": "json",
            # "api_token": "YOUR_TOKEN",  # optional; else env EODHD_API_KEY
        },
    })


    # --- mp_index_components: S&P 500 (sample) ---
    add_test({
        "name": "MP Index Components: GSPC.INDX JSON",
        "tool": "mp_index_components",
        "use_common": ["fmt", "api_token"],  # if COMMON has fmt='json'
        "params": {
            "symbol": "GSPC.INDX",
            #"fmt": "json",
        },
    })

    # --- Stock Screener: happy path with JSON filters (as string) ---
    add_test({
        "name": "Screener: basic market_cap desc with filter string",
        "tool": "stock_screener",
        "use_common": ["fmt", "api_token"],
        "params": {
            "sort": "market_capitalization.desc",
            "filters": '[[\"market_capitalization\",\"\\u003e\",1000],[\"name\",\"match\",\"apple\"],[\"code\",\"=\",\"AAPL\"],[\"exchange\",\"=\",\"us\"],[\"sector\",\"=\",\"Technology\"]]',
            "limit": 10,
            "offset": 0
        },
    })

    # --- Stock Screener: python list filters (module will JSON-encode) ---
    add_test({
        "name": "Screener: list filters + signals list",
        "tool": "stock_screener",
        "use_common": ["fmt", "api_token"],
        "params": {
            "sort": "market_capitalization.desc",
            "filters": [
                ["market_capitalization", ">", 10000]
            ],
            "signals": ["bookvalue_neg", "200d_new_lo"],
            "limit": 10,
            "offset": 0
        },
    })

    # --- Stock Screener: signals as comma string ---
    add_test({
        "name": "Screener: signals string",
        "tool": "stock_screener",
        "use_common": ["fmt", "api_token"],
        "params": {
            "signals": "bookvalue_neg,200d_new_lo",
            "limit": 5,
            "offset": 0
        },
    })




