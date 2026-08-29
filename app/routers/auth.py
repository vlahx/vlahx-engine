from __future__ import annotations

from datetime import datetime, timezone
import os
import json
import urllib.request
import urllib.parse
from typing import Any

from fastapi import APIRouter, Depends, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import events
from app.core.config import TELEGRAM_AUTH_URL, get_telegram_bot_username, SESSION_SECRET
from app.core.templates import render_template
from app.models.db_models import User
from app.utils.auth import login_required, get_current_user_from_request, user_has_role
from app.utils.db import get_db
from app.utils.telegram import verify_telegram_login
from app.utils.open_graph import public_site_origin
import hmac
import hashlib
import base64
import time

def create_sso_token(user: User) -> str:
    payload = {
        "user_id": user.id,
        "first_name": user.first_name or "",
        "username": user.username or f"user_{user.id}",
        "email": user.email or "",
        "role": user.role or "reader",
        "exp": int(time.time()) + 60
    }
    payload_bytes = json.dumps(payload).encode('utf-8')
    b64_payload = base64.urlsafe_b64encode(payload_bytes).decode('utf-8').rstrip('=')
    sig = hmac.new(SESSION_SECRET.encode('utf-8'), b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{sig}"

def get_repo_domain_url() -> str:
    return os.environ.get("REPO_SITE_URL", "https://repo.vlahx.org").rstrip("/")

router = APIRouter(tags=["auth"])


def get_google_credentials() -> tuple[str, str]:
    from app.core.site_settings import read_settings
    db_s = read_settings()
    cid = str(db_s.get("GOOGLE_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID", "")).strip()
    csec = str(db_s.get("GOOGLE_CLIENT_SECRET") or os.environ.get("GOOGLE_CLIENT_SECRET", "")).strip()
    return cid, csec

def get_github_credentials() -> tuple[str, str]:
    from app.core.site_settings import read_settings
    db_s = read_settings()
    cid = str(db_s.get("GITHUB_CLIENT_ID") or os.environ.get("GITHUB_CLIENT_ID", "")).strip()
    csec = str(db_s.get("GITHUB_CLIENT_SECRET") or os.environ.get("GITHUB_CLIENT_SECRET", "")).strip()
    return cid, csec

def build_auth_router(templates: Jinja2Templates) -> APIRouter:
    @router.get("/login", response_class=HTMLResponse)
    @router.get("/admin/login", response_class=HTMLResponse)
    def login_page(request: Request, msg: str | None = None, err: str | None = None):
        bot_username = get_telegram_bot_username()
        google_client_id, _ = get_google_credentials()
        github_client_id, _ = get_github_credentials()

        return render_template(
            templates,
            request=request,
            name="admin/login.html",
            context={
                "title": "Conectare — VlahX Core",
                "bot_username": bot_username or "",
                "auth_url": TELEGRAM_AUTH_URL,
                "google_client_id": google_client_id,
                "github_client_id": github_client_id,
                "msg": msg or request.query_params.get("msg"),
                "err": err or request.query_params.get("err"),
            },
        )

    @router.post("/login")
    async def classic_login(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
    ):
        from app.utils.auth import verify_password
        email_clean = email.strip().lower()
        user = db.execute(
            select(User).where(User.email == email_clean, User.password_hash.isnot(None))
        ).scalars().first()

        if not user or not user.password_hash or not verify_password(password.strip(), user.password_hash):
            return RedirectResponse(url="/login?err=Email+sau+parolă+incorectă.", status_code=303)

        if not user.email_verified:
            return RedirectResponse(url="/login?err=Adresa+de+email+nu+a+fost+verificată+încă.+Verifică+Inbox-ul+sau+Folderul+Spam+pentru+linkul+de+activare.", status_code=303)

        request.session["user_id"] = str(user.id)
        return RedirectResponse(url="/profile", status_code=303)

    @router.get("/register", response_class=HTMLResponse)
    def register_page(request: Request, msg: str | None = None, err: str | None = None):
        return render_template(
            templates,
            request=request,
            name="user/register.html",
            context={
                "title": "Înregistrare Cont — VlahX Core",
                "msg": msg or request.query_params.get("msg"),
                "err": err or request.query_params.get("err"),
            },
        )

    @router.post("/register")
    async def classic_register(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
        first_name: str = Form(...),
        last_name: str = Form(""),
        db: Session = Depends(get_db)
    ):
        from app.utils.auth import hash_password
        from app.utils.email_verification import send_verification_email
        from uuid import uuid4

        email_clean = email.strip().lower()
        if not email_clean or "@" not in email_clean:
            return RedirectResponse(url="/register?err=Adresă+de+email+nevalidă.", status_code=303)

        existing = db.execute(select(User).where(User.email == email_clean)).scalars().first()
        token = uuid4().hex
        now = datetime.now(timezone.utc)

        if existing:
            if existing.password_hash:
                return RedirectResponse(url="/register?err=Există+deja+un+cont+cu+această+adresă+de+email.", status_code=303)
            else:
                # Link classic password & email verification to existing OAuth user
                existing.first_name = first_name.strip() or existing.first_name
                existing.last_name = last_name.strip() or existing.last_name
                existing.password_hash = hash_password(password.strip())
                existing.email_verified = False
                existing.verification_token = token
                new_user = existing
        else:
            new_user = User(
                provider="email",
                oauth_id=f"email_{email_clean}",
                email=email_clean,
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                password_hash=hash_password(password.strip()),
                email_verified=False,
                verification_token=token,
                role="reader",
                created_at=now
            )
            db.add(new_user)

        db.commit()
        db.refresh(new_user)

        # Auto-subscribe new registered user email to newsletter
        if email_clean:
            try:
                from app.plugins.newsletter.db import add_or_reactivate_subscriber
                loc_user = getattr(request.state, "locale", "ro") or "ro"
                add_or_reactivate_subscriber(email_clean, locale=loc_user)
            except Exception as e_news:
                logger.warning(f"Could not auto-subscribe user to newsletter: {e_news}")

        # Send Telegram Notification Alert to Admin on New User Registration
        reg_msg = (
            f"👤 *UTILIZATOR NOU ÎNREGISTRAT PE SITE!*\n\n"
            f"📛 *Nume:* {first_name.strip()} {last_name.strip()}\n"
            f"📧 *Email:* {email_clean}\n"
            f"📅 *Data:* {now.strftime('%d.%m.%Y %H:%M UTC')}\n\n"
            f"⚡ *Vezi în Admin:* {public_site_origin(request)}/admin/users"
        )
        try:
            from app.utils.telegram_notify import send_telegram_message
            send_telegram_message(reg_msg)
        except Exception as e:
            logger.warning(f"classic_register: Telegram notify error: {e}")

        # Send verification email via no-reply@vlahx.org
        sent_ok = send_verification_email(email_clean, token, first_name.strip())
        
        # Mandatory Email Verification Redirect - DO NOT Auto-Login
        return RedirectResponse(
            url=f"/login?msg=Contul+a+fost+creat!+Un+link+de+verificare+a+fost+trimis+pe+adresa+{email_clean}.+Verifică+Inbox-ul+pentru+activare.",
            status_code=303
        )

    @router.get("/verify-email")
    async def verify_email_route(request: Request, token: str, db: Session = Depends(get_db)):
        user = db.execute(select(User).where(User.verification_token == token)).scalar_one_or_none()
        if not user:
            return RedirectResponse(url="/login?err=Token+de+verificare+nevalid+sau+expirat.", status_code=303)

        user.email_verified = True
        user.verification_token = None
        db.commit()

        request.session["user_id"] = str(user.id)
        return RedirectResponse(url="/profile?msg=Emailul+tău+a+fost+verificat+cu+succes!+Bun+venit!", status_code=303)

    @router.post("/profile/intent")
    async def save_profile_intent(request: Request, intent: str = Form(...), db: Session = Depends(get_db)):
        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/login", status_code=303)

        db_user = db.execute(select(User).where(User.id == user.id)).scalar_one_or_none() or user
        clean_intent = intent.strip()
        db_user.onboarding_intent = clean_intent

        if clean_intent == "developer" and "developer" not in db_user.roles_list and db_user.role != "admin":
            if db_user.dev_status != "approved":
                db_user.dev_status = "pending"
                db_user.dev_requested_at = datetime.now(timezone.utc)
                db.commit()

                # Trigger Telegram notification to Admin
                user_name = f"{db_user.first_name or db_user.username or 'Utilizator'} {db_user.last_name or ''}".strip()
                msg = (
                    f"🔔 *SOLICITARE ROL DEZVOLTATOR (ONBOARDING)!*\n\n"
                    f"👤 *Utilizator:* {user_name} (`ID: #{db_user.id}`)\n"
                    f"📧 *Email:* {db_user.email or 'Nespecificat'}\n"
                    f"🎯 *Intenție:* Dezvoltator Teme / Plugin (DevStudio)\n\n"
                    f"⚡ *Aprobă în Admin:* {public_site_origin(request)}/admin/users"
                )
                try:
                    from app.utils.telegram_notify import send_telegram_message
                    send_telegram_message(msg)
                except Exception as e:
                    logger.warning(f"save_profile_intent: Telegram notify error: {e}")

                return RedirectResponse(url="/profile?msg=Solicitarea+pentru+rolul+de+Dezvoltator+a+fost+trimisă!+Se+așteaptă+aprobarea+administratorului.", status_code=303)

        db.commit()
        return RedirectResponse(url=f"/profile?msg=Opțiunea+ta+({clean_intent})+a+fost+salvată!", status_code=303)

    @router.get("/dev/login")
    async def dev_login(
        request: Request,
        user_id: int = 1,
        role: str = "admin",
        db: Session = Depends(get_db),
    ):
        """Quick developer session login & elevation route for local testing."""
        stmt = select(User).where(User.id == user_id)
        user = db.execute(stmt).scalar_one_or_none()
        now = datetime.now(timezone.utc)

        if user is None:
            user = User(
                provider="dev",
                oauth_id=f"dev_{user_id}",
                username="Developer Admin",
                first_name="Dev",
                last_name="Admin",
                email="dev@camionagiul.club",
                role=role,
                created_at=now,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            if role:
                user.role = role
                db.commit()

        request.session["user_id"] = str(user.id)

        target = request.query_params.get("target", "").strip() or request.cookies.get("login_target", "").strip()
        if target == "repo" and user_has_role(user, "developer", "admin"):
            token = create_sso_token(user)
            repo_base = get_repo_domain_url()
            return RedirectResponse(url=f"{repo_base}/auth/sso?token={token}", status_code=303)

        return RedirectResponse(url="/profile", status_code=303)

    @router.get("/auth/sso-redirect")
    async def sso_redirect(request: Request, db: Session = Depends(get_db)):
        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/admin/login?next=/auth/sso-redirect", status_code=303)
        if not user_has_role(user, "developer", "admin"):
            return RedirectResponse(url="/profile?error=developer_role_required", status_code=303)

        token = create_sso_token(user)
        repo_base = get_repo_domain_url()
        return RedirectResponse(url=f"{repo_base}/auth/sso?token={token}", status_code=303)

    @router.get("/admin/pending", response_class=HTMLResponse)
    def pending_page(request: Request):
        user_id = request.session.get("user_id")
        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=303)

        return render_template(
            templates,
            request=request,
            name="admin/pending.html",
            context={"title": "Cont în Așteptare"},
        )

    @router.get("/admin/login/telegram")
    async def telegram_login(
        request: Request,
        db: Session = Depends(get_db),
    ):
        params = dict(request.query_params)

        if not verify_telegram_login(params):
            return HTMLResponse("Telegram login verification failed.", status_code=403)

        telegram_id = params.get("id")
        if not telegram_id:
            return HTMLResponse("Missing Telegram id.", status_code=400)

        provider = "telegram"
        stmt = select(User).where(User.provider == provider, User.oauth_id == str(telegram_id))
        result = db.execute(stmt)
        existing = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if existing is None:
            count_stmt = select(func.count()).select_from(User)
            user_count = db.execute(count_stmt).scalar() or 0
            initial_role = "admin" if user_count == 0 else "reader"

            existing = User(
                provider=provider,
                oauth_id=str(telegram_id),
                username=params.get("username"),
                first_name=params.get("first_name"),
                last_name=params.get("last_name"),
                image_url=params.get("photo_url"),
                role=initial_role,
                created_at=now,
            )
            db.add(existing)
            db.commit()
            db.refresh(existing)
            events.publish(
                "user.registered",
                provider=provider,
                username=existing.username,
                first_name=existing.first_name,
                last_name=existing.last_name,
                email=existing.email,
            )
        else:
            existing.username = params.get("username") or existing.username
            existing.first_name = params.get("first_name") or existing.first_name
            existing.last_name = params.get("last_name") or existing.last_name
            existing.image_url = params.get("photo_url") or existing.image_url

        db.commit()
        db.refresh(existing)

        request.session["user_id"] = str(existing.id)

        next_url = (params.get("next") or request.session.get("auth_next") or "").strip()
        if "auth_next" in request.session:
            del request.session["auth_next"]

        if existing.role == "pending":
            existing.role = "reader"
            db.commit()

        if existing.role in ("reader", "user"):
            if next_url and next_url.startswith("/") and not next_url.startswith("/admin"):
                return RedirectResponse(url=next_url, status_code=303)
            return RedirectResponse(url="/profile", status_code=303)

        target = request.cookies.get("login_target", "").strip()
        if target == "repo" and user_has_role(existing, "developer", "admin"):
            token = create_sso_token(existing)
            repo_base = get_repo_domain_url()
            return RedirectResponse(url=f"{repo_base}/auth/sso?token={token}", status_code=303)

        if next_url and next_url.startswith("/"):
            return RedirectResponse(url=next_url, status_code=303)

        return RedirectResponse(url="/admin", status_code=303)

    @router.get("/auth/google/login")
    @router.get("/oauth/login/google")
    async def google_login(request: Request):
        client_id, _ = get_google_credentials()
        if not client_id:
            return HTMLResponse("GOOGLE_CLIENT_ID nu este configurat în Baza de Date sau Mediu.", status_code=500)
        
        base = public_site_origin(request).rstrip("/")
        redirect_uri = f"{base}/oauth/callback/google"

        next_url = request.query_params.get("next", "/profile")
        request.session["auth_next"] = next_url

        google_auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            + urllib.parse.urlencode({
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "prompt": "select_account",
            })
        )
        return RedirectResponse(url=google_auth_url, status_code=303)

    @router.get("/auth/google/callback")
    @router.get("/oauth/callback/google")
    async def google_callback(
        request: Request,
        db: Session = Depends(get_db),
    ):
        code = request.query_params.get("code")
        if not code:
            return HTMLResponse("Codul de autorizare Google lipsește.", status_code=400)

        client_id, client_secret = get_google_credentials()
        base = public_site_origin(request).rstrip("/")
        redirect_uri = f"{base}/oauth/callback/google"

        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        token_data = urllib.parse.urlencode({
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }).encode("utf-8")

        try:
            req = urllib.request.Request(token_url, data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req) as resp:
                tokens = json.loads(resp.read().decode("utf-8"))
            
            access_token = tokens.get("access_token")
            if not access_token:
                return HTMLResponse("Eroare la obținerea token-ului Google.", status_code=400)

            # Fetch user info
            userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
            u_req = urllib.request.Request(userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
            with urllib.request.urlopen(u_req) as u_resp:
                user_info = json.loads(u_resp.read().decode("utf-8"))

            google_sub = str(user_info.get("sub"))
            email = user_info.get("email")
            given_name = user_info.get("given_name") or user_info.get("name")
            family_name = user_info.get("family_name")
            picture = user_info.get("picture")

            provider = "google"
            stmt = select(User).where(User.provider == provider, User.oauth_id == google_sub)
            existing = db.execute(stmt).scalar_one_or_none()
            now = datetime.now(timezone.utc)

            if existing is None:
                count_stmt = select(func.count()).select_from(User)
                user_count = db.execute(count_stmt).scalar() or 0
                initial_role = "admin" if user_count == 0 else "reader"

                existing = User(
                    provider=provider,
                    oauth_id=google_sub,
                    email=email,
                    first_name=given_name,
                    last_name=family_name,
                    image_url=picture,
                    role=initial_role,
                    created_at=now,
                )
                db.add(existing)
                db.commit()
                db.refresh(existing)
                events.publish(
                    "user.registered",
                    provider=provider,
                    first_name=existing.first_name,
                    last_name=existing.last_name,
                    email=existing.email,
                )
            else:
                existing.email = email or existing.email
                existing.first_name = given_name or existing.first_name
                existing.last_name = family_name or existing.last_name
                existing.image_url = picture or existing.image_url

            db.commit()
            db.refresh(existing)

            request.session["user_id"] = str(existing.id)

            next_url = request.session.get("auth_next")
            if next_url:
                del request.session["auth_next"]
            else:
                next_url = "/profile?msg=Te-ai+conectat+cu+succes+prin+Google%21"

            return RedirectResponse(url=next_url, status_code=303)

        except Exception as e:
            return HTMLResponse(f"Eroare autentificare Google: {e}", status_code=500)

    @router.get("/auth/github/login")
    @router.get("/oauth/login/github")
    async def github_login(request: Request):
        client_id, _ = get_github_credentials()
        if not client_id:
            return HTMLResponse("GITHUB_CLIENT_ID nu este configurat în Baza de Date sau Mediu.", status_code=500)

        base = public_site_origin(request).rstrip("/")
        redirect_uri = f"{base}/oauth/callback/github"

        next_url = request.query_params.get("next", "/profile")
        request.session["auth_next"] = next_url

        github_auth_url = (
            "https://github.com/login/oauth/authorize?"
            + urllib.parse.urlencode({
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": "read:user user:email",
            })
        )
        return RedirectResponse(url=github_auth_url, status_code=303)

    @router.get("/auth/github/callback")
    @router.get("/oauth/callback/github")
    async def github_callback(
        request: Request,
        db: Session = Depends(get_db),
    ):
        code = request.query_params.get("code")
        if not code:
            return HTMLResponse("Codul de autorizare GitHub lipsește.", status_code=400)

        client_id, client_secret = get_github_credentials()
        base = public_site_origin(request).rstrip("/")
        redirect_uri = f"{base}/oauth/callback/github"

        token_url = "https://github.com/login/oauth/access_token"
        token_data = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                token_url,
                data=token_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req) as resp:
                tokens = json.loads(resp.read().decode("utf-8"))

            access_token = tokens.get("access_token")
            if not access_token:
                err_msg = tokens.get("error_description") or tokens.get("error") or "Eroare la obținerea token-ului GitHub."
                return HTMLResponse(f"Eroare GitHub Token: {err_msg}", status_code=400)

            user_url = "https://api.github.com/user"
            u_req = urllib.request.Request(
                user_url,
                headers={
                    "Authorization": f"token {access_token}",
                    "User-Agent": "VlahX-Core-App",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(u_req) as u_resp:
                user_info = json.loads(u_resp.read().decode("utf-8"))

            github_sub = str(user_info.get("id"))
            name = user_info.get("name") or user_info.get("login")
            email = user_info.get("email")
            picture = user_info.get("avatar_url")

            if not email:
                try:
                    emails_url = "https://api.github.com/user/emails"
                    e_req = urllib.request.Request(
                        emails_url,
                        headers={
                            "Authorization": f"token {access_token}",
                            "User-Agent": "VlahX-Core-App",
                            "Accept": "application/json",
                        },
                    )
                    with urllib.request.urlopen(e_req) as e_resp:
                        emails_data = json.loads(e_resp.read().decode("utf-8"))
                        for e_item in emails_data:
                            if isinstance(e_item, dict) and e_item.get("primary"):
                                email = e_item.get("email")
                                break
                        if not email and emails_data and isinstance(emails_data[0], dict):
                            email = emails_data[0].get("email")
                except Exception:
                    pass

            provider = "github"
            stmt = select(User).where(User.provider == provider, User.oauth_id == github_sub)
            existing = db.execute(stmt).scalar_one_or_none()
            now = datetime.now(timezone.utc)

            if existing is None:
                count_stmt = select(func.count()).select_from(User)
                user_count = db.execute(count_stmt).scalar() or 0
                initial_role = "admin" if user_count == 0 else "reader"

                existing = User(
                    provider=provider,
                    oauth_id=github_sub,
                    email=email or f"{github_sub}@github.user",
                    first_name=name,
                    last_name=None,
                    image_url=picture,
                    role=initial_role,
                    email_verified=True,
                    created_at=now,
                    updated_at=now,
                )
                db.add(existing)
                db.commit()
                db.refresh(existing)
                events.publish(
                    "user.registered",
                    provider=provider,
                    first_name=existing.first_name,
                    last_name=existing.last_name,
                    email=existing.email,
                )
            else:
                existing.email = email or existing.email
                existing.first_name = name or existing.first_name
                existing.image_url = picture or existing.image_url

            db.commit()
            db.refresh(existing)

            request.session["user_id"] = str(existing.id)

            next_url = request.session.get("auth_next")
            if next_url:
                del request.session["auth_next"]
            else:
                next_url = "/profile?msg=Te-ai+conectat+cu+succes+prin+GitHub%21"

            return RedirectResponse(url=next_url, status_code=303)

        except Exception as e:
            return HTMLResponse(f"Eroare autentificare GitHub: {e}", status_code=500)

    @router.get("/profile", response_class=HTMLResponse)
    async def user_profile_page(
        request: Request,
        db: Session = Depends(get_db),
    ):
        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/admin/login?next=/profile", status_code=303)

        db_user = db.execute(select(User).where(User.id == user.id)).scalar_one_or_none() or user
        from app.core.user_purge import get_user_deletion_status
        is_pending, req_at, deadline = get_user_deletion_status(db_user)
        if is_pending and req_at and deadline:
            return render_template(
                templates,
                request=request,
                name="user/account_recovery.html",
                context={
                    "title": "Recuperare Cont — VlahX",
                    "user": db_user,
                    "requested_at_str": req_at.strftime("%d.%m.%Y la %H:%M"),
                    "deadline_str": deadline.strftime("%d.%m.%Y la %H:%M"),
                },
            )

        # Retrieve user's orders from minishop if minishop plugin exists
        orders = []
        try:
            from app.plugins.minishop.db import list_user_orders
            orders = list_user_orders(user_id=db_user.id, email=db_user.email)
        except Exception:
            pass

        return render_template(
            templates,
            request=request,
            name="user/profile.html",
            context={
                "title": "Profilul Meu — Club",
                "user": db_user,
                "orders": orders,
            },
        )

    @router.post("/profile/delete-account")
    async def user_profile_delete_account(
        request: Request,
        db: Session = Depends(get_db),
    ):
        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/admin/login", status_code=303)

        from app.core.user_purge import request_user_deletion
        request_user_deletion(db, user.id)

        if "session" in request.scope:
            request.session.clear()

        return RedirectResponse(url="/?msg=Ștergerea+contului+a+fost+programată.+Ai+la+dispoziție+30+de+zile+pentru+a-ți+recupera+contul.", status_code=303)

    @router.post("/profile/cancel-deletion")
    async def user_profile_cancel_deletion(
        request: Request,
        db: Session = Depends(get_db),
    ):
        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/admin/login", status_code=303)

        from app.core.user_purge import cancel_user_deletion
        cancel_user_deletion(db, user.id)

        return RedirectResponse(url="/profile?msg=Ștergerea+a+fost+anulată.+Contul+tău+a+fost+recuperat+cu+succes!", status_code=303)

    @router.post("/profile/update")
    async def user_profile_update(
        request: Request,
        first_name: str = Form(...),
        last_name: str = Form(None),
        email: str = Form(None),
        phone: str = Form(None),
        image_url: str = Form(None),
        bio: str = Form(None),
        avatar_file: UploadFile | None = File(None),
        db: Session = Depends(get_db),
    ):
        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/admin/login", status_code=303)

        db_user = db.execute(select(User).where(User.id == user.id)).scalar_one_or_none()
        if not db_user:
            return RedirectResponse(url="/admin/login", status_code=303)

        if first_name:
            db_user.first_name = first_name.strip()
        db_user.last_name = last_name.strip() if last_name else None
        db_user.email = email.strip() if email else None
        db_user.phone = phone.strip() if phone else None
        db_user.bio = bio.strip() if bio else None

        # Process uploaded avatar file if provided
        if avatar_file and avatar_file.filename and getattr(avatar_file, "size", 1):
            data = await avatar_file.read()
            if data and len(data) > 0:
                ext = pathlib.Path(avatar_file.filename).suffix.lower()
                if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                    ext = ".jpg"

                dest_dir = APP_DIR / "static" / "images" / "user_uploads"
                dest_dir.mkdir(parents=True, exist_ok=True)

                filename = f"avatar_{db_user.id}_{uuid4().hex[:10]}{ext}"
                dest_path = dest_dir / filename
                dest_path.write_bytes(data)

                db_user.image_url = f"/static/images/user_uploads/{filename}"
        elif image_url and image_url.strip():
            db_user.image_url = image_url.strip()

        db.commit()
        return RedirectResponse(url="/profile?updated=1", status_code=303)

    @router.get("/user/{user_id}", response_class=HTMLResponse)
    async def public_user_profile(
        request: Request,
        user_id: int,
        db: Session = Depends(get_db),
    ):
        stmt = select(User).where(User.id == user_id)
        pub_user = db.execute(stmt).scalar_one_or_none()
        if not pub_user or pub_user.deletion_requested_at is not None:
            raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit.")

        return render_template(
            templates,
            request=request,
            name="user/public_profile.html",
            context={
                "title": f"Profil {pub_user.first_name or pub_user.username} — Club",
                "public_user": pub_user,
            },
        )

    @router.get("/auth/logout")
    @router.get("/admin/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse(url="/", status_code=303)

    @router.post("/profile/request-role")
    async def user_request_role(
        request: Request,
        requested_role: str = Form(...),
        motivation: str = Form(""),
        db: Session = Depends(get_db),
    ):
        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/admin/login", status_code=303)

        db_user = db.execute(select(User).where(User.id == user.id)).scalar_one_or_none() or user

        roles_map = {
            "developer": "👨‍💻 Programator / Dezvoltator (VlahX Developer)",
            "seller": "🛍️ Vânzător (Magazin / Piață)",
            "author": "✍️ Autor / Scriitor Articole",
            "editor": "📝 Editor Conținut",
        }
        role_label = roles_map.get(requested_role, requested_role)
        user_name = f"{db_user.first_name or db_user.username or 'Utilizator'} {db_user.last_name or ''}".strip()

        if requested_role == "developer":
            db_user.dev_status = "pending"
            db_user.dev_notes = motivation.strip()
            db_user.dev_requested_at = datetime.now(timezone.utc)
            db.commit()

        msg = (
            f"🔔 *SOLICITARE ROL NOU PE SITE!*\n\n"
            f"👤 *Utilizator:* {user_name} (`ID: #{db_user.id}`)\n"
            f"📧 *Email:* {db_user.email or 'Nespecificat'}\n"
            f"📱 *Telefon:* {db_user.phone or 'Nespecificat'}\n"
            f"🎯 *Rol Solicitat:* {role_label}\n"
            f"💬 *Motivare:* {motivation.strip() or 'Fără mesaj suplimentar'}\n\n"
            f"⚡ *Aprobă în Admin:* {public_site_origin(request)}/admin/users"
        )

        try:
            from app.utils.telegram_notify import send_telegram_message
            sent_ok = send_telegram_message(msg)
            if not sent_ok:
                logger.warning("user_request_role: Telegram notification returned False")
        except Exception as e:
            logger.warning(f"user_request_role: Exception sending Telegram notification: {e}")

        return RedirectResponse(url="/profile?requested=1", status_code=303)

    return router
