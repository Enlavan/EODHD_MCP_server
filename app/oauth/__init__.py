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

from .auth import (
    AuthMiddleware,
    AuthResult,
    get_auth_middleware,
    create_401_response,
    create_403_response,
)

from .oauth_server import (
    OAuthMiddleware,
    create_oauth_routes,
    create_app_with_oauth,
)

from .auth_server import (
    create_auth_server_app,
    TokenStorage,
    get_storage,
)

from .mount_apps import (
    create_multi_mount_app,
    run_multi_mount_server,
)

__all__ = [
    # OAuth validation
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
    # Authentication
    "AuthMiddleware",
    "AuthResult",
    "get_auth_middleware",
    "create_401_response",
    "create_403_response",
    # OAuth Server
    "OAuthMiddleware",
    "create_oauth_routes",
    "create_app_with_oauth",
    # Auth Server
    "create_auth_server_app",
    "TokenStorage",
    "get_storage",
    # Multi-mount
    "create_multi_mount_app",
    "run_multi_mount_server",
]
