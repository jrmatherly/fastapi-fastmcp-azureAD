"""
Authorization middleware for fastMCP server with Azure AD role-based access control.

This middleware implements the 2-tier security model:
1. Azure App Role-based access control (primary gatekeeper)
2. Optional On-Behalf-Of flow for delegated access
"""

import logging
from typing import Any

import jwt
from fastmcp.server.dependencies import AccessToken, get_access_token
from fastmcp.server.middleware import Middleware, MiddlewareContext


class AuthorizationMiddleware(Middleware):
    """
    Role-based authorization middleware for fastMCP servers.

    Implements Azure AD App Role-based access control by:
    - Decoding JWT tokens to extract user roles
    - Filtering MCP tools based on role permissions
    - Dynamically removing unauthorized tools from tool manager
    - Providing audit logging for tool access
    """

    def __init__(
        self,
        auth_context,
        redis_token_store=None,
        role_mappings: dict[str, list[str]] | None = None,
    ):
        """
        Initialize authorization middleware.

        Args:
            auth_context: AuthContext instance for Azure AD integration
            redis_token_store: RedisTokenStore instance for session management
            role_mappings: Custom role to tag mappings
        """
        self.auth_context = auth_context
        self.redis_token_store = redis_token_store

        # Default role mappings for tool access
        self.role_mappings = role_mappings or {
            "Task.Read": ["read", "view", "get", "list"],
            "Task.Write": ["write", "create", "update", "edit", "post", "put"],
            "Task.Delete": ["delete", "remove", "destroy"],
            "Task.All": ["*"],  # Access to all tools
            "MCPServer.Admin": ["admin", "config", "manage"],
        }

        # User context from token
        self.claims: dict[str, Any] = {}
        self.roles: list[str] = []
        self.user_id: str | None = None
        self.oid: str | None = None

    async def on_request(self, context: MiddlewareContext, call_next):
        """
        Extract user information from JWT token on each request.

        This runs for every MCP request to establish user context
        from the Bearer token provided by the client.
        """
        try:
            # Get access token from fastMCP
            access_token: AccessToken = get_access_token()

            if access_token and access_token.token:
                # Decode JWT without verification for claims extraction
                # (verification is handled by fastMCP JWT provider)
                self.claims = jwt.decode(
                    access_token.token, options={"verify_signature": False}
                )

                # Extract user information
                self.roles = self.claims.get("roles", [])
                self.user_id = self.claims.get("upn")  # User Principal Name
                self.oid = self.claims.get("oid")  # Object ID

                # Log authentication for audit
                logging.info(
                    f"Authenticated user: {self.user_id} with roles: {self.roles}"
                )

        except Exception as e:
            logging.error(f"Error extracting user context: {e}")
            # Reset context on error
            self.claims = {}
            self.roles = []
            self.user_id = None
            self.oid = None

        return await call_next(context)

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        """
        Filter MCP tools based on user roles.

        This is the core authorization logic that determines which tools
        a user can see and access based on their Azure AD App Roles.
        """
        # Get all available tools first
        result = await call_next(context)

        if not self.roles:
            # No roles = no access (fail secure)
            logging.warning(
                f"No roles found for user {self.user_id}, denying all tool access"
            )
            return []

        filtered_tools = []

        # Check each role and add corresponding tools
        for role in self.roles:
            if role == "Task.All":
                # Full access - return all tools
                filtered_tools = result
                break
            elif role in self.role_mappings:
                # Add tools matching this role's tags
                allowed_tags = self.role_mappings[role]

                for tool in result:
                    # Check if tool has any matching tags
                    tool_tags = getattr(tool, "tags", [])

                    if any(tag in tool_tags for tag in allowed_tags):
                        if tool not in filtered_tools:
                            filtered_tools.append(tool)

        # Get list of available tool names for sync with tool manager
        available_tool_names = [tool.name for tool in filtered_tools]

        # Sync with fastMCP tool manager to remove unauthorized tools
        if context.fastmcp_context:
            try:
                tool_manager = context.fastmcp_context.fastmcp._tool_manager

                # Remove tools that user doesn't have access to
                for tool in result:
                    if tool.name not in available_tool_names:
                        tool_manager.remove_tool(tool.name)

            except Exception as e:
                logging.error(f"Tool manager sync error: {str(e)}")

        # Audit log for tool access
        logging.info(
            f"User {self.user_id} granted access to {len(filtered_tools)} tools"
        )

        return filtered_tools

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """
        Audit and validate tool execution.

        This runs when a user actually calls a tool to provide
        additional security validation and audit logging.
        """
        tool_name = context.message.name if context.message else "unknown"
        tool_args = context.message.args if context.message else {}

        # Audit log for tool execution
        logging.info(
            f"User {self.user_id} calling tool: {tool_name} with args: {tool_args}"
        )

        # Additional validation can be added here for sensitive operations
        if tool_name.startswith("admin_") and "MCPServer.Admin" not in self.roles:
            raise PermissionError(
                f"User {self.user_id} lacks admin role for {tool_name}"
            )

        if context.fastmcp_context:
            try:
                # Get tool metadata for additional validation
                tool = await context.fastmcp_context.fastmcp.get_tool(tool_name)
                logging.debug(f"Executing authorized tool: {tool.name}")

            except Exception as e:
                logging.error(f"Error getting tool metadata: {e}")

        # Execute the tool
        result = await call_next(context)

        # Post-execution audit
        logging.info(f"Tool {tool_name} executed successfully for user {self.user_id}")

        return result

    def has_role(self, required_role: str) -> bool:
        """
        Check if user has a specific role.

        Args:
            required_role: Role to check for

        Returns:
            True if user has the role, False otherwise
        """
        return required_role in self.roles

    def has_any_role(self, required_roles: list[str]) -> bool:
        """
        Check if user has any of the specified roles.

        Args:
            required_roles: List of roles to check for

        Returns:
            True if user has at least one role, False otherwise
        """
        return any(role in self.roles for role in required_roles)

    def get_user_permissions(self) -> dict[str, Any]:
        """
        Get current user permissions summary.

        Returns:
            Dictionary containing user permissions and metadata
        """
        permissions = {
            "user_id": self.user_id,
            "oid": self.oid,
            "roles": self.roles,
            "permissions": [],
        }

        # Calculate effective permissions
        for role in self.roles:
            if role in self.role_mappings:
                permissions["permissions"].extend(self.role_mappings[role])

        # Remove duplicates
        permissions["permissions"] = list(set(permissions["permissions"]))

        return permissions

    async def validate_token_freshness(self) -> bool:
        """
        Validate that the user's token is still fresh and valid.

        Returns:
            True if token is fresh, False if needs refresh
        """
        if not self.oid or not self.redis_token_store:
            return False

        try:
            token_data = self.redis_token_store.load_token(self.oid)
            if token_data:
                expires_at = token_data.get("expires_at", 0)
                import time

                return expires_at > time.time() + 300  # 5 minutes buffer
            return False
        except Exception:
            return False


