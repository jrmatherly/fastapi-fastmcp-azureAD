"""
Redis-based token storage for Azure AD authentication sessions.

This module provides secure, scalable token storage with TTL management
for Azure AD access tokens, refresh tokens, and auth codes.
"""

import json
import logging
import time
from typing import Any

import redis
from redis import Redis


class RedisTokenStore:
    """
    Redis-based token storage with TTL management.

    Provides secure storage for:
    - Access tokens with expiration handling
    - Refresh tokens for token renewal
    - Auth codes for client exchange flow
    - Session data and user context
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: str | None = None,
        ssl: bool = False,
        prefix: str = "azuread",
        db: int = 0,
    ):
        """
        Initialize Redis token store.

        Args:
            host: Redis server hostname
            port: Redis server port
            password: Redis password (optional)
            ssl: Enable SSL connection
            prefix: Key prefix for token storage
            db: Redis database number
        """
        self.client = Redis(
            host=host,
            port=port,
            password=password,
            ssl=ssl,
            db=db,
            decode_responses=True,  # Auto-decode responses to strings
        )
        self.prefix = prefix

        # Test connection
        try:
            self.client.ping()
        except redis.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to Redis: {e}")

    def _get_token_key(self, user_oid: str) -> str:
        """Generate Redis key for user token storage."""
        return f"{self.prefix}:token:{user_oid}"

    def _get_auth_code_key(self, auth_code: str) -> str:
        """Generate Redis key for auth code storage."""
        return f"{self.prefix}:authcode:{auth_code}"

    def _get_session_key(self, session_id: str) -> str:
        """Generate Redis key for session storage."""
        return f"{self.prefix}:session:{session_id}"

    def save_token(self, user_oid: str, token_data: dict[str, Any]) -> bool:
        """
        Save user token data with appropriate TTL.

        Args:
            user_oid: User object identifier from Azure AD
            token_data: Token data including access_token, refresh_token, expires_at

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            key = self._get_token_key(user_oid)

            # Calculate TTL from expires_at, with minimum of 60 seconds
            expires_at = token_data.get("expires_at", time.time() + 3600)
            ttl = max(60, int(expires_at - time.time()))

            # Add metadata
            token_data_with_meta = {
                **token_data,
                "stored_at": time.time(),
                "user_oid": user_oid,
            }

            self.client.setex(key, ttl, json.dumps(token_data_with_meta))
            return True
        except Exception as e:
            logging.error(f"Error saving token for user {user_oid}: {e}")
            return False

    def load_token(self, user_oid: str) -> dict[str, Any] | None:
        """
        Load user token data from Redis.

        Args:
            user_oid: User object identifier

        Returns:
            Token data if found and valid, None otherwise
        """
        try:
            key = self._get_token_key(user_oid)
            data = self.client.get(key)

            if data:
                token_data = json.loads(data)

                # Check if token is still valid
                expires_at = token_data.get("expires_at", 0)
                if expires_at > time.time():
                    return token_data
                else:
                    # Token expired, remove it
                    self.client.delete(key)
                    return None
            return None
        except Exception as e:
            logging.error(f"Error loading token for user {user_oid}: {e}")
            return None

    def delete_token(self, user_oid: str) -> bool:
        """
        Delete user token data.

        Args:
            user_oid: User object identifier

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            key = self._get_token_key(user_oid)
            return bool(self.client.delete(key))
        except Exception as e:
            logging.error(f"Error deleting token for user {user_oid}: {e}")
            return False

    def set_auth_code(self, auth_code: str, user_oid: str, ttl: int = 120) -> bool:
        """
        Store auth code for token exchange.

        Args:
            auth_code: Generated auth code
            user_oid: User object identifier
            ttl: Time to live in seconds (default 120 seconds)

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            key = self._get_auth_code_key(auth_code)
            data = {
                "user_oid": user_oid,
                "created_at": time.time(),
                "auth_code": auth_code,
            }
            self.client.setex(key, ttl, json.dumps(data))
            return True
        except Exception as e:
            logging.error(f"Error setting auth code {auth_code}: {e}")
            return False

    def get_auth_code(self, auth_code: str) -> str | None:
        """
        Retrieve user OID for auth code.

        Args:
            auth_code: Auth code to lookup

        Returns:
            User OID if found, None otherwise
        """
        try:
            key = self._get_auth_code_key(auth_code)
            data = self.client.get(key)

            if data:
                auth_data = json.loads(data)
                return auth_data.get("user_oid")
            return None
        except Exception as e:
            logging.error(f"Error getting auth code {auth_code}: {e}")
            return None

    def delete_auth_code(self, auth_code: str) -> bool:
        """
        Delete auth code after use.

        Args:
            auth_code: Auth code to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            key = self._get_auth_code_key(auth_code)
            return bool(self.client.delete(key))
        except Exception as e:
            logging.error(f"Error deleting auth code {auth_code}: {e}")
            return False

    def save_session(
        self, session_id: str, session_data: dict[str, Any], ttl: int = 3600
    ) -> bool:
        """
        Save session data.

        Args:
            session_id: Session identifier
            session_data: Session data to store
            ttl: Time to live in seconds

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            key = self._get_session_key(session_id)
            session_data_with_meta = {
                **session_data,
                "created_at": time.time(),
                "session_id": session_id,
            }
            self.client.setex(key, ttl, json.dumps(session_data_with_meta))
            return True
        except Exception as e:
            logging.error(f"Error saving session {session_id}: {e}")
            return False

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        """
        Load session data.

        Args:
            session_id: Session identifier

        Returns:
            Session data if found, None otherwise
        """
        try:
            key = self._get_session_key(session_id)
            data = self.client.get(key)

            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logging.error(f"Error loading session {session_id}: {e}")
            return None

    def delete_session(self, session_id: str) -> bool:
        """
        Delete session data.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            key = self._get_session_key(session_id)
            return bool(self.client.delete(key))
        except Exception as e:
            logging.error(f"Error deleting session {session_id}: {e}")
            return False

    def get_user_sessions(self, user_oid: str) -> list:
        """
        Get all active sessions for a user.

        Args:
            user_oid: User object identifier

        Returns:
            List of active session IDs
        """
        try:
            pattern = f"{self.prefix}:session:*"
            sessions = []

            for key in self.client.scan_iter(match=pattern):
                data = self.client.get(key)
                if data:
                    session_data = json.loads(data)
                    if session_data.get("user_oid") == user_oid:
                        sessions.append(session_data.get("session_id"))

            return sessions
        except Exception as e:
            logging.error(f"Error getting sessions for user {user_oid}: {e}")
            return []

    def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired tokens manually (Redis handles TTL automatically).

        Returns:
            Number of tokens cleaned up
        """
        # Redis handles TTL automatically, but this method can be used
        # for additional cleanup logic if needed
        return 0

    def health_check(self) -> bool:
        """
        Check Redis connection health.

        Returns:
            True if Redis is accessible, False otherwise
        """
        try:
            return self.client.ping()
        except Exception:
            return False
