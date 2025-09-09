from fastapi import FastAPI
from fastmcp import FastMCP

from shared.auth_context import (
    AuthContext,  # helper class to configure Azure App Registration, MSAL, and JWT verifier
    setup_auth_routes,  # function to setup authentication routes
)
from shared.middleware.authorization_middleware import (
    AuthorizationMiddleware,  # custom FastMCP middleware for enforcing RBAC
)
from shared.redis_token_store import (
    RedisTokenStore,  # handles secure token and auth code storage via Redis
)

# --- Setup Auth + Token Store ---
auth_context = AuthContext(
    tenant_id="<TENANT_ID>", client_id="<CLIENT_ID>", client_secret="<CLIENT_SECRET>"
)

redis_token_store = RedisTokenStore(
    host="<REDIS_HOST>", port=6380, password="<REDIS_PASSWORD>", ssl=True
)

# --- Configure MCP ---
mcp = FastMCP("Test Weather MCP Server", auth=auth_context.bearer_auth)
mcp.add_middleware(AuthorizationMiddleware(auth_context, redis_token_store))


@mcp.tool(tags={"read"})
def get_weather(city: str) -> str:
    ...


@mcp.tool(tags={"write"})
def get_alerts(state: str) -> str:
    ...


# --- Mount MCP Server ---
app = FastAPI()
app.mount("/weather-mcp", mcp.http_app())

# 🔐 Setup authentication routes
REDIRECT_URI = "http://localhost:8000/auth/callback"
setup_auth_routes(app, auth_context, redis_token_store, REDIRECT_URI)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
