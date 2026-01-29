# app/oauth/auth_server.py
"""
OAuth 2.1 Authorization Server for EODHD MCP Server.

Implements:
- Client registration (Dynamic Client Registration Protocol)
- User authentication
- Authorization endpoint (authorization code grant)
- Token endpoint (exchange code for access token)
- Token introspection (RFC 7662)

Since eodhd.com doesn't provide OAuth, this server implements the full
authorization flow internally.
"""

import os
import secrets
import time
import logging
import hashlib
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
import jwt
import httpx

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse, RedirectResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware

logger = logging.getLogger("eodhd-mcp.auth_server")

# Configuration
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRES = int(os.getenv("ACCESS_TOKEN_EXPIRES", 3600))  # 1 hour
AUTH_CODE_EXPIRES = int(os.getenv("AUTH_CODE_EXPIRES", 600))  # 10 minutes
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_urlsafe(32))

# In-memory storage (can be replaced with persistent storage)
@dataclass
class OAuthClient:
    """OAuth client registration."""
    client_id: str
    client_secret: str
    redirect_uris: list[str]
    client_name: str
    grant_types: list[str] = field(default_factory=lambda: ["authorization_code"])
    response_types: list[str] = field(default_factory=lambda: ["code"])
    created_at: float = field(default_factory=time.time)

@dataclass
class AuthorizationCode:
    """Temporary authorization code."""
    code: str
    client_id: str
    redirect_uri: str
    user_id: str
    scopes: list[str]
    expires_at: float
    code_challenge: Optional[str] = None
    code_challenge_method: Optional[str] = None

@dataclass
class AccessToken:
    """Issued access token."""
    token: str
    client_id: str
    user_id: str
    scopes: list[str]
    expires_at: float
    issued_at: float

@dataclass
class User:
    """User with their EODHD API key."""
    email: str
    eodhd_api_key: str
    name: str = ""
    subscription_type: str = ""
    scopes: list[str] = field(default_factory=lambda: ["full-access"])
    created_at: float = field(default_factory=time.time)

class TokenStorage:
    """In-memory token storage."""

    def __init__(self):
        self.clients: Dict[str, OAuthClient] = {}
        self.auth_codes: Dict[str, AuthorizationCode] = {}
        self.access_tokens: Dict[str, AccessToken] = {}
        # Map email -> User
        self.users: Dict[str, User] = {}
        # Map EODHD API key -> email (for quick lookup)
        self.api_key_to_email: Dict[str, str] = {}

    def add_user(self, user: User) -> None:
        """Add or update a user."""
        self.users[user.email] = user
        self.api_key_to_email[user.eodhd_api_key] = user.email
        logger.info(f"Added user: {user.email}")

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.users.get(email)

    def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        """Get user by their EODHD API key."""
        email = self.api_key_to_email.get(api_key)
        return self.users.get(email) if email else None

    def get_user_scopes(self, email: str) -> list[str]:
        """Get user's granted scopes."""
        user = self.users.get(email)
        return user.scopes if user else []

    def get_eodhd_api_key_for_token(self, access_token: str) -> Optional[str]:
        """Get the EODHD API key associated with an access token."""
        token_obj = self.access_tokens.get(access_token)
        if not token_obj:
            return None
        user = self.users.get(token_obj.user_id)
        return user.eodhd_api_key if user else None

    def register_client(self, client: OAuthClient) -> None:
        """Register a new OAuth client."""
        self.clients[client.client_id] = client

    def get_client(self, client_id: str) -> Optional[OAuthClient]:
        """Get client by ID."""
        return self.clients.get(client_id)

    def verify_client_secret(self, client_id: str, client_secret: str) -> bool:
        """Verify client secret."""
        client = self.get_client(client_id)
        return client is not None and client.client_secret == client_secret

    def store_auth_code(self, code: AuthorizationCode) -> None:
        """Store authorization code."""
        self.auth_codes[code.code] = code

    def consume_auth_code(self, code: str) -> Optional[AuthorizationCode]:
        """Consume authorization code (one-time use)."""
        auth_code = self.auth_codes.pop(code, None)
        if auth_code and time.time() > auth_code.expires_at:
            return None  # Expired
        return auth_code

    def store_access_token(self, token: AccessToken) -> None:
        """Store access token."""
        self.access_tokens[token.token] = token

    def get_access_token(self, token: str) -> Optional[AccessToken]:
        """Get access token."""
        return self.access_tokens.get(token)

    def cleanup_expired(self) -> None:
        """Remove expired codes and tokens."""
        now = time.time()
        # Remove expired auth codes
        self.auth_codes = {
            k: v for k, v in self.auth_codes.items()
            if v.expires_at > now
        }
        # Remove expired tokens
        self.access_tokens = {
            k: v for k, v in self.access_tokens.items()
            if v.expires_at > now
        }