class RoleBasedToolFilter:
    """
    Utility class for advanced role-based tool filtering.

    Provides additional filtering capabilities beyond basic tag matching.
    """

    @staticmethod
    def filter_by_sensitivity(
        tools, user_roles: list[str], sensitivity_map: dict[str, str]
    ):
        """
        Filter tools based on sensitivity levels.

        Args:
            tools: List of tools to filter
            user_roles: User's roles
            sensitivity_map: Tool name to sensitivity level mapping

        Returns:
            Filtered list of tools
        """
        sensitivity_roles = {
            "public": ["Task.Read", "Task.Write", "Task.All"],
            "internal": ["Task.Write", "Task.All", "MCPServer.Admin"],
            "confidential": ["Task.All", "MCPServer.Admin"],
            "restricted": ["MCPServer.Admin"],
        }

        filtered = []
        for tool in tools:
            tool_sensitivity = sensitivity_map.get(tool.name, "public")
            allowed_roles = sensitivity_roles.get(tool_sensitivity, [])

            if any(role in user_roles for role in allowed_roles):
                filtered.append(tool)

        return filtered

    @staticmethod
    def filter_by_context(tools, context: dict[str, Any]):
        """
        Filter tools based on request context.

        Args:
            tools: List of tools to filter
            context: Request context information

        Returns:
            Filtered list of tools
        """
        # Example: Time-based access control
        import datetime

        current_hour = datetime.datetime.now().hour

        # Only allow admin tools during business hours (9-17)
        if not (9 <= current_hour <= 17):
            tools = [t for t in tools if not t.name.startswith("admin_")]

        return tools
