"""Authentication: user accounts, password hashing, stateless HMAC tokens.

- User roles: student (goes to the Q&A page) / admin (goes to department management and the review center).
- Token format: `<user_id>.<hexdigest>`, HMAC-SHA256 signed, verified statelessly on the server.
- Department admins: admin accounts can be bound to a dept_id; unbound admins manage all departments.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import Settings
from app.storage.store import DataStore
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Seed accounts (for demos; in production, accounts should be created by admins and kept secure)
DEFAULT_USERS = [
    {"username": "student", "password": "student123", "name": "Zhang San (Student)", "role": "student", "dept_id": ""},
    {"username": "admin", "password": "admin123", "name": "System Administrator", "role": "admin", "dept_id": ""},
    {"username": "jwc_admin", "password": "admin123", "name": "Academic Affairs Admin", "role": "admin", "dept_id": "dept_jwc"},
    {"username": "cwc_admin", "password": "admin123", "name": "Finance Office Admin", "role": "admin", "dept_id": "dept_cwc"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuthService:
    """Account management and token issuance/verification."""

    def __init__(self, store: DataStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings

    # ---------- Passwords ----------
    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> str:
        salt = salt or uuid.uuid4().hex[:16]
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
        return f"{salt}${digest}"

    @staticmethod
    def verify_password(password: str, stored: str) -> bool:
        try:
            salt, digest = stored.split("$", 1)
        except ValueError:
            return False
        calc = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
        return hmac.compare_digest(calc, digest)

    # ---------- Users ----------
    async def seed_users(self) -> None:
        """Create demo accounts according to configuration.

        - Skipped when `SEED_DEMO_USERS=false` (must be disabled in production, and any created demo accounts deleted).
        - Demo accounts use fixed passwords (admin123) and are only for local demos; never use them in production.
        """
        if not self.settings.seed_demo_users:
            logger.warning("SEED_DEMO_USERS=false: skipping demo account creation (make sure no demo accounts remain in production)")
            return
        for u in DEFAULT_USERS:
            if await self.store.get("users", u["username"]) is None:
                await self.store.upsert_user(self._to_user(u))
                logger.info("Created seed account: %s (%s)", u["username"], u["role"])
        logger.warning("Demo accounts created (student/student123, admin/admin123, etc.). In production, set SEED_DEMO_USERS=false and delete these accounts.")

    @staticmethod
    def _to_user(u: dict[str, Any]) -> dict[str, Any]:
        return {
            "_id": u["username"],
            "username": u["username"],
            "name": u.get("name", u["username"]),
            "role": u.get("role", "student"),
            "dept_id": u.get("dept_id", ""),
            "password_hash": AuthService.hash_password(u["password"]),
            "created_at": _now(),
        }

    async def authenticate(self, username: str, password: str) -> Optional[dict[str, Any]]:
        user = await self.store.get("users", username.strip())
        if user is None or not self.verify_password(password, user.get("password_hash", "")):
            return None
        return self._public(user)

    async def get_user(self, user_id: str) -> Optional[dict[str, Any]]:
        user = await self.store.get("users", user_id)
        return self._public(user) if user else None

    async def list_users(self) -> list[dict[str, Any]]:
        return [self._public(u) for u in await self.store.find("users")]

    @staticmethod
    def _public(user: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": user.get("_id", ""),
            "username": user.get("username", ""),
            "name": user.get("name", ""),
            "role": user.get("role", "student"),
            "dept_id": user.get("dept_id", ""),
        }

    # ---------- Token ----------
    @staticmethod
    def _b64encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    @staticmethod
    def _b64decode(data: str) -> bytes:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))

    def issue_token(self, user_id: str) -> str:
        """Issue a compact HMAC token carrying iat/exp.

        Avoids an extra JWT dependency but uses the same base64url payload +
        HMAC-SHA256 integrity protection as JWT. Legacy non-expiring tokens are rejected.
        """
        now = int(time.time())
        payload = {
            "sub": user_id,
            "iat": now,
            "exp": now + int(self.settings.auth_token_ttl_hours * 3600),
        }
        encoded = self._b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        sig = hmac.new(self.settings.auth_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
        return f"v1.{encoded}.{self._b64encode(sig)}"

    def verify_token(self, token: str) -> Optional[str]:
        try:
            version, encoded, signature = token.split(".", 2)
            if version != "v1":
                return None
            supplied = self._b64decode(signature)
            expected = hmac.new(
                self.settings.auth_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256
            ).digest()
            if not hmac.compare_digest(supplied, expected):
                return None
            payload = json.loads(self._b64decode(encoded))
            now = int(time.time())
            issued_at = int(payload["iat"])
            expires_at = int(payload["exp"])
            user_id = str(payload["sub"])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None
        # Tolerate up to 60 seconds of clock skew while rejecting abnormal inverted time windows.
        if issued_at > now + 60 or expires_at <= now or expires_at <= issued_at:
            return None
        return user_id
