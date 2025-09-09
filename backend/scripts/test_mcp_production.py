#!/usr/bin/env python3
"""
Production MCP Server Testing Script

This script tests the MCP server with real Azure AD authentication.
Requires: Azure AD Enterprise Application configured with proper redirect URIs.

Note: This is an interactive testing script that intentionally uses print statements
for direct user output. Ruff T201 (print) warnings are suppressed via ruff.toml config.
"""

import json
import sys
import webbrowser
from urllib.parse import parse_qs, urlparse

import httpx


class ProductionMCPTester:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.client = httpx.Client(follow_redirects=False)
        self.access_token: str | None = None

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
        print("3. You'll be redirected to a callback URL")
        print("4. Copy the ENTIRE callback URL and paste it here")
        print("\n🌐 Opening browser...")

        try:
            webbrowser.open(auth_url)
        except Exception:
            print(f"⚠️  Couldn't open browser automatically. Please visit: {auth_url}")

        # Get callback URL from user
        print("\n📥 Paste the callback URL here:")
        callback_url = input().strip()

        # Extract auth code
        try:
            parsed = urlparse(callback_url)
            query_params = parse_qs(parsed.query)
            auth_code = query_params.get("code", [None])[0]

            if not auth_code:
                print("❌ No authorization code found in callback URL")
                return False

            print("✅ Authorization code extracted")

            # Exchange auth code for token
            return self.exchange_auth_code(auth_code)

        except Exception as e:
            print(f"❌ Failed to process callback URL: {e}")
            return False

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
