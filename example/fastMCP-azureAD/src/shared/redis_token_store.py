import redis
import json
import time
from typing import Optional

class RedisTokenStore:
    def __init__(self, host, port, password, ssl=True, prefix="token"):
        self.client = redis.Redis(host=host, port=port, password=password, ssl=ssl, ssl_cert_reqs=None)
        self.prefix = prefix

    def _make_key(self, user_oid):
        return f"{self.prefix}:{user_oid}"

    def _make_authcode_key(self, auth_code):
        return f"authcode:{auth_code}"

    def save_token(self, user_oid, token_data):
        key = self._make_key(user_oid)
        ttl = int(token_data.get("expires_at", time.time() + 3600) - time.time())
        self.client.set(key, json.dumps(token_data), ex=ttl)

    def load_token(self, user_oid) -> Optional[dict]:
        val = self.client.get(self._make_key(user_oid))
        return json.loads(val) if val else None

    def set_auth_code(self, auth_code, user_oid, ttl=120):
        self.client.setex(self._make_authcode_key(auth_code), ttl, user_oid)

    def get_auth_code(self, auth_code) -> Optional[str]:
        val = self.client.get(self._make_authcode_key(auth_code))
        return val.decode() if val else None

    def delete_auth_code(self, auth_code):
        self.client.delete(self._make_authcode_key(auth_code))

