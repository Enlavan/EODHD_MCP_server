# app/oauth/token_storage.py
"""
Token Storage compatible with FastMCP's recommended storage stack.

FastMCP uses `key_value.aio` (AsyncKeyValue protocol) for storage backends.
We use the same here so OAuth can be enabled/removed with minimal blast radius.

Default storage is in-memory. For production/testing across restarts, set:
  OAUTH_TOKEN_STORAGE_DIR=/var/lib/eodhd-mcp-oauth

Optionally encrypt at rest by providing a Fernet key (32 urlsafe-base64 bytes):
  OAUTH_STORAGE_ENCRYPTION_KEY=...
"""

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Any, Dict, List
from collections.abc import Mapping

logger = logging.getLogger("eodhd-mcp.token_storage")

try:
    from key_value.aio.protocols.key_value import AsyncKeyValue as KeyValue
    from key_value.aio.stores.memory import MemoryStore
    from key_value.aio.stores.disk import DiskStore
except Exception:  # pragma: no cover
    KeyValue = None  # type: ignore
    MemoryStore = None  # type: ignore
    DiskStore = None  # type: ignore

try:
    from key_value.aio.wrappers.fernet import FernetEncryptionWrapper  # type: ignore
except Exception:  # pragma: no cover
    FernetEncryptionWrapper = None  # type: ignore


def _now() -> float:
    return time.time()


def _hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass
class OAuthClient:
    client_id: str
    client_secret: Optional[str]
    redirect_uris: List[str]
    client_name: str
    grant_types: List[str] = field(default_factory=lambda: ["authorization_code"])
    response_types: List[str] = field(default_factory=lambda: ["code"])
    token_endpoint_auth_method: str = "none"  # none|client_secret_post|client_secret_basic
    created_at: float = field(default_factory=_now)


@dataclass
class AuthorizationCode:
    code: str
    client_id: str
    redirect_uri: str
    user_id: str
    scopes: List[str]
    expires_at: float
    code_challenge: Optional[str] = None
    code_challenge_method: Optional[str] = None
    resource: Optional[str] = None


@dataclass
class AccessToken:
    token: str
    client_id: str
    user_id: str
    scopes: List[str]
    expires_at: float
    issued_at: float


@dataclass
class User:
    email: str
    eodhd_api_key: str
    name: str = ""
    subscription_type: str = ""
    scopes: List[str] = field(default_factory=lambda: ["full-access"])
    created_at: float = field(default_factory=_now)


def _build_kv() -> Any:
    """
    Returns a KeyValue instance if available; otherwise a minimal in-memory fallback.
    """
    if KeyValue is None:
        return None

    storage_dir = os.getenv("OAUTH_TOKEN_STORAGE_DIR", "").strip()
    if storage_dir:
        store: Any = DiskStore(storage_dir)
    else:
        store = MemoryStore()

    enc_key = os.getenv("OAUTH_STORAGE_ENCRYPTION_KEY", "").strip()
    if enc_key and FernetEncryptionWrapper is not None:
        store = FernetEncryptionWrapper(store=store, key=enc_key)

    return store


class TokenStorage:
    """
    Async token storage backed by key_value.aio (FastMCP's storage layer).

    Collections:
      - oauth_clients
      - oauth_auth_codes
      - oauth_access_tokens
      - oauth_users
      - oauth_api_key_to_email
    """

    def __init__(self, kv: Any):
        self._kv = kv
        self._fallback: Dict[str, Dict[str, Any]] = {
            "oauth_clients": {},
            "oauth_auth_codes": {},
            "oauth_access_tokens": {},
            "oauth_users": {},
            "oauth_api_key_to_email": {},
        }

    async def _put(self, collection: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if self._kv is None:
            self._fallback[collection][key] = value
            return
        # py-key-value expects a Mapping value; wrap scalars for simple key->value stores.
        if not isinstance(value, Mapping):
            value = {"value": value}
        await self._kv.put(collection=collection, key=key, value=value, ttl=ttl)

    async def _get(self, collection: str, key: str) -> Any:
        if self._kv is None:
            return self._fallback[collection].get(key)
        data = await self._kv.get(collection=collection, key=key)
        if isinstance(data, Mapping) and set(data.keys()) == {"value"}:
            return data.get("value")
        return data

    async def _delete(self, collection: str, key: str) -> None:
        if self._kv is None:
            self._fallback[collection].pop(key, None)
            return
        await self._kv.delete(collection=collection, key=key)

    # --- Users ---
    async def add_user(self, user: User) -> None:
        await self._put("oauth_users", user.email, asdict(user))
        await self._put("oauth_api_key_to_email", _hash_secret(user.eodhd_api_key), user.email)

    async def get_user_by_email(self, email: str) -> Optional[User]:
        data = await self._get("oauth_users", email)
        if not data:
            return None
        return User(**data)

    async def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        email = await self._get("oauth_api_key_to_email", _hash_secret(api_key))
        if not email:
            return None
        return await self.get_user_by_email(str(email))

    # Back-compat aliases (used by earlier middleware versions)
    async def load_user_by_email(self, email: str) -> Optional[User]:
        return await self.get_user_by_email(email)

    async def load_user_by_api_key(self, api_key: str) -> Optional[User]:
        return await self.get_user_by_api_key(api_key)

    # --- Clients ---
    async def register_client(self, client: OAuthClient) -> None:
        await self._put("oauth_clients", client.client_id, asdict(client))

    async def get_client(self, client_id: str) -> Optional[OAuthClient]:
        data = await self._get("oauth_clients", client_id)
        if not data:
            return None
        return OAuthClient(**data)

    # Back-compat alias
    async def load_client(self, client_id: str) -> Optional[OAuthClient]:
        return await self.get_client(client_id)

    # --- Auth Codes ---
    async def store_auth_code(self, code: AuthorizationCode) -> None:
        ttl = max(1, int(code.expires_at - time.time()))
        await self._put("oauth_auth_codes", code.code, asdict(code), ttl=ttl)

    async def consume_auth_code(self, code: str) -> Optional[AuthorizationCode]:
        data = await self._get("oauth_auth_codes", code)
        if not data:
            return None
        await self._delete("oauth_auth_codes", code)
        ac = AuthorizationCode(**data)
        if time.time() > ac.expires_at:
            return None
        return ac

    # --- Access Tokens ---
    async def store_access_token(self, token: AccessToken) -> None:
        ttl = max(1, int(token.expires_at - time.time()))
        await self._put("oauth_access_tokens", _hash_secret(token.token), asdict(token), ttl=ttl)

    async def get_access_token(self, token: str) -> Optional[AccessToken]:
        data = await self._get("oauth_access_tokens", _hash_secret(token))
        if not data:
            return None
        at = AccessToken(**data)
        if time.time() > at.expires_at:
            return None
        return at

    # Convenience helper for resource middleware
    async def get_eodhd_api_key_for_token(self, token: str) -> Optional[str]:
        at = await self.get_access_token(token)
        if not at:
            return None
        user = await self.get_user_by_email(at.user_id)
        return user.eodhd_api_key if user else None

    # Optional alias name some middleware looks for
    async def get_eodhd_api_key_for_token_cached(self, token: str) -> Optional[str]:
        return await self.get_eodhd_api_key_for_token(token)


_storage: Optional[TokenStorage] = None


def get_storage() -> TokenStorage:
    global _storage
    if _storage is None:
        _storage = TokenStorage(_build_kv())
        logger.info("OAuth TokenStorage initialized")
    return _storage
