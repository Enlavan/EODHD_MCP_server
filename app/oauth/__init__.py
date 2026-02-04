# app/oauth/__init__.py
# OAuth 2.1 Support for EODHD MCP Server

from .oauth import (
    OAuthValidator,
    TokenInfo,
    get_validator,
    get_protected_resource_metadata,
    get_www_authenticate_header,
    get_required_scopes,
    SCOPES,
    TOOL_SCOPES,
    OAUTH_ISSUER,
    MCP_SERVER_URL,
)


from .auth_server import (
    create_auth_server_app,
)

from .token_storage import (
    TokenStorage,
    get_storage,
)

from app.mount_apps import (
    create_multi_mount_app,
    run_multi_mount_server,
)

__all__ = [
    "OAuthValidator",
    "TokenInfo",
    "get_validator",
    "get_protected_resource_metadata",
    "get_www_authenticate_header",
    "get_required_scopes",
    "SCOPES",
    "TOOL_SCOPES",
    "OAUTH_ISSUER",
    "MCP_SERVER_URL",
    "create_auth_server_app",
    "TokenStorage",
    "get_storage",
    "create_multi_mount_app",
    "run_multi_mount_server",
]
