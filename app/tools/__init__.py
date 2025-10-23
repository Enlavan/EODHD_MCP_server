#"main" endpoints
from .get_historical_stock_prices import register as register_historical_stock_prices
from .get_live_price_data import register as register_live_price_data
from .get_intraday_historical_data import register as register_intraday_historical_data
from .get_company_news import register as register_company_news
from .get_sentiment_data import register as register_sentiment_data
from .get_news_word_weights import register as register_news_word_weights
from .get_exchanges_list import register as register_exchanges_list
from .get_exchange_tickers import register as register_exchange_tickers
from .get_macro_indicator import register as register_macro_indicator
from .get_stocks_from_search import register as register_stocks_from_search
from .get_user_details import register as register_user_details
from .get_exchange_details import register as register_exchange_details
from .get_symbol_change_history import register as register_symbol_change_history
from .get_historical_market_cap import register as register_historical_market_cap
from .get_insider_transactions import register as register_insider_transactions
from .capture_realtime_ws import register as register_capture_realtime_ws
from .get_us_tick_data import register as register_us_tick_data
from .get_stock_screener_data import register as register_stock_screener_data
from .get_economic_events import register as register_economic_events
from .get_upcoming_earnings import register as register_upcoming_earnings
from .get_earnings_trends import register as register_earnings_trends
from .get_upcoming_ipos import register as register_upcoming_ipos
from .get_upcoming_splits import register as register_upcoming_splits
from .get_fundamentals_data import register as register_fundamentals_data


#marketplace endpoints
from .get_mp_us_options_contracts import register as register_mp_us_options_contracts
from .get_mp_us_options_eod import register as register_mp_us_options_eod
from .get_mp_us_options_underlyings import register as register_mp_us_options_underlyings
from .get_mp_indices_list import register as register_mp_indices_list
from .get_mp_index_components import register as register_mp_index_components




def register_all(mcp):
    register_historical_stock_prices(mcp)
    register_live_price_data(mcp)
    register_intraday_historical_data(mcp)
    register_company_news(mcp)
    register_sentiment_data(mcp)
    register_news_word_weights(mcp)
    register_exchanges_list(mcp)
    register_exchange_tickers(mcp)
    register_macro_indicator(mcp)
    register_user_details(mcp)
    register_stocks_from_search(mcp)
    register_exchange_details(mcp)
    register_symbol_change_history(mcp)
    register_historical_market_cap(mcp)
    register_insider_transactions(mcp)
    register_capture_realtime_ws(mcp)
    register_us_tick_data(mcp)
    register_economic_events(mcp)
    register_upcoming_earnings(mcp)
    register_earnings_trends(mcp)
    register_upcoming_ipos(mcp)
    register_upcoming_splits(mcp)
    register_stock_screener_data(mcp)
    register_fundamentals_data(mcp)

    register_mp_us_options_contracts(mcp)
    register_mp_us_options_eod(mcp)
    register_mp_us_options_underlyings(mcp)
    register_mp_indices_list(mcp)
    register_mp_index_components(mcp)




