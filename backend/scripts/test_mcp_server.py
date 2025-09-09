#!/usr/bin/env python3
"""
MCP Server Testing Script

This script helps test the MCP server functionality without requiring
full Azure AD setup during development.

Note: This is an interactive testing script that intentionally uses print statements
for direct user output. Ruff T201 (print) warnings are suppressed via ruff.toml config.
"""

import sys

import httpx


class MCPTester:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.client = httpx.Client()

    def test_server_health(self) -> bool:
        """Test if the MCP server is running and healthy."""
        try:
            response = self.client.get(f"{self.base_url}/")
            print(f"✅ Server Info: {response.json()}")
            return True
        except Exception as e:
            print(f"❌ Server not accessible: {e}")
            return False

    def test_health_endpoint(self) -> bool:
        """Test the health check endpoint."""
        try:
            response = self.client.get(f"{self.base_url}/health")
            health_data = response.json()
            print(f"✅ Health Check: {health_data}")

            # Check Redis connection
            if health_data.get("redis") == "connected":
                print("✅ Redis connection: OK")
            else:
                print("⚠️  Redis connection: Not connected")

            return True
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False

    def test_openapi_schema(self) -> bool:
        """Test OpenAPI schema generation."""
        try:
            response = self.client.get(f"{self.base_url}/openapi.json")
            schema = response.json()
            print(f"✅ OpenAPI Schema: {len(schema.get('paths', {}))} endpoints found")

            # List available endpoints
            paths = schema.get("paths", {})
            for path, methods in paths.items():
                method_list = list(methods.keys())
                print(f"  - {path}: {method_list}")

            return True
        except Exception as e:
            print(f"❌ OpenAPI schema test failed: {e}")
            return False

    def test_auth_endpoints_exist(self) -> bool:
        """Test that auth endpoints are configured (but don't call them)."""
        try:
            response = self.client.get(f"{self.base_url}/openapi.json")
            schema = response.json()
            paths = schema.get("paths", {})

            auth_endpoints = ["/auth/login", "/auth/callback", "/auth/exchange"]
            found_endpoints = []

            for endpoint in auth_endpoints:
                if endpoint in paths:
                    found_endpoints.append(endpoint)
                    print(f"✅ Auth endpoint configured: {endpoint}")
                else:
                    print(f"❌ Auth endpoint missing: {endpoint}")

            return len(found_endpoints) == len(auth_endpoints)
        except Exception as e:
            print(f"❌ Auth endpoints test failed: {e}")
            return False

    def test_mcp_endpoint_structure(self) -> bool:
        """Test MCP endpoint accessibility (without auth)."""
        try:
            # This should return 401/403 or similar auth error, not 404
            response = self.client.get(f"{self.base_url}/mcp")

            if response.status_code == 404:
                print("❌ MCP endpoint not found")
                return False
            elif response.status_code in [401, 403]:
                print("✅ MCP endpoint exists but requires authentication (expected)")
                return True
            else:
                print(f"✅ MCP endpoint accessible with status: {response.status_code}")
                return True

        except Exception as e:
            print(f"❌ MCP endpoint test failed: {e}")
            return False

    def run_all_tests(self) -> bool:
        """Run all available tests."""
        print("🧪 Starting MCP Server Testing...")
        print("=" * 50)

        tests = [
            ("Server Health", self.test_server_health),
            ("Health Endpoint", self.test_health_endpoint),
            ("OpenAPI Schema", self.test_openapi_schema),
            ("Auth Endpoints", self.test_auth_endpoints_exist),
            ("MCP Endpoint Structure", self.test_mcp_endpoint_structure),
        ]

        results = []
        for test_name, test_func in tests:
            print(f"\n🔍 Testing: {test_name}")
            print("-" * 30)
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"❌ {test_name} failed with exception: {e}")
                results.append((test_name, False))

        print("\n" + "=" * 50)
        print("📊 Test Results Summary:")

        passed = 0
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {status}: {test_name}")
            if result:
                passed += 1

        print(f"\nOverall: {passed}/{len(results)} tests passed")

        if passed == len(results):
            print(
                "\n🎉 All tests passed! MCP server is ready for Azure AD integration."
            )
        else:
            print("\n⚠️  Some tests failed. Check server configuration and try again.")

        return passed == len(results)


def main():
    """Main testing function."""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8001"

    print(f"🎯 Testing MCP server at: {base_url}")

    tester = MCPTester(base_url)
    success = tester.run_all_tests()

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
