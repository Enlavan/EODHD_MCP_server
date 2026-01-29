#!/usr/bin/env python3
"""
OAuth 2.1 Flow Test Script for EODHD MCP Server

This script tests the complete OAuth authorization flow:
1. Client registration
2. User login with EODHD API key
3. Authorization code grant
4. Token exchange
5. API access with Bearer token

Usage:
    python test_oauth.py --api-key YOUR_EODHD_API_KEY [--host HOST] [--port PORT]

Requirements:
    - Server must be running with --oauth flag
    - httpx library installed (pip install httpx)
    - Valid EODHD API key
"""

import argparse
import asyncio
import json
import sys
from urllib.parse import urlencode, parse_qs, urlparse

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install it with: pip install httpx")
    sys.exit(1)


class OAuthTester:
    """Test OAuth 2.1 flow against EODHD MCP Server."""

    def __init__(self, base_url: str, eodhd_api_key: str = None):
        self.base_url = base_url.rstrip("/")
        self.eodhd_api_key = eodhd_api_key
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=False)
        self.client_id = None
        self.client_secret = None
        self.access_token = None

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def test_discovery(self) -> bool:
        """Test OAuth discovery endpoints."""
        print("\n" + "=" * 70)
        print("TEST 1: OAuth Discovery Endpoints")
        print("=" * 70)

        try:
            # Test authorization server metadata
            print(f"\n→ GET {self.base_url}/.well-known/oauth-authorization-server")
            response = await self.client.get(
                f"{self.base_url}/.well-known/oauth-authorization-server"
            )

            if response.status_code == 200:
                metadata = response.json()
                print("✓ Authorization Server Metadata:")
                print(f"  - Issuer: {metadata.get('issuer')}")
                print(f"  - Authorization Endpoint: {metadata.get('authorization_endpoint')}")
                print(f"  - Token Endpoint: {metadata.get('token_endpoint')}")
                print(f"  - Scopes: {', '.join(metadata.get('scopes_supported', []))}")
            else:
                print(f"✗ Failed with status {response.status_code}")
                return False

            # Test protected resource metadata
            print(f"\n→ GET {self.base_url}/.well-known/oauth-protected-resource")
            response = await self.client.get(
                f"{self.base_url}/.well-known/oauth-protected-resource"
            )

            if response.status_code == 200:
                metadata = response.json()
                print("✓ Protected Resource Metadata:")
                print(f"  - Resource: {metadata.get('resource')}")
                print(f"  - Authorization Servers: {metadata.get('authorization_servers')}")
            else:
                print(f"✗ Failed with status {response.status_code}")
                return False

            return True

        except Exception as e:
            print(f"✗ Error: {e}")
            return False

    async def test_client_registration(self) -> bool:
        """Test client registration."""
        print("\n" + "=" * 70)
        print("TEST 2: Client Registration")
        print("=" * 70)

        try:
            payload = {
                "client_name": "OAuth Test Client",
                "redirect_uris": ["http://localhost:3000/callback"]
            }

            print(f"\n→ POST {self.base_url}/register")
            print(f"  Payload: {json.dumps(payload, indent=2)}")

            response = await self.client.post(
                f"{self.base_url}/register",
                json=payload
            )

            if response.status_code == 200:
                data = response.json()
                self.client_id = data["client_id"]
                self.client_secret = data["client_secret"]

                print("✓ Client registered successfully:")
                print(f"  - Client ID: {self.client_id}")
                print(f"  - Client Secret: {self.client_secret[:20]}...")
                print(f"  - Redirect URIs: {data['redirect_uris']}")
                return True
            else:
                print(f"✗ Failed with status {response.status_code}")
                print(f"  Response: {response.text}")
                return False

        except Exception as e:
            print(f"✗ Error: {e}")
            return False

    async def test_authorization_flow(self) -> bool:
        """Test authorization code flow (simplified)."""
        print("\n" + "=" * 70)
        print("TEST 3: Authorization Code Flow")
        print("=" * 70)

        if not self.client_id:
            print("✗ Client ID not available. Run client registration first.")
            return False

        if not self.eodhd_api_key:
            print("✗ EODHD API key not provided. Use --api-key parameter.")
            return False

        try:
            # Step 1: User login with EODHD API key
            print("\n→ Step 1: User Login with EODHD API Key")
            print(f"  POST {self.base_url}/login")
            print(f"  Using API key: {self.eodhd_api_key[:10]}...")

            login_response = await self.client.post(
                f"{self.base_url}/login",
                data={
                    "api_key": self.eodhd_api_key
                }
            )

            if login_response.status_code in (303, 302, 200):
                print("✓ Login successful (API key validated with EODHD)")
                # Save cookies for subsequent requests
                cookies = login_response.cookies
            else:
                print(f"✗ Login failed with status {login_response.status_code}")
                print(f"  Response: {login_response.text[:200]}")
                return False

            # Step 2: Authorization request
            print("\n→ Step 2: Authorization Request")
            params = {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": "http://localhost:3000/callback",
                "state": "test_state_123",
                "scope": "full-access"
            }

            auth_url = f"{self.base_url}/authorize?{urlencode(params)}"
            print(f"  GET {auth_url}")

            auth_response = await self.client.get(auth_url, cookies=cookies)

            # Should redirect with code
            if auth_response.status_code in (303, 302):
                location = auth_response.headers.get("location", "")
                print(f"✓ Authorization granted, redirecting to: {location}")

                # Extract code from redirect
                parsed = urlparse(location)
                query_params = parse_qs(parsed.query)
                auth_code = query_params.get("code", [None])[0]

                if auth_code:
                    print(f"  - Authorization Code: {auth_code[:20]}...")
                    return await self.test_token_exchange(auth_code)
                else:
                    print("✗ No authorization code in redirect")
                    return False
            else:
                print(f"✗ Authorization failed with status {auth_response.status_code}")
                return False

        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def test_token_exchange(self, auth_code: str) -> bool:
        """Test token exchange."""
        print("\n→ Step 3: Token Exchange")

        try:
            payload = {
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": "http://localhost:3000/callback",
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }

            print(f"  POST {self.base_url}/token")

            response = await self.client.post(
                f"{self.base_url}/token",
                data=payload
            )

            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]

                print("✓ Access token received:")
                print(f"  - Token Type: {data['token_type']}")
                print(f"  - Expires In: {data['expires_in']} seconds")
                print(f"  - Scope: {data.get('scope', 'N/A')}")
                print(f"  - Access Token: {self.access_token[:30]}...")
                return True
            else:
                print(f"✗ Token exchange failed with status {response.status_code}")
                print(f"  Response: {response.text}")
                return False

        except Exception as e:
            print(f"✗ Error: {e}")
            return False

    async def test_token_introspection(self) -> bool:
        """Test token introspection."""
        print("\n" + "=" * 70)
        print("TEST 4: Token Introspection")
        print("=" * 70)

        if not self.access_token:
            print("✗ Access token not available.")
            return False

        try:
            print(f"\n→ POST {self.base_url}/introspect")

            response = await self.client.post(
                f"{self.base_url}/introspect",
                data={"token": self.access_token}
            )

            if response.status_code == 200:
                data = response.json()
                print("✓ Token introspection result:")
                print(f"  - Active: {data.get('active')}")
                print(f"  - Subject: {data.get('sub')}")
                print(f"  - Client ID: {data.get('client_id')}")
                print(f"  - Scope: {data.get('scope')}")
                return data.get("active", False)
            else:
                print(f"✗ Introspection failed with status {response.status_code}")
                return False

        except Exception as e:
            print(f"✗ Error: {e}")
            return False

    async def test_mcp_access(self) -> bool:
        """Test MCP endpoint access with Bearer token."""
        print("\n" + "=" * 70)
        print("TEST 5: MCP Access with Bearer Token")
        print("=" * 70)

        if not self.access_token:
            print("✗ Access token not available.")
            return False

        try:
            # Test OAuth-protected endpoint
            print(f"\n→ Testing /mcp-oauth (OAuth-protected)")
            print(f"  GET {self.base_url}/mcp-oauth")
            print(f"  Authorization: Bearer {self.access_token[:30]}...")

            response = await self.client.get(
                f"{self.base_url}/mcp-oauth",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )

            if response.status_code in (200, 404):  # 404 is OK for GET on MCP endpoint
                print("✓ OAuth endpoint accessible with Bearer token")
            else:
                print(f"✗ Failed with status {response.status_code}")
                print(f"  Response: {response.text}")
                return False

            # Test legacy endpoint (should work without token if env var is set)
            print(f"\n→ Testing /mcp (legacy endpoint)")
            print(f"  GET {self.base_url}/mcp")

            response = await self.client.get(f"{self.base_url}/mcp")

            if response.status_code in (200, 404):
                print("✓ Legacy endpoint accessible")
            else:
                print(f"  Note: Legacy endpoint returned {response.status_code}")

            return True

        except Exception as e:
            print(f"✗ Error: {e}")
            return False

    async def run_all_tests(self) -> bool:
        """Run all tests."""
        print("\n" + "=" * 70)
        print("EODHD MCP Server - OAuth 2.1 Test Suite")
        print("=" * 70)
        print(f"Server: {self.base_url}")

        tests = [
            ("Discovery Endpoints", self.test_discovery),
            ("Client Registration", self.test_client_registration),
            ("Authorization Flow", self.test_authorization_flow),
            ("Token Introspection", self.test_token_introspection),
            ("MCP Access", self.test_mcp_access),
        ]

        results = []
        for name, test_func in tests:
            try:
                result = await test_func()
                results.append((name, result))
            except Exception as e:
                print(f"\n✗ Test '{name}' failed with exception: {e}")
                results.append((name, False))

        # Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)

        passed = sum(1 for _, result in results if result)
        total = len(results)

        for name, result in results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {status}  {name}")

        print("\n" + "=" * 70)
        print(f"Results: {passed}/{total} tests passed")
        print("=" * 70 + "\n")

        return passed == total


async def main():
    parser = argparse.ArgumentParser(
        description="Test OAuth 2.1 flow for EODHD MCP Server",
        epilog="Example: python test_oauth.py --api-key demo123456.abcdef"
    )
    parser.add_argument("--api-key", required=True, help="Your EODHD API key")
    parser.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"

    tester = OAuthTester(base_url, eodhd_api_key=args.api_key)
    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