# Global storage instance
_storage = TokenStorage()

def get_storage() -> TokenStorage:
    """Get global token storage."""
    return _storage


# OAuth endpoints

async def register_client_endpoint(request: Request) -> JSONResponse:
    """
    Client registration endpoint (RFC 7591).

    POST /register
    {
        "client_name": "My MCP Client",
        "redirect_uris": ["http://localhost:3000/callback"]
    }
    """
    try:
        data = await request.json()

        client_name = data.get("client_name")
        redirect_uris = data.get("redirect_uris", [])

        if not client_name or not redirect_uris:
            return JSONResponse(
                {"error": "invalid_request", "error_description": "client_name and redirect_uris required"},
                status_code=400
            )

        # Generate client credentials
        client_id = secrets.token_urlsafe(16)
        client_secret = secrets.token_urlsafe(32)

        client = OAuthClient(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uris=redirect_uris,
            client_name=client_name,
        )

        storage = get_storage()
        storage.register_client(client)

        logger.info(f"Registered client: {client_name} (ID: {client_id})")

        return JSONResponse({
            "client_id": client_id,
            "client_secret": client_secret,
            "client_name": client_name,
            "redirect_uris": redirect_uris,
            "grant_types": client.grant_types,
            "response_types": client.response_types,
        })

    except Exception as e:
        logger.error(f"Client registration error: {e}")
        return JSONResponse(
            {"error": "server_error", "error_description": str(e)},
            status_code=500
        )


