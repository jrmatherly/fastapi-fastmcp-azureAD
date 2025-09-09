import time
import uuid

from fastapi import Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastmcp.server.auth.providers.jwt import JWTVerifier
from msal import ConfidentialClientApplication


class AuthContext:
    def __init__(self, tenant_id, client_id, client_secret):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = [f"api://{client_id}/access_as_user"]
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"

        self.msal_app = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=self.authority,
        )

        self.bearer_auth = JWTVerifier(
            jwks_uri=f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
            issuer=f"https://sts.windows.net/{tenant_id}/",
            audience=f"api://{client_id}",
        )

    def get_token_data(self, result: dict) -> dict:
        return {
            "access_token": result.get("access_token"),
            "refresh_token": result.get("refresh_token"),
            "expires_at": time.time() + result.get("expires_in", 3600),
            "id_token_claims": result.get("id_token_claims"),
        }


def setup_auth_routes(app, auth_context, redis_token_store, redirect_uri: str):
    """Setup authentication routes for the FastAPI app"""
    flow_store = {}  # Store for OAuth flows

    @app.get("/auth/login")
    def login():
        flow = auth_context.msal_app.initiate_auth_code_flow(
            scopes=auth_context.scope, redirect_uri=redirect_uri
        )
        flow_store[flow["state"]] = flow
        return RedirectResponse(flow["auth_uri"])

    @app.get("/auth/callback")
    def callback(request: Request):
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

        oid = result["id_token_claims"]["oid"]
        redis_token_store.save_token(
            oid,
            {
                "access_token": result["access_token"],
                "refresh_token": result.get("refresh_token"),
                "expires_at": time.time() + result.get("expires_in", 3600),
                "id_token_claims": result.get("id_token_claims"),
            },
        )
        auth_code = str(uuid.uuid4())
        redis_token_store.set_auth_code(auth_code, oid, 120)

        # Clean up the flow from store
        flow_store.pop(state, None)

        return HTMLResponse(
            f"Login successful. Use this code to exchange for token: <pre>{auth_code}</pre>"
        )

    @app.post("/auth/exchange")
    def exchange_auth_code(payload: dict):
        auth_code = payload.get("auth_code")
        if not auth_code:
            return {"error": "auth_code is required"}

        user_oid = redis_token_store.get_auth_code(auth_code)
        if not user_oid:
            return {"error": "Invalid or expired auth_code"}

        token_data = redis_token_store.load_token(user_oid)
        redis_token_store.delete_auth_code(auth_code)
        return token_data
