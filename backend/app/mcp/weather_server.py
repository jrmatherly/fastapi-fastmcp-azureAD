"""
Example MCP server with weather tools for Azure AD integration testing.

This demonstrates the complete integration of fastMCP with Azure AD authentication,
role-based access control, and tool filtering.
"""

import os
from typing import Any

from fastapi import FastAPI
from fastmcp import FastMCP

from app.core.authorization_middleware import AuthorizationMiddleware
from app.core.azure_auth import AuthContext, setup_auth_routes
from app.core.redis_token_store import RedisTokenStore


class WeatherMCPServer:
    """
    Example MCP server with weather-related tools.

    Demonstrates role-based tool access with Azure AD integration:
    - Task.Read: get_weather (read-only operations)
    - Task.Write: set_weather_alert (write operations)
    - Task.All: all tools
    - MCPServer.Admin: admin operations
    """

    def __init__(self):
        self.app = FastAPI(title="Weather MCP Server", version="1.0.0")
        self.setup_mcp_server()
        self.setup_azure_auth()

    def setup_azure_auth(self):
        """Setup Azure AD authentication and Redis token store."""
        # Get configuration from environment
        tenant_id = os.getenv("AZURE_TENANT_ID")
        client_id = os.getenv("AZURE_CLIENT_ID")
        client_secret = os.getenv("AZURE_CLIENT_SECRET")

        if not all([tenant_id, client_id, client_secret]):
            raise ValueError("Missing required Azure AD configuration")

        # Setup Redis token store
        self.redis_store = RedisTokenStore(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD"),
            ssl=os.getenv("REDIS_SSL", "false").lower() == "true",
        )

        # Setup Azure AD context
        self.auth_context = AuthContext(tenant_id, client_id, client_secret)

        # Setup authentication routes
        redirect_uri = os.getenv(
            "AZURE_REDIRECT_URI", "http://localhost:8000/auth/callback"
        )
        setup_auth_routes(self.app, self.auth_context, self.redis_store, redirect_uri)

    def setup_mcp_server(self):
        """Setup fastMCP server with weather tools."""
        # Initialize fastMCP server with JWT authentication
        self.mcp_server = FastMCP(
            auth=self.auth_context.bearer_auth
            if hasattr(self, "auth_context")
            else None
        )

        # Add authorization middleware for role-based access control
        if hasattr(self, "auth_context") and hasattr(self, "redis_store"):
            auth_middleware = AuthorizationMiddleware(
                self.auth_context, self.redis_store
            )
            self.mcp_server.add_middleware(auth_middleware)

        # Register weather tools
        self.register_weather_tools()

        # Mount MCP server into FastAPI app
        self.app.mount("/mcp", self.mcp_server)

    def register_weather_tools(self):
        """Register weather-related MCP tools with appropriate tags."""

        @self.mcp_server.tool(
            name="get_weather",
            description="Get current weather for a location",
            tags=["read", "weather", "public"],
        )
        def get_weather(location: str) -> dict[str, Any]:
            """
            Get current weather information for a specified location.

            This tool requires Task.Read or higher permissions.
            """
            # Mock weather data - in real implementation, call weather API
            return {
                "location": location,
                "temperature": "22°C",
                "condition": "Sunny",
                "humidity": "45%",
                "wind_speed": "10 km/h",
                "timestamp": "2024-01-09T12:00:00Z",
            }

        @self.mcp_server.tool(
            name="get_weather_forecast",
            description="Get 5-day weather forecast for a location",
            tags=["read", "weather", "forecast"],
        )
        def get_weather_forecast(location: str, days: int = 5) -> list[dict[str, Any]]:
            """
            Get weather forecast for a specified location.

            This tool requires Task.Read or higher permissions.
            """
            # Mock forecast data - in real implementation, call weather API
            forecast = []
            for i in range(min(days, 5)):
                forecast.append(
                    {
                        "day": f"Day {i + 1}",
                        "date": f"2024-01-{10 + i:02d}",
                        "location": location,
                        "temperature_high": f"{20 + i}°C",
                        "temperature_low": f"{10 + i}°C",
                        "condition": "Partly cloudy" if i % 2 else "Sunny",
                        "precipitation_chance": f"{i * 10}%",
                    }
                )
            return forecast

        @self.mcp_server.tool(
            name="set_weather_alert",
            description="Set weather alert for a location",
            tags=["write", "weather", "alert"],
        )
        def set_weather_alert(
            location: str, condition: str, threshold: str, notification_email: str
        ) -> dict[str, Any]:
            """
            Create a weather alert for specified conditions.

            This tool requires Task.Write or higher permissions.
            """
            alert_id = f"alert_{hash(location + condition)}"

            return {
                "alert_id": alert_id,
                "location": location,
                "condition": condition,
                "threshold": threshold,
                "notification_email": notification_email,
                "status": "active",
                "created_at": "2024-01-09T12:00:00Z",
            }

        @self.mcp_server.tool(
            name="delete_weather_alert",
            description="Delete a weather alert",
            tags=["delete", "weather", "alert"],
        )
        def delete_weather_alert(alert_id: str) -> dict[str, Any]:
            """
            Delete a weather alert by ID.

            This tool requires Task.Delete or higher permissions.
            """
            return {
                "alert_id": alert_id,
                "status": "deleted",
                "deleted_at": "2024-01-09T12:00:00Z",
            }

        @self.mcp_server.tool(
            name="admin_weather_stats",
            description="Get administrative weather statistics",
            tags=["admin", "weather", "stats"],
        )
        def admin_weather_stats() -> dict[str, Any]:
            """
            Get administrative weather statistics.

            This tool requires MCPServer.Admin permissions.
            """
            return {
                "total_requests": 1234,
                "active_alerts": 56,
                "locations_monitored": 78,
                "uptime": "99.9%",
                "last_updated": "2024-01-09T12:00:00Z",
            }

        @self.mcp_server.tool(
            name="health_check",
            description="Check server health status",
            tags=["read", "health", "public"],
        )
        def health_check() -> dict[str, Any]:
            """
            Check the health status of the weather MCP server.

            Available to all authenticated users.
            """
            # Check Redis connection
            redis_healthy = (
                self.redis_store.health_check() if self.redis_store else False
            )

            return {
                "status": "healthy",
                "timestamp": "2024-01-09T12:00:00Z",
                "redis_connected": redis_healthy,
                "auth_configured": hasattr(self, "auth_context"),
                "tools_registered": len(self.mcp_server._tool_manager._tools),
                "version": "1.0.0",
            }

    def get_app(self) -> FastAPI:
        """Get the FastAPI application instance."""
        return self.app


# Create server instance
weather_server = WeatherMCPServer()
app = weather_server.get_app()


# Additional FastAPI routes for server management
@app.get("/")
def root():
    """Root endpoint with server information."""
    return {
        "message": "Weather MCP Server with Azure AD Authentication",
        "version": "1.0.0",
        "mcp_endpoint": "/mcp",
        "auth_endpoints": {
            "login": "/auth/login",
            "callback": "/auth/callback",
            "exchange": "/auth/exchange",
            "refresh": "/auth/refresh",
            "user": "/auth/user",
        },
        "documentation": "/docs",
    }


@app.get("/health")
def health():
    """Health check endpoint."""
    try:
        redis_healthy = weather_server.redis_store.health_check()
        return {
            "status": "healthy",
            "redis": "connected" if redis_healthy else "disconnected",
            "auth": "configured"
            if hasattr(weather_server, "auth_context")
            else "not configured",
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