async def login_page(request: Request) -> HTMLResponse:
    """Display login page."""
    # Get redirect parameters from session
    return_to = request.session.get("oauth_return_to", "/")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>EODHD MCP Server - Login</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 500px;
                margin: 50px auto;
                padding: 20px;
            }}
            .form-group {{
                margin-bottom: 15px;
            }}
            label {{
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }}
            input {{
                width: 100%;
                padding: 10px;
                box-sizing: border-box;
                font-family: monospace;
            }}
            button {{
                background-color: #4CAF50;
                color: white;
                padding: 12px 20px;
                border: none;
                cursor: pointer;
                width: 100%;
                font-size: 16px;
            }}
            button:hover {{
                background-color: #45a049;
            }}
            .error {{
                color: red;
                margin-bottom: 10px;
                padding: 10px;
                background-color: #ffebee;
                border-radius: 5px;
            }}
            .info {{
                background-color: #e3f2fd;
                padding: 15px;
                margin-bottom: 20px;
                border-radius: 5px;
                border-left: 4px solid #2196F3;
            }}
            .help-text {{
                font-size: 12px;
                color: #666;
                margin-top: 5px;
            }}
        </style>
    </head>
    <body>
        <h2>EODHD MCP Server Login</h2>
        <div class="info">
            <strong>Authentication Required</strong><br>
            Please enter your EODHD API key to authenticate.<br>
            <small>Your API key is used to validate your identity and make API requests on your behalf.</small>
        </div>
        {"<div class='error'>" + request.query_params.get("error", "") + "</div>" if "error" in request.query_params else ""}
        <form method="POST" action="/login">
            <div class="form-group">
                <label for="api_key">EODHD API Key:</label>
                <input type="password" id="api_key" name="api_key" required
                       placeholder="Enter your EODHD API key"
                       autocomplete="off">
                <div class="help-text">
                    Find your API key at <a href="https://eodhd.com/cp/settings" target="_blank">eodhd.com/cp/settings</a>
                </div>
            </div>
            <button type="submit">Login</button>
        </form>
    </body>
    </html>
    """
    return HTMLResponse(html)


async def login_submit(request: Request) -> RedirectResponse:
    """Handle login form submission with EODHD API key validation."""
    try:
        form = await request.form()
        api_key = form.get("api_key")

        if not api_key:
            return RedirectResponse(url="/login?error=API+key+is+required", status_code=303)

        storage = get_storage()

        # Check if user already exists (to avoid redundant API calls)
        existing_user = storage.get_user_by_api_key(api_key)
        if existing_user:
            # User already registered, log them in
            request.session["user_id"] = existing_user.email
            request.session["logged_in"] = True
            logger.info(f"User logged in: {existing_user.email}")

            # Redirect to original destination
            return_to = request.session.pop("oauth_return_to", "/")
            return RedirectResponse(url=return_to, status_code=303)

        # Validate API key with EODHD
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    "https://eodhd.com/api/internal-user",
                    params={"api_token": api_key}
                )

                if response.status_code == 200:
                    user_data = response.json()

                    # Extract user information
                    email = user_data.get("email")
                    name = user_data.get("name", "")
                    subscription_type = user_data.get("subscriptionType", "free")

                    if not email:
                        logger.error("EODHD API response missing email field")
                        return RedirectResponse(url="/login?error=Invalid+API+response", status_code=303)

                    # Create and store user
                    user = User(
                        email=email,
                        eodhd_api_key=api_key,
                        name=name,
                        subscription_type=subscription_type,
                        scopes=["full-access"],
                    )
                    storage.add_user(user)

                    # Store user in session
                    request.session["user_id"] = email
                    request.session["logged_in"] = True

                    logger.info(f"New user registered and logged in: {email}")

                    # Redirect to original destination
                    return_to = request.session.pop("oauth_return_to", "/")
                    return RedirectResponse(url=return_to, status_code=303)

                else:
                    logger.warning(f"EODHD API key validation failed: {response.status_code}")
                    return RedirectResponse(
                        url="/login?error=Invalid+API+key+or+EODHD+service+unavailable",
                        status_code=303
                    )

            except httpx.TimeoutException:
                logger.error("EODHD API timeout")
                return RedirectResponse(url="/login?error=Service+timeout.+Please+try+again", status_code=303)
            except Exception as e:
                logger.error(f"EODHD API validation error: {e}")
                return RedirectResponse(url="/login?error=Unable+to+validate+API+key", status_code=303)

    except Exception as e:
        logger.error(f"Login error: {e}")
        return RedirectResponse(url="/login?error=Server+error", status_code=303)


async def authorize_endpoint(request: Request) -> HTMLResponse | RedirectResponse:
    """
    Authorization endpoint (RFC 6749).

    GET /authorize?response_type=code&client_id=...&redirect_uri=...&state=...&scope=...
    """
    # Check if user is logged in
    if not request.session.get("logged_in"):
        # Store OAuth parameters and redirect to login
        request.session["oauth_return_to"] = str(request.url)
        return RedirectResponse(url="/login", status_code=303)

    # Extract OAuth parameters
    response_type = request.query_params.get("response_type")
    client_id = request.query_params.get("client_id")
    redirect_uri = request.query_params.get("redirect_uri")
    state = request.query_params.get("state")
    scope = request.query_params.get("scope", "full-access")

    # Validate parameters
    if response_type != "code":
        return HTMLResponse("<h1>Error</h1><p>Only 'code' response type is supported</p>", status_code=400)

    if not client_id or not redirect_uri:
        return HTMLResponse("<h1>Error</h1><p>Missing required parameters</p>", status_code=400)

    storage = get_storage()
    client = storage.get_client(client_id)

    if not client:
        return HTMLResponse("<h1>Error</h1><p>Unknown client</p>", status_code=400)

    if redirect_uri not in client.redirect_uris:
        return HTMLResponse("<h1>Error</h1><p>Invalid redirect_uri</p>", status_code=400)

    # For simplicity, auto-approve (no consent screen)
    # In production, show consent screen here
    user_id = request.session["user_id"]
    scopes = scope.split() if scope else ["full-access"]

    # Generate authorization code
    code = secrets.token_urlsafe(32)
    auth_code = AuthorizationCode(
        code=code,
        client_id=client_id,
        redirect_uri=redirect_uri,
        user_id=user_id,
        scopes=scopes,
        expires_at=time.time() + AUTH_CODE_EXPIRES,
    )
    storage.store_auth_code(auth_code)

    # Redirect back to client with code
    redirect_url = f"{redirect_uri}?code={code}"
    if state:
        redirect_url += f"&state={state}"

    logger.info(f"Issued authorization code for client {client_id}, user {user_id}")

    return RedirectResponse(url=redirect_url, status_code=303)


async def token_endpoint(request: Request) -> JSONResponse:
    """
    Token endpoint (RFC 6749).

    POST /token
    grant_type=authorization_code&code=...&redirect_uri=...&client_id=...&client_secret=...
    """
    try:
        form = await request.form()

        grant_type = form.get("grant_type")
        code = form.get("code")
        redirect_uri = form.get("redirect_uri")
        client_id = form.get("client_id")
        client_secret = form.get("client_secret")

        if grant_type != "authorization_code":
            return JSONResponse(
                {"error": "unsupported_grant_type", "error_description": "Only authorization_code is supported"},
                status_code=400
            )

        if not all([code, redirect_uri, client_id, client_secret]):
            return JSONResponse(
                {"error": "invalid_request", "error_description": "Missing required parameters"},
                status_code=400
            )

        storage = get_storage()

        # Verify client credentials
        if not storage.verify_client_secret(client_id, client_secret):
            return JSONResponse(
                {"error": "invalid_client", "error_description": "Invalid client credentials"},
                status_code=401
            )

        # Consume authorization code
        auth_code = storage.consume_auth_code(code)
        if not auth_code:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Invalid or expired authorization code"},
                status_code=400
            )

        # Verify code was issued to this client
        if auth_code.client_id != client_id:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Authorization code was issued to different client"},
                status_code=400
            )

        # Verify redirect URI matches
        if auth_code.redirect_uri != redirect_uri:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Redirect URI mismatch"},
                status_code=400
            )

        # Generate access token (JWT)
        now = time.time()
        expires_at = now + ACCESS_TOKEN_EXPIRES

        token_data = {
            "sub": auth_code.user_id,
            "client_id": client_id,
            "scope": " ".join(auth_code.scopes),
            "iat": int(now),
            "exp": int(expires_at),
        }

        access_token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)

        # Store token
        token_obj = AccessToken(
            token=access_token,
            client_id=client_id,
            user_id=auth_code.user_id,
            scopes=auth_code.scopes,
            expires_at=expires_at,
            issued_at=now,
        )
        storage.store_access_token(token_obj)

        logger.info(f"Issued access token for user {auth_code.user_id}, client {client_id}")

        return JSONResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_EXPIRES,
            "scope": " ".join(auth_code.scopes),
        })

    except Exception as e:
        logger.error(f"Token endpoint error: {e}")
        return JSONResponse(
            {"error": "server_error", "error_description": str(e)},
            status_code=500
        )


async def introspect_endpoint(request: Request) -> JSONResponse:
    """
    Token introspection endpoint (RFC 7662).

    POST /introspect
    token=...
    """
    try:
        form = await request.form()
        token = form.get("token")

        if not token:
            return JSONResponse({"active": False})

        # Verify JWT
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

            # Check expiration
            if payload.get("exp", 0) < time.time():
                return JSONResponse({"active": False})

            return JSONResponse({
                "active": True,
                "sub": payload.get("sub"),
                "client_id": payload.get("client_id"),
                "scope": payload.get("scope", ""),
                "exp": payload.get("exp"),
                "iat": payload.get("iat"),
            })

        except jwt.InvalidTokenError:
            return JSONResponse({"active": False})

    except Exception as e:
        logger.error(f"Introspection error: {e}")
        return JSONResponse({"active": False})


async def well_known_oauth_server(request: Request) -> JSONResponse:
    """
    OAuth 2.0 Authorization Server Metadata (RFC 8414).

    GET /.well-known/oauth-authorization-server
    """
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")

    metadata = {
        "issuer": server_url,
        "authorization_endpoint": f"{server_url}/authorize",
        "token_endpoint": f"{server_url}/token",
        "introspection_endpoint": f"{server_url}/introspect",
        "registration_endpoint": f"{server_url}/register",
        "scopes_supported": [
            "read:eod",
            "read:intraday",
            "read:live",
            "read:fundamentals",
            "read:news",
            "read:technicals",
            "read:options",
            "read:marketplace",
            "read:screener",
            "read:macro",
            "read:user",
            "full-access",
        ],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
        "code_challenge_methods_supported": ["S256"],
    }

    return JSONResponse(metadata)


async def home_page(request: Request) -> HTMLResponse:
    """Home page with OAuth information."""
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
    logged_in = request.session.get("logged_in", False)
    user_id = request.session.get("user_id", "")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>EODHD MCP Server - OAuth</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
            }}
            .status {{
                background-color: #e8f5e9;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
            }}
            .endpoint {{
                background-color: #f5f5f5;
                padding: 10px;
                margin: 5px 0;
                border-radius: 3px;
                font-family: monospace;
            }}
            a {{
                color: #1976d2;
            }}
        </style>
    </head>
    <body>
        <h1>EODHD MCP Server</h1>
        <div class="status">
            <strong>Status:</strong> OAuth 2.1 Enabled<br>
            {"<strong>Logged in as:</strong> " + user_id if logged_in else "<strong>Not logged in</strong>"}
        </div>

        <h2>OAuth Endpoints</h2>
        <div class="endpoint">Authorization Server Metadata: <a href="/.well-known/oauth-authorization-server">/.well-known/oauth-authorization-server</a></div>
        <div class="endpoint">Protected Resource Metadata: <a href="/.well-known/oauth-protected-resource">/.well-known/oauth-protected-resource</a></div>
        <div class="endpoint">Client Registration: POST /register</div>
        <div class="endpoint">User Login: <a href="/login">GET /login</a></div>
        <div class="endpoint">Authorization: GET /authorize</div>
        <div class="endpoint">Token Exchange: POST /token</div>
        <div class="endpoint">Token Introspection: POST /introspect</div>

        <h2>MCP Endpoints</h2>
        <div class="endpoint">Legacy MCP (token auth): /mcp</div>
        <div class="endpoint">OAuth MCP (Bearer token): /mcp-oauth</div>

        <h2>Quick Start</h2>
        <ol>
            <li>Register a client: <code>POST /register</code></li>
            <li>Login with your EODHD API key: <code>GET /login</code></li>
            <li>Get authorization code: <code>GET /authorize</code></li>
            <li>Exchange code for access token: <code>POST /token</code></li>
            <li>Use access token with MCP: <code>Authorization: Bearer &lt;token&gt;</code></li>
        </ol>

        <h2>How It Works</h2>
        <p>
            This server authenticates users using their EODHD API keys. When you log in,
            your API key is validated with EODHD and securely stored. When you make requests
            with an OAuth access token, the server uses your personal EODHD API key to
            access the data on your behalf.
        </p>
    </body>
    </html>
    """
    return HTMLResponse(html)


def create_auth_server_app() -> Starlette:
    """Create the OAuth Authorization Server ASGI app."""
    routes = [
        Route("/", home_page, methods=["GET"]),
        Route("/register", register_client_endpoint, methods=["POST"]),
        Route("/login", login_page, methods=["GET"]),
        Route("/login", login_submit, methods=["POST"]),
        Route("/authorize", authorize_endpoint, methods=["GET"]),
        Route("/token", token_endpoint, methods=["POST"]),
        Route("/introspect", introspect_endpoint, methods=["POST"]),
        Route("/.well-known/oauth-authorization-server", well_known_oauth_server, methods=["GET"]),
    ]

    middleware = [
        Middleware(SessionMiddleware, secret_key=SESSION_SECRET),
    ]

    app = Starlette(
        routes=routes,
        middleware=middleware,
    )

    return app