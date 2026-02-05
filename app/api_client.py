# app/api_client.py

import os
from typing import Optional, Tuple, Dict, Any

import httpx
from fastmcp.server.dependencies import get_http_request

# Reuse a single async client to avoid per-request connection overhead.
_client: Optional[httpx.AsyncClient] = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient()
    return _client


def _resolve_eodhd_token_from_request() -> Tuple[Optional[str], bool]:
    """
    Resolve an API token from the active HTTP request, if any.

    Returns:
        (token, is_http_context)
    """
    try:
        req = get_http_request()
    except Exception:
        # Not running under HTTP transport (e.g., stdio), or no active request
        return None, False

    # OAuth middleware injects this for /v2/mcp
    state_token = getattr(getattr(req, "state", None), "eodhd_api_key", None)
    if state_token:
        return str(state_token).strip(), True

    # 1) Authorization: Bearer <token>
    auth = req.headers.get("authorization") or req.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            return token, True

    # 2) X-API-Key (optional)
    xkey = req.headers.get("x-api-key") or req.headers.get("X-API-Key")
    if xkey:
        return xkey.strip(), True

    # 3) Legacy query params
    apikey = req.query_params.get("apikey")
    if apikey:
        return apikey, True

    apikey = req.query_params.get("api_key")
    if apikey:
        return apikey, True

    apikey = req.query_params.get("api-key")
    if apikey:
        return apikey, True

    apikey = req.query_params.get("api_token")
    if apikey:
        return apikey, True

    return None, True


def _ensure_api_token(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Inject api_token into URL query string if missing.

    Returns:
        (url_with_token_or_none, error_message_or_none)
    """
    if "api_token=" in url:
        return url, None

    token, is_http = _resolve_eodhd_token_from_request()
    if token:
        return url + (f"&api_token={token}" if "?" in url else f"?api_token={token}"), None

    # Only allow env/CLI token injection in non-HTTP contexts (e.g., stdio)
    if not is_http:
        env_token = os.getenv("EODHD_API_KEY")
        if env_token:
            return url + (f"&api_token={env_token}" if "?" in url else f"?api_token={env_token}"), None

    return None, "Missing API token. Provide it via OAuth (Bearer), query param, header, or env for stdio."


async def make_request(
    url: str,
    method: str = "GET",
    json_body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0,
) -> Optional[Dict[str, Any]]:
    """
    Generic HTTP request helper for EODHD APIs.

    - Auto-injects api_token into URL if absent.
    - Supports GET (default) and POST with JSON payload.
    - Returns parsed JSON dict on success, or {"error": "..."} on failure.
    """
    url, err = _ensure_api_token(url)
    if err:
        return {"error": err}
    if not url:
        return {"error": "Invalid request URL."}

    m = (method or "GET").upper()

    # Default headers
    req_headers: dict = {}
    if headers:
        req_headers.update(headers)

    # If sending JSON, ensure content-type
    if json_body is not None and "Content-Type" not in {k.title(): v for k, v in req_headers.items()}:
        # Avoid overwriting if caller set it in any case variant
        if "content-type" not in (k.lower() for k in req_headers.keys()):
            req_headers["Content-Type"] = "application/json"

    client = await _get_client()
    try:
        if m == "GET":
            response = await client.get(url, headers=req_headers, timeout=timeout)
        elif m == "POST":
            response = await client.post(url, json=json_body, headers=req_headers, timeout=timeout)
        elif m == "PUT":
            response = await client.put(url, json=json_body, headers=req_headers, timeout=timeout)
        elif m == "DELETE":
            response = await client.delete(url, headers=req_headers, timeout=timeout)
        else:
            return {"error": f"Unsupported HTTP method: {m}"}

        response.raise_for_status()

        # Prefer JSON; if server returns non-JSON (e.g., HTML), return a helpful error object.
        try:
            return response.json()
        except Exception:
            ct = response.headers.get("content-type", "")
            text = response.text
            # Keep the payload small-ish
            if text and len(text) > 2000:
                text = text[:2000] + "…"
            return {
                "error": "Response is not valid JSON.",
                "status_code": response.status_code,
                "content_type": ct,
                "text": text,
            }

    except httpx.HTTPStatusError as e:
        # Server returned a non-2xx
        text = e.response.text
        if text and len(text) > 2000:
            text = text[:2000] + "…"
        return {
            "error": str(e),
            "status_code": e.response.status_code,
            "text": text,
        }
    except Exception as e:
        return {"error": str(e)}
