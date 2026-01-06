# app/api_client.py
#import httpx
#from .config import EODHD_API_KEY

#async def make_request(url: str) -> dict | None:
#    if "api_token=" not in url:
#        url += f"&api_token={EODHD_API_KEY}" if "?" in url else f"?api_token={EODHD_API_KEY}"
#    async with httpx.AsyncClient() as client:
#        try:
#            response = await client.get(url, timeout=30.0)
#            response.raise_for_status()
#            return response.json()
#        except Exception as e:
#            return {"error": str(e)}


# app/api_client.py
import httpx
from .config import EODHD_API_KEY

# FastMCP exposes the current HTTP request (Starlette Request) via dependency
from fastmcp.server.dependencies import get_http_request  # :contentReference[oaicite:1]{index=1}


def _resolve_eodhd_token_from_request() -> str | None:
    """
    Try to read ?apikey=... from the incoming MCP HTTP request.
    Safe to call even outside HTTP context (falls back).
    """
    try:
        req = get_http_request()  # returns starlette.requests.Request :contentReference[oaicite:2]{index=2}
    except RuntimeError:
        # Not running under HTTP transport (e.g., stdio), or no active request
        return None
    except Exception:
        return None

    # Your clients call: /mcp?apikey=....
    apikey = req.query_params.get("apikey")
    if apikey:
        return apikey

    # Optional aliases if you ever change the client
    return req.query_params.get("api_key") or req.query_params.get("token")


async def make_request(url: str) -> dict | None:
    # If tool already provided api_token explicitly, keep it.
    if "api_token=" not in url:
        token = _resolve_eodhd_token_from_request() or EODHD_API_KEY
        url += f"&api_token={token}" if "?" in url else f"?api_token={token}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
