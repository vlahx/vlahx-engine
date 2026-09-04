from __future__ import annotations
from app.core.templates import render_template

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.db_models import User
from app.utils.auth import hash_password
from app.utils.db import get_db
from app.core.site_settings import write_settings

logger = logging.getLogger(__name__)

def build_install_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter(tags=["install"])

    @router.get("/install", response_class=HTMLResponse)
    async def install_page(request: Request, db: Session = Depends(get_db)):
        users_count = db.execute(select(func.count(User.id))).scalar() or 0
        if users_count > 0:
            return RedirectResponse(url="/profile", status_code=303)

        return render_template(templates, request=request, name="install.html", context={"error": None})

    @router.post("/install")
    async def install_submit(
        request: Request,
        username: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        site_name: str = Form("VlahX Platform"),
        site_tagline: str = Form("Modular High-Performance Engine"),
        db: Session = Depends(get_db),
    ):
        users_count = db.execute(select(func.count(User.id))).scalar() or 0
        if users_count > 0:
            return RedirectResponse(url="/profile", status_code=303)

        u = username.strip().lower()
        e = email.strip().lower()
        p = password.strip()

        if not u or not e or not p:
            return render_template(templates, request=request, name="install.html", context={"error": "All fields are required!"})

        pwd_hash = hash_password(p)
        now = datetime.now(timezone.utc)
        admin_user = User(
            provider="local",
            oauth_id=u,
            username=u,
            email=e,
            password_hash=pwd_hash,
            email_verified=True,
            role="admin,developer,editor,reader",
            created_at=now,
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        # Auto-login newly created user into session
        request.session["user_id"] = str(admin_user.id)

        write_settings({
            "SITE_NAME": site_name.strip() or "VlahX Platform",
            "SITE_TAGLINE": site_tagline.strip() or "Modular High-Performance Engine",
        })

        return RedirectResponse(
            url="/profile?msg=Welcome!+Your+account+has+been+registered+successfully.",
            status_code=303,
        )

    return router
