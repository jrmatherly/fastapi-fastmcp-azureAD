"""
Azure AD authentication integration for FastMCP server.

This module provides Azure AD OAuth 2.0 integration with JWT token verification
for fastMCP servers, following the validated approach from the analysis.
"""

import time
import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastmcp.server.auth.providers.jwt import JWTVerifier
from msal import ConfidentialClientApplication


class AuthContext:
    """
    Azure AD authentication context with MSAL integration and JWT verification.

    Provides the core authentication functionality including:
    - MSAL confidential client application setup
    - JWT token verification for fastMCP
    - Token data processing and management
    """

    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        """
        Initialize Azure AD authentication context.

        Args:
            tenant_id: Azure AD tenant identifier
            client_id: Application (client) ID from Azure App Registration
            client_secret: Client secret from Azure App Registration
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = [f"api://{client_id}/access_as_user"]
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"

        # MSAL Configuration for OAuth flow
        self.msal_app = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=self.authority,
        )

        # JWT Verification for fastMCP token validation
        self.bearer_auth = JWTVerifier(
            jwks_uri=f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
            issuer=f"https://sts.windows.net/{tenant_id}/",
            audience=f"api://{client_id}",
        )

    def get_token_data(self, result: dict[str, Any]) -> dict[str, Any]:
        """
        Extract and format token data from MSAL authentication result.

        Args:
            result: MSAL authentication result dictionary

        Returns:
            Formatted token data for storage
        """
        return {
            "access_token": result.get("access_token"),
            "refresh_token": result.get("refresh_token"),
            "expires_at": time.time() + result.get("expires_in", 3600),
            "id_token_claims": result.get("id_token_claims"),
        }

    async def refresh_token(self, refresh_token: str) -> dict[str, Any] | None:
        """
        Refresh an access token using the refresh token.

        Args:
            refresh_token: The refresh token to use

        Returns:
            New token data if successful, None otherwise
        """
        try:
            result = self.msal_app.acquire_token_by_refresh_token(
                refresh_token, scopes=self.scope
            )

            if "error" not in result:
                return self.get_token_data(result)
            return None
        except Exception:
            return None


def setup_auth_routes(
    app, auth_context: AuthContext, redis_token_store, redirect_uri: str
):
    """
    Setup authentication routes for the FastAPI application.

    Args:
        app: FastAPI application instance
        auth_context: AuthContext instance for Azure AD integration
        redis_token_store: RedisTokenStore instance for session management
        redirect_uri: OAuth callback redirect URI
    """
    flow_store = {}  # In-memory store for OAuth flows (consider Redis for production)

    @app.get("/auth/login")
    def login():
        """Initiate OAuth login flow with Azure AD."""
        flow = auth_context.msal_app.initiate_auth_code_flow(
            scopes=auth_context.scope, redirect_uri=redirect_uri
        )
        flow_store[flow["state"]] = flow
        return RedirectResponse(flow["auth_uri"])

    @app.get("/auth/callback")
    def callback(request: Request):
        """Handle OAuth callback from Azure AD."""
        state = request.query_params.get("state")
        flow = flow_store.get(state)
        if not flow:
            return HTMLResponse("Invalid state parameter", status_code=400)

        result = auth_context.msal_app.acquire_token_by_auth_code_flow(
            flow, dict(request.query_params)
        )

        if "error" in result:
            return HTMLResponse(
                f"Authentication failed: {result.get('error_description', 'Unknown error')}",
                status_code=400,
            )

        # Store token data in Redis with user OID as key
        oid = result["id_token_claims"]["oid"]
        token_data = {
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token"),
            "expires_at": time.time() + result.get("expires_in", 3600),
            "id_token_claims": result.get("id_token_claims"),
        }
        redis_token_store.save_token(oid, token_data)

        # Generate auth code for client exchange
        auth_code = str(uuid.uuid4())
        redis_token_store.set_auth_code(auth_code, oid, 120)  # 2 minutes TTL

        # Clean up the flow from store
        flow_store.pop(state, None)

        return HTMLResponse(
            f"Login successful. Use this code to exchange for token: <pre>{auth_code}</pre>"
        )

    @app.post("/auth/exchange")
    def exchange_auth_code(payload: dict[str, Any]):
        """Exchange auth code for access token."""
        auth_code = payload.get("auth_code")
        if not auth_code:
            return {"error": "auth_code is required"}

        user_oid = redis_token_store.get_auth_code(auth_code)
        if not user_oid:
            return {"error": "Invalid or expired auth_code"}

        token_data = redis_token_store.load_token(user_oid)
        redis_token_store.delete_auth_code(auth_code)  # Single-use auth code
        return token_data

    @app.post("/auth/refresh")
    async def refresh_token_endpoint(payload: dict[str, Any]):
        """Refresh access token using refresh token."""
        refresh_token = payload.get("refresh_token")
        if not refresh_token:
            return {"error": "refresh_token is required"}

        new_token_data = await auth_context.refresh_token(refresh_token)
        if new_token_data:
            # Update stored token data
            oid = new_token_data["id_token_claims"]["oid"]
            redis_token_store.save_token(oid, new_token_data)
            return new_token_data
        else:
            return {"error": "Failed to refresh token"}

    @app.get("/auth/user")
    def get_user_info(_request: Request):
        """Get current user information from token claims."""
        # This would be implemented with proper JWT validation
        # For now, returns basic structure for API compatibility
        return {"user": "authenticated", "roles": []}
