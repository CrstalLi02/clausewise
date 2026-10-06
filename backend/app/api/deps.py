"""Auth dependencies: resolve the current user from Authorization: Bearer <token>."""
from __future__ import annotations

import hmac
from typing import Optional

from fastapi import Header, HTTPException, Request


async def get_optional_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> Optional[dict]:
    """Resolve the optional current user (returns None when not logged in, without raising)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer "):].strip()
    auth = request.app.state.container.auth
    user_id = auth.verify_token(token)
    if not user_id:
        return None
    return await auth.get_user(user_id)


async def require_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> dict:
    user = await get_optional_user(request, authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in or session expired")
    return user


async def require_admin(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> dict:
    user = await require_user(request, authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user


async def require_internal(
    request: Request,
    x_internal_token: Optional[str] = Header(default=None, alias="X-Internal-Token"),
) -> None:
    """Internal endpoint auth: verify that X-Internal-Token matches the configuration.

    Fail-closed: reject outright (503) when INTERNAL_API_TOKEN is not configured, so the endpoints are never open by default.
    """
    token = request.app.state.container.settings.internal_api_token
    if not token:
        raise HTTPException(status_code=503, detail="Internal endpoint access token is not configured (INTERNAL_API_TOKEN)")
    if not x_internal_token or not hmac.compare_digest(x_internal_token.strip(), token):
        raise HTTPException(status_code=401, detail="Invalid internal endpoint token")


def scope_dept(user: Optional[dict]) -> Optional[str]:
    """Department scope visible to an admin: only their own department if dept_id is set; empty means system admin (all)."""
    return (user or {}).get("dept_id") or None
