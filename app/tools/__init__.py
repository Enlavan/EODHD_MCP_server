# app/tools/__init__.py

import importlib
import logging
from typing import Iterable, List, Set

logger = logging.getLogger("eodhd-mcp.tools")

# --- Tool module names (filenames without .py) ---

MAIN_TOOLS: List[str] = [
    "get_historical_stock_prices",
    "get_live_price_data",
    "get_intraday_historical_data",
    "get_company_news",
    "get_exchanges_list",
    "get_exchange_tickers",
    "get_stocks_from_search",
    "get_user_details",
]

MARKETPLACE_TOOLS: List[str] = [

]

THIRD_PARTY_TOOLS: List[str] = [

]

ALL_TOOLS: List[str] = MAIN_TOOLS + MARKETPLACE_TOOLS + THIRD_PARTY_TOOLS


def _safe_register(mcp, module_name: str, attr: str = "register") -> None:
    """
    Import .{module_name} and call its register(mcp), logging and skipping on errors.
    """
    try:
        mod = importlib.import_module(f".{module_name}", package=__name__)
    except ModuleNotFoundError as e:
        logger.warning("Skipping tool '%s': module not found (%s)", module_name, e)
        return
    except Exception as e:
        logger.error("Error importing tool '%s': %s: %s", module_name, type(e).__name__, e)
        return

    fn = getattr(mod, attr, None)
    if not callable(fn):
        logger.warning("Skipping tool '%s': no callable '%s()' found", module_name, attr)
        return

    try:
        fn(mcp)
        logger.info("Registered tool: %s.%s", module_name, attr)
    except Exception as e:
        logger.error("Failed to register tool '%s': %s: %s", module_name, type(e).__name__, e)


def _dedupe(seq: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for item in seq:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return out


def register_all(mcp) -> None:
    """Attempt to register every known tool, skipping any that are missing or erroring."""
    for name in _dedupe(ALL_TOOLS):
        _safe_register(mcp, name)
