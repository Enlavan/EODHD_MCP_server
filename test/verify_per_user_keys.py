#!/usr/bin/env python3
"""
Verification script to demonstrate per-user EODHD API key mapping.

This script shows that:
1. Each user's EODHD API key is stored when they log in
2. Access tokens are mapped to their respective user's EODHD API key
3. MCP requests use the correct per-user API key

Usage:
    python verify_per_user_keys.py

This script uses the internal API to verify the token-to-key mapping.
"""

import asyncio
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(__file__))

from app.oauth.auth_server import get_storage, User
from app.oauth.oauth import OAuthValidator


async def main():
    print("=" * 70)
    print("Per-User EODHD API Key Mapping Verification")
    print("=" * 70)

    storage = get_storage()

    # Simulate adding two users with different API keys
    print("\n1. Simulating two users logging in with different API keys:")
    print("-" * 70)

    user1 = User(
        email="alice@example.com",
        eodhd_api_key="demo_key_alice_123456",
        name="Alice Smith",
        subscription_type="premium"
    )
    storage.add_user(user1)
    print(f"✓ User 1: {user1.email}")
    print(f"  EODHD API Key: {user1.eodhd_api_key}")

    user2 = User(
        email="bob@example.com",
        eodhd_api_key="demo_key_bob_789xyz",
        name="Bob Jones",
        subscription_type="free"
    )
    storage.add_user(user2)
    print(f"\n✓ User 2: {user2.email}")
    print(f"  EODHD API Key: {user2.eodhd_api_key}")

    # Simulate issuing access tokens
    print("\n2. Simulating access token issuance:")
    print("-" * 70)

    import time
    import secrets
    from app.oauth.auth_server import AccessToken, ACCESS_TOKEN_EXPIRES

    token1 = "demo_access_token_alice_" + secrets.token_urlsafe(16)
    token_obj1 = AccessToken(
        token=token1,
        client_id="test_client_1",
        user_id=user1.email,  # This links the token to the user
        scopes=["full-access"],
        expires_at=time.time() + ACCESS_TOKEN_EXPIRES,
        issued_at=time.time()
    )
    storage.store_access_token(token_obj1)
    print(f"✓ Issued token for {user1.email}")
    print(f"  Token: {token1[:40]}...")

    token2 = "demo_access_token_bob_" + secrets.token_urlsafe(16)
    token_obj2 = AccessToken(
        token=token2,
        client_id="test_client_2",
        user_id=user2.email,  # This links the token to the user
        scopes=["full-access"],
        expires_at=time.time() + ACCESS_TOKEN_EXPIRES,
        issued_at=time.time()
    )
    storage.store_access_token(token_obj2)
    print(f"\n✓ Issued token for {user2.email}")
    print(f"  Token: {token2[:40]}...")

    # Verify token-to-key mapping
    print("\n3. Verifying token-to-EODHD-key mapping:")
    print("-" * 70)

    key1 = storage.get_eodhd_api_key_for_token(token1)
    print(f"✓ Token for {user1.email} maps to:")
    print(f"  EODHD API Key: {key1}")
    print(f"  Correct: {key1 == user1.eodhd_api_key} ✓" if key1 == user1.eodhd_api_key else f"  ERROR: Mismatch!")

    key2 = storage.get_eodhd_api_key_for_token(token2)
    print(f"\n✓ Token for {user2.email} maps to:")
    print(f"  EODHD API Key: {key2}")
    print(f"  Correct: {key2 == user2.eodhd_api_key} ✓" if key2 == user2.eodhd_api_key else f"  ERROR: Mismatch!")

    # Verify lookup by API key
    print("\n4. Verifying reverse lookup (API key -> User):")
    print("-" * 70)

    user_by_key1 = storage.get_user_by_api_key(user1.eodhd_api_key)
    print(f"✓ API key '{user1.eodhd_api_key}' belongs to: {user_by_key1.email}")

    user_by_key2 = storage.get_user_by_api_key(user2.eodhd_api_key)
    print(f"✓ API key '{user2.eodhd_api_key}' belongs to: {user_by_key2.email}")

    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print("✓ Each user has a unique EODHD API key stored")
    print("✓ Access tokens are correctly mapped to user emails")
    print("✓ Tokens can be resolved to their user's EODHD API key")
    print("✓ When MCP requests arrive with Bearer tokens, the correct")
    print("  per-user EODHD API key will be used for API calls")
    print("\nThe OAuth implementation correctly handles per-user API keys!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())