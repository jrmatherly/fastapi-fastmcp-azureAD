"""
FastAPI main application with MCP process manager.

This demonstrates how to use the MCP manager to automatically start/stop
MCP servers as background processes.
"""

from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings
from app.mcp.manager import mcp_manager, shutdown_mcp_servers, startup_mcp_servers


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    # Startup
    await startup_mcp_servers()
    yield
    # Shutdown
    await shutdown_mcp_servers()


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
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

app.include_router(api_router, prefix=settings.API_V1_STR)


# === MCP MANAGEMENT ENDPOINTS ===
@app.get("/api/v1/mcp/status")
def get_mcp_status():
    """Get status of all MCP servers."""
    return mcp_manager.get_server_status()


@app.post("/api/v1/mcp/start/{server_name}")
async def start_mcp_server(server_name: str):
    """Start a specific MCP server."""
    success = await mcp_manager.start_server(server_name)
    return {"server": server_name, "started": success}


@app.post("/api/v1/mcp/stop/{server_name}")
async def stop_mcp_server(server_name: str):
    """Stop a specific MCP server."""
    success = await mcp_manager.stop_server(server_name)
    return {"server": server_name, "stopped": success}


@app.get("/api/v1/mcp/servers")
def list_mcp_servers():
    """List all configured MCP servers."""
    return {
        "servers": mcp_manager.server_configs,
        "status": mcp_manager.get_server_status(),
    }
