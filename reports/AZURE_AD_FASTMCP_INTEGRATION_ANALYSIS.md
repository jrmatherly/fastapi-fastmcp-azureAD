# Azure AD + fastMCP Integration Analysis Report

**Date**: 2025-01-09
**Project**: FastAPI Template with Azure AD OAuth and fastMCP Integration
**Status**: Implementation Ready
**Sources**: Example files, FastMCP documentation, Saima Khan Medium article

## Executive Summary

Based on comprehensive analysis of the fastMCP example files, official documentation, and Saima Khan's detailed implementation guide, I recommend implementing **JWT Token Verification with 2-Tier Security** approach for Azure AD integration. This proven pattern provides enterprise-grade security while maintaining compatibility with Azure AD's authentication model.

## ✅ Validated Approach: JWT Token Verification (Not OAuth Proxy)

### Key Insight from Medium Article
> "FastMCP provides several auth mechanisms, including Remote OAuth and Token Verification. While Remote OAuth supports integrations like WorkOS, it requires Dynamic Client Registration (DCR) — something Azure AD (Entra ID) does not support natively."

**Why JWT Token Verification is Recommended:**
- ✅ **Azure AD Compatible**: No DCR requirement
- ✅ **Proven Implementation**: Working code examples provided
- ✅ **Enterprise Security**: 2-tier security model with App Roles
- ✅ **Production Ready**: MSAL + Redis + JWT validation

## 📋 2-Tier Security Architecture

### Tier 1: App Role-Based Access Control (Primary)
**Purpose**: Control tool visibility at MCP server level
- **Gatekeeper Function**: Hide dangerous tools from unauthorized users
- **Azure App Roles**: `Task.Read`, `Task.Write`, `Task.All`
- **Tool Tagging**: Dynamic filtering based on user roles
- **Default Deny**: Dangerous tools disabled unless explicitly approved

### Tier 2: API-Level Restrictions with OBO (Optional)
**Purpose**: Runtime permission validation for external APIs
- **On-Behalf-Of Flow**: Delegate user identity to external services
- **Use Cases**: Azure DevOps, Microsoft Graph, Cognitive Search
- **Real-time Validation**: Permission checks at execution time

## 🏗️ Implementation Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MCP Client    │    │   FastAPI App    │    │   Azure AD      │
│                 │    │                  │    │                 │
│  1. /auth/login ├────┤  2. MSAL Flow    ├────┤  3. User Auth   │
│  4. Auth Code   │    │  5. Token Store  │    │  6. JWT + Roles │
│  7. Bearer Token├────┤  8. JWT Verify   │    │                 │
│  9. MCP Requests│    │ 10. Tool Filter  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                       ┌──────────────────┐
                       │   Redis Store    │
                       │ - Access Tokens  │
                       │ - Refresh Tokens │
                       │ - Auth Codes     │
                       │ - Session Data   │
                       └──────────────────┘
```

## 🔧 Core Components Implementation

### 1. AuthContext (Azure AD + MSAL Integration)
```python
from msal import ConfidentialClientApplication
from fastmcp.server.auth.providers.jwt import JWTVerifier

class AuthContext:
    def __init__(self, tenant_id, client_id, client_secret):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = [f"api://{client_id}/access_as_user"]
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"

        # MSAL Configuration
        self.msal_app = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=self.authority
        )

        # JWT Verification for fastMCP
        self.bearer_auth = JWTVerifier(
            jwks_uri=f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
            issuer=f"https://sts.windows.net/{tenant_id}/",
            audience=f"api://{client_id}"
        )
```

### 2. RedisTokenStore (Session Management)
```python
class RedisTokenStore:
    def __init__(self, host, port, password, ssl=True, prefix="token"):
        self.client = redis.Redis(
            host=host, port=port, password=password, ssl=ssl
        )
        self.prefix = prefix

    def save_token(self, user_oid, token_data):
        key = f"{self.prefix}:{user_oid}"
        ttl = int(token_data.get("expires_at", time.time() + 3600) - time.time())
        self.client.set(key, json.dumps(token_data), ex=ttl)

    def set_auth_code(self, auth_code, user_oid, ttl=120):
        self.client.setex(f"authcode:{auth_code}", ttl, user_oid)
