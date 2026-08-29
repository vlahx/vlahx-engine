from __future__ import annotations

import functools
import logging
from typing import Any, Callable, TypeVar

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select

from app.models.db_models import User
from app.utils.db import SessionLocal

import hmac
import hashlib
import os

logger = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable[..., Any])


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return f"{salt}${pwd_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        if not stored_hash or "$" not in stored_hash:
            return False
        salt, pwd_hash = stored_hash.split("$", 1)
        check_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
        return hmac.compare_digest(check_hash, pwd_hash)
    except Exception:
        return False


def get_current_user_from_request(request: Request) -> User | None:
    if "session" not in request.scope:
        return None
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    try:
        uid = int(user_id)
        with SessionLocal() as db:
            user = db.execute(select(User).where(User.id == uid)).scalar_one_or_none()
            return user
    except Exception:
        logger.exception("Error loading current user")
        return None


def login_required(endpoint: F) -> F:
    @functools.wraps(endpoint)
    async def wrapper(*args: Any, **kwargs: Any):
        request: Request | None = kwargs.get("request")
        if request is None:
            for a in args:
                if isinstance(a, Request):
                    request = a
                    break

        if request is None:
            return RedirectResponse(url="/admin/login", status_code=302)

        user = get_current_user_from_request(request)
        if not user:
            if (
                request.headers.get("accept") == "application/json"
                or request.headers.get("x-requested-with") == "XMLHttpRequest"
                or request.url.path.startswith("/api/")
                or request.url.path.startswith("/admin/upload")
                or request.url.path.startswith("/admin/settings/upload")
                or request.url.path.startswith("/admin/settings/clear-image")
            ):
                return JSONResponse({"error": "Trebuie să fii autentificat"}, status_code=401)
            return RedirectResponse(url="/admin/login", status_code=302)

        request.state.user_id = user.id
        request.state.user_role = user.role or "reader"
        request.state.current_user = user



        return await endpoint(*args, **kwargs)

    return wrapper


def role_required(*allowed_roles: str) -> Callable[[F], F]:
    def decorator(endpoint: F) -> F:
        @login_required
        @functools.wraps(endpoint)
        async def wrapper(*args: Any, **kwargs: Any):
            request: Request | None = kwargs.get("request")
            if request is None:
                for a in args:
                    if isinstance(a, Request):
                        request = a
                        break

            user = getattr(request.state, "current_user", None) or (get_current_user_from_request(request) if request else None)
            if not user or not user_has_role(user, *allowed_roles):
                if request and (
                    request.headers.get("accept") == "application/json"
                    or request.headers.get("x-requested-with") == "XMLHttpRequest"
                ):
                    return JSONResponse({"error": "Nu ai permisiunea necesară pentru această acțiune."}, status_code=403)
                return RedirectResponse(url="/?error=access_denied", status_code=302)

            return await endpoint(*args, **kwargs)

        return wrapper

    return decorator

def get_user_roles(user: Any) -> list[str]:
    if not user:
        return ["reader"]
    if isinstance(user, dict):
        role_str = user.get("role", "reader")
    else:
        role_str = getattr(user, "role", "reader") or "reader"
    if not role_str:
        return ["reader"]
    return [r.strip().lower() for r in str(role_str).split(",") if r.strip()]

def user_has_role(user: Any, *allowed_roles: str) -> bool:
    user_roles = set(get_user_roles(user))
    if "admin" in user_roles:
        return True
    return bool(user_roles.intersection(set(allowed_roles)))
