"""
FastAPI main application with embedded MCP server.

This demonstrates how to embed MCP functionality directly into the main FastAPI app.
"""

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings
from app.mcp.weather_server import WeatherMCPServer


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

# Create main FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include main API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# === MCP INTEGRATION ===
# Create and embed MCP server
try:
    weather_mcp = WeatherMCPServer()
    mcp_app = weather_mcp.get_app()

    # Mount MCP routes under /mcp prefix
    app.mount("/mcp-server", mcp_app)

    # Add MCP health check to main app
    @app.get("/api/v1/mcp/health")
    def mcp_health():
        """Check MCP server health from main app."""
        try:
            redis_healthy = weather_mcp.redis_store.health_check()
            return {
                "status": "healthy",
                "mcp_server": "embedded",
                "redis": "connected" if redis_healthy else "disconnected",
                "auth": "configured"
                if hasattr(weather_mcp, "auth_context")
                else "not configured",
                "endpoints": {
                    "mcp_root": "/mcp-server/",
                    "mcp_protocol": "/mcp-server/mcp",
                    "auth_login": "/mcp-server/auth/login",
                },
            }
        except Exception as e:
            return {"status": "unhealthy", "mcp_error": str(e)}

except Exception as e:
    import logging

    logger = logging.getLogger(__name__)
    logger.warning("MCP server failed to initialize: %s", e)
    logger.info("Main app will continue without MCP functionality")

    @app.get("/api/v1/mcp/health")
    def mcp_health_disabled():
        return {"status": "disabled", "error": "MCP server initialization failed"}