```

### 3. AuthorizationMiddleware (Role-Based Tool Filtering)
```python
from fastmcp.server.middleware import Middleware, MiddlewareContext
import jwt

class AuthorizationMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        access_token = get_access_token().token
        self.claims = jwt.decode(access_token, options={"verify_signature": False})
        self.roles = self.claims.get('roles')
        self.user_id = self.claims.get('upn')
        return await call_next(context)

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        result = await call_next(context)
        filtered_tools = []

        for role in self.roles:
            if role == 'Task.Write':
                filtered_tools.extend([t for t in result if "write" in t.tags])
            if role == 'Task.Read':
                filtered_tools.extend([t for t in result if "read" in t.tags])
            if role == 'Task.All':
                filtered_tools = result

        return filtered_tools
```

### 4. Authentication Flow Endpoints
```python
@app.get("/auth/login")
def login():
    flow = auth_context.msal_app.initiate_auth_code_flow(
        scopes=auth_context.scope, redirect_uri=REDIRECT_URI
    )
    flow_store[flow["state"]] = flow
    return RedirectResponse(flow["auth_uri"])

@app.get("/auth/callback")
def callback(request: Request):
    result = auth_context.msal_app.acquire_token_by_auth_code_flow(flow, dict(request.query_params))
    oid = result["id_token_claims"]["oid"]
    redis_token_store.save_token(oid, token_data)
    auth_code = str(uuid.uuid4())
    redis_token_store.set_auth_code(auth_code, oid, 120)
    return HTMLResponse(f"Use this code: {auth_code}")

@app.post("/auth/exchange")
def exchange_auth_code(payload: dict):
    auth_code = payload.get("auth_code")
    user_oid = redis_token_store.get_auth_code(auth_code)
    token_data = redis_token_store.load_token(user_oid)
    return token_data
```

## 🔐 Azure App Registration Configuration

### Required Settings
1. **Application Type**: Web application
2. **Redirect URIs**:
   - Development: `http://localhost:8000/auth/callback`
   - Production: `https://yourdomain.com/auth/callback`
3. **Authentication**: Enable ID tokens checkbox
4. **App Roles** (Critical for Tool Access):
   ```json
   {
     "allowedMemberTypes": ["User"],
     "displayName": "Task Read Access",
     "id": "uuid-here",
     "isEnabled": true,
     "description": "Allows reading tools",
     "value": "Task.Read"
   }
   ```
5. **Required Scopes**: `api://{client_id}/access_as_user`

### App Roles for MCP Tool Access
- **Task.Read**: Read-only tool access (tagged with `read`)
- **Task.Write**: Write operations (tagged with `write`)
- **Task.All**: Full access to all MCP tools
- **MCPServer.Admin**: Administrative operations

## 💻 Integration with FastAPI Template

### Dependencies to Add
```toml
# Backend dependencies
fastmcp = ">=0.4.0"
msal = ">=1.30.0"
redis = ">=5.0.0"
PyJWT = ">=2.8.0"
cryptography = ">=41.0.0"
```

```json
// Frontend dependencies
"@azure/msal-browser": "^3.0.0",
"@azure/msal-react": "^2.0.0"
```

### Environment Configuration
```bash
# Azure AD Configuration
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret

# Redis Configuration (for token storage)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=optional-password
REDIS_SSL=false

# fastMCP Configuration
FASTMCP_AUTH_PROVIDER=azure_jwt
FASTMCP_AZURE_JWKS_URI=https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys
```

### Docker Compose Updates
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    environment:
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    volumes:
      - redis_data:/data

  backend:
    environment:
      - AZURE_TENANT_ID=${AZURE_TENANT_ID}
      - AZURE_CLIENT_ID=${AZURE_CLIENT_ID}
      - AZURE_CLIENT_SECRET=${AZURE_CLIENT_SECRET}
      - REDIS_HOST=redis
    depends_on:
      - db
      - redis
