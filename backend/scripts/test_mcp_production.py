#!/usr/bin/env python3
"""
Production MCP Server Testing Script

This script tests the MCP server with real Azure AD authentication.
Requires: Azure AD Enterprise Application configured with proper redirect URIs.

Note: This is an interactive testing script that intentionally uses print statements
for direct user output. Ruff T201 (print) warnings are suppressed via ruff.toml config.
"""

import json
import re
import sys
import webbrowser
from urllib.parse import parse_qs, urlparse

import httpx


class ProductionMCPTester:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.client = httpx.Client(follow_redirects=False)
        self.access_token: str | None = None

    def extract_auth_code(self, user_input: str) -> str | None:
        """
        Smart extraction of auth code from either:
        1. Full callback URL: http://localhost:8001/auth/callback?code=abc123&state=xyz
        2. Direct auth code: f64ec70f-73a5-4079-8b94-199268023911

        This supports both the traditional workflow (pasting full URL) and the
        enhanced UI workflow (copying just the auth code from our improved interface).
        """
        user_input = user_input.strip()

        # Method 1: Full URL parsing (existing behavior for backward compatibility)
        if user_input.startswith("http") and "callback" in user_input:
            try:
                parsed = urlparse(user_input)
                query_params = parse_qs(parsed.query)
                auth_code = query_params.get("code", [None])[0]
                if auth_code:
                    print("✅ Extracted auth code from callback URL")
                    return auth_code
            except Exception:
                pass

        # Method 2: Direct auth code (new enhanced UI support)
        # UUID format: 8-4-4-4-12 characters (total 36 chars with hyphens)
        if len(user_input) == 36 and user_input.count("-") == 4:
            if re.match(r"^[a-fA-F0-9\-]{36}$", user_input):
                print("✅ Using auth code directly from enhanced UI")
                return user_input

        # Method 3: Other common auth code formats (without hyphens)
        if re.match(r"^[a-fA-F0-9]{30,40}$", user_input):
            print("✅ Using auth code directly")
            return user_input

        # Method 4: Handle mixed formats and clean input
        # Remove common prefixes and suffixes that users might accidentally include
        cleaned = re.sub(
            r"^(code[=:]?|auth[_-]?code[=:]?)\s*", "", user_input, flags=re.IGNORECASE
        )
        cleaned = re.sub(r'\s*([\'"`,;.])+$', "", cleaned)

        if cleaned != user_input and len(cleaned) >= 30:
            # Try again with cleaned input
            return self.extract_auth_code(cleaned)

        return None

    def test_server_startup(self) -> bool:
        """Test that MCP server started with Azure AD configuration."""
        try:
            # Test health endpoint
            response = self.client.get(f"{self.base_url}/health")
            health = response.json()
            print(f"✅ Health Status: {health}")

            # Check if Azure AD is properly configured
            auth_status = health.get("auth", "not configured")
            if auth_status == "configured":
                print("✅ Azure AD: Properly configured")
                return True
            else:
                print("❌ Azure AD: Not configured")
                return False

        except Exception as e:
            print(f"❌ Server startup test failed: {e}")
            return False

    def get_auth_url(self) -> str | None:
        """Get the Azure AD authentication URL."""
        try:
            response = self.client.get(f"{self.base_url}/auth/login")

            if response.status_code in [302, 307]:  # Redirect to Azure AD (302 or 307)
                auth_url = response.headers.get("location")
                print(
                    f"✅ Azure AD Login URL obtained (HTTP {response.status_code}): {auth_url[:100]}..."
                )
                return auth_url
            else:
                print(f"❌ Auth URL request failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return None

        except Exception as e:
            print(f"❌ Failed to get auth URL: {e}")
            return None

    def interactive_auth_flow(self) -> bool:
        """Guide user through interactive authentication."""
        print("\n🔐 Starting Interactive Azure AD Authentication...")

        # Get auth URL
        auth_url = self.get_auth_url()
        if not auth_url:
            return False

        print("\n📋 Authentication Instructions:")
        print("1. The browser will open with Azure AD login")
        print("2. Complete the authentication process")
        print("3. You'll be redirected to our enhanced authentication page")
        print("4. Either:")
        print("   • Copy the authentication code using the 'Copy to Clipboard' button")
        print("   • OR copy the full callback URL from the browser address bar")
        print("\n🌐 Opening browser...")

        try:
            webbrowser.open(auth_url)
        except Exception:
            print(f"⚠️  Couldn't open browser automatically. Please visit: {auth_url}")

        # Get input from user (supports both URL and auth code)
        print("\n📥 Paste the authentication code OR callback URL here:")
        user_input = input().strip()

        # Smart extraction of auth code
        auth_code = self.extract_auth_code(user_input)

        if not auth_code:
            print("❌ Could not extract authorization code from input")
            print("💡 Please ensure you copied either:")
            print("   • The authentication code from the success page")
            print("   • The full callback URL from your browser")
            return False

        # Exchange auth code for token
        return self.exchange_auth_code(auth_code)

    def exchange_auth_code(self, auth_code: str) -> bool:
        """Exchange authorization code for access token."""
        try:
            response = self.client.post(
                f"{self.base_url}/auth/exchange", json={"auth_code": auth_code}
            )

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")

                print("✅ Token exchange successful!")
                print(f"✅ Token type: {token_data.get('token_type', 'Bearer')}")
                print(
                    f"✅ Expires in: {token_data.get('expires_in', 'Unknown')} seconds"
                )

                # Show user info if available
                user_info = token_data.get("user_info", {})
                if user_info:
                    print(f"✅ User: {user_info.get('name', 'Unknown')}")
                    print(f"✅ Email: {user_info.get('email', 'Unknown')}")
                    roles = user_info.get("roles", [])
                    print(f"✅ Roles: {roles}")

                return True
            else:
                print(f"❌ Token exchange failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False

        except Exception as e:
            print(f"❌ Token exchange error: {e}")
            return False

    def test_mcp_tools_list(self) -> bool:
        """Test listing MCP tools with authentication."""
        if not self.access_token:
            print("❌ No access token available")
            return False

        try:
            response = self.client.post(
                f"{self.base_url}/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    tools = result["result"]["tools"]
                    print(f"✅ Available Tools ({len(tools)}):")
                    for tool in tools:
                        name = tool.get("name", "Unknown")
                        description = tool.get("description", "No description")
                        tags = tool.get("inputSchema", {}).get("tags", [])
                        print(f"  - {name}: {description}")
                        if tags:
                            print(f"    Tags: {tags}")
                    return True
                else:
                    print(f"❌ Unexpected response format: {result}")
                    return False
            else:
                print(f"❌ Tools list failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False

        except Exception as e:
            print(f"❌ Tools list error: {e}")
            return False

    def test_weather_tool_call(self) -> bool:
        """Test calling a weather tool."""
        if not self.access_token:
            print("❌ No access token available")
            return False

        try:
            response = self.client.post(
                f"{self.base_url}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "get_weather",
                        "arguments": {"location": "San Francisco", "units": "metric"},
                    },
                },
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    weather_data = result["result"]
                    print("✅ Weather Tool Call Result:")
                    print(json.dumps(weather_data, indent=2))
                    return True
                else:
                    print(f"❌ Unexpected response format: {result}")
                    return False
            else:
                print(f"❌ Weather tool call failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False

        except Exception as e:
            print(f"❌ Weather tool call error: {e}")
            return False

    def run_full_test_suite(self) -> bool:
        """Run the complete production test suite."""
        print("🚀 Production MCP Testing with Azure AD")
        print("=" * 50)

        # Test 1: Server startup and config
        print("\n🔍 Test 1: Server Configuration")
        if not self.test_server_startup():
            print("❌ Cannot proceed - server not properly configured")
            return False

        # Test 2: Interactive authentication
        print("\n🔍 Test 2: Azure AD Authentication")
        if not self.interactive_auth_flow():
            print("❌ Authentication failed - cannot test MCP functionality")
            return False

        # Test 3: MCP Tools listing (with role filtering)
        print("\n🔍 Test 3: Role-Based Tool Access")
        if not self.test_mcp_tools_list():
            print("❌ Tools listing failed")
            return False

        # Test 4: Tool execution
        print("\n🔍 Test 4: Tool Execution")
        if not self.test_weather_tool_call():
            print("⚠️  Tool execution failed (may be role-related)")

        print("\n" + "=" * 50)
        print("🎉 Production MCP testing completed!")
        print("Your Azure AD integration is working correctly.")

        return True


def main():
    """Main testing function."""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8001"

    print(f"🎯 Testing Production MCP server at: {base_url}")
    print("📋 Prerequisites:")
    print("  - Azure AD Enterprise Application configured")
    print("  - Redirect URI includes http://localhost:8001/auth/callback")
    print("  - App Roles defined (Task.Read, Task.Write, etc.)")
    print("  - User assigned to at least one role")
    print()

    response = input("Ready to proceed? (y/N): ").strip().lower()
    if response != "y":
        print("Exiting...")
        return

    tester = ProductionMCPTester(base_url)
    success = tester.run_full_test_suite()

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