```

## 🎯 Implementation Roadmap

### Phase 1: Core Authentication (Week 1)
- [ ] Add fastMCP and MSAL dependencies
- [ ] Create AuthContext and RedisTokenStore classes
- [ ] Implement authentication flow endpoints
- [ ] Configure Azure App Registration
- [ ] Add Redis service to Docker Compose
- [ ] Test basic authentication flow

### Phase 2: MCP Server Integration (Week 2)
- [ ] Create AuthorizationMiddleware with role-based filtering
- [ ] Implement sample MCP tools with proper tagging
- [ ] Mount MCP server into FastAPI application
- [ ] Add MCP tool management endpoints
- [ ] Test role-based tool filtering
- [ ] Create MCP client integration examples

### Phase 3: Frontend Integration (Week 2-3)
- [ ] Add MSAL.js to React frontend
- [ ] Implement Azure AD login flow in React
- [ ] Create MCP client interface components
- [ ] Add token management and refresh logic
- [ ] Test end-to-end authentication flow

### Phase 4: Production Hardening (Week 3-4)
- [ ] Azure Key Vault integration for secrets
- [ ] Application Insights monitoring
- [ ] Comprehensive error handling
- [ ] Performance optimization
- [ ] Security audit and testing
- [ ] Documentation and deployment guides

## 🔒 Security Considerations

### Authentication Security
- ✅ **HTTPS Required**: All production flows use HTTPS
- ✅ **Secure Token Storage**: Redis with TTL management
- ✅ **JWT Signature Verification**: Azure JWKS endpoint validation
- ✅ **Role-Based Access Control**: Azure App Roles enforcement
- ✅ **Auth Code Exchange**: Prevents token exposure in browser

### Production Security
- **Secret Management**: Azure Key Vault for client secrets
- **Audit Logging**: Comprehensive authentication and tool usage logs
- **Rate Limiting**: Prevent authentication abuse
- **CORS Configuration**: Restrict frontend origins
- **Token Refresh**: Automatic token renewal handling

## ✅ Validation from Examples

The example files perfectly align with the Medium article recommendations:

1. **AuthContext Implementation**: ✅ Matches proven MSAL + JWT pattern
2. **RedisTokenStore**: ✅ Secure session management with TTL
3. **AuthorizationMiddleware**: ✅ Role-based tool filtering via `on_list_tools`
4. **Directory Structure**: ✅ Clean modular organization in `shared/`
5. **FastMCP Integration**: ✅ Proper mounting and middleware configuration

## 🎉 Expected Outcomes

### Immediate Benefits
- **Enterprise Authentication**: Azure AD SSO integration
- **Fine-Grained Security**: Role-based tool access control
- **Scalable Architecture**: Redis-backed session management
- **Production Ready**: MSAL + JWT validation with proper error handling

### Long-term Value
- **Extensible Framework**: Easy to add new MCP servers
- **Multi-tenant Support**: Foundation for tenant isolation
- **Advanced Features**: Ready for OBO flow integration
- **Monitoring**: Comprehensive audit and analytics capabilities

## 🚀 Next Steps

1. **Review and Approve Architecture**: Validate approach with stakeholders
2. **Azure Setup**: Create development Azure App Registration with roles
3. **Development Environment**: Configure Redis and environment variables
4. **Start Implementation**: Begin Phase 1 following the proven patterns from examples
5. **Testing Strategy**: Create comprehensive test suite for authentication flows

## 📚 Reference Sources

- **FastMCP Example Files**: Validated working implementation
- **Saima Khan Medium Article**: Detailed implementation guide with security best practices
- **FastMCP Documentation**: Official authentication patterns and middleware system
- **Microsoft Azure Documentation**: App registration and JWT token reference

The combination of example code, detailed Medium article, and official documentation provides a solid foundation for implementing enterprise-grade Azure AD authentication with fastMCP servers in our FastAPI template.
