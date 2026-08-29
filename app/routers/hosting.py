from __future__ import annotations

import socket
import logging
from pathlib import Path
from fastapi import APIRouter, Request, Query, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.utils.db import get_db
from fastapi.templating import Jinja2Templates
from app.core.templates import render_template

logger = logging.getLogger(__name__)
SERVER_TARGET_IP = "82.76.206.101"

router = APIRouter(tags=["hosting"])


def build_hosting_router(templates: Jinja2Templates) -> APIRouter:

    @router.get("/hosting", response_class=HTMLResponse)
    @router.get("/hosting/", response_class=HTMLResponse)
    async def hosting_home(request: Request, domain: str | None = Query(None)):
        from app.core.i18n import resolve_locale, get_translation
        loc = resolve_locale(request)
        h_title = get_translation(loc, "hosting.title")
        h_sub = get_translation(loc, "hosting.subtitle")
        return render_template(
            templates,
            request=request,
            name="hosting/index.html",
            context={
                "title": f"{h_title} — VlahX Core",
                "seo_title": f"{h_title} — VlahX Core",
                "seo_description": h_sub,
                "initial_domain": domain or "",
                "target_ip": SERVER_TARGET_IP,
            },
        )

    @router.get("/hosting/check-domain")
    async def check_domain_dns(domain: str = Query(...)):
        clean_domain = domain.strip().lower().replace("http://", "").replace("https://", "").split("/")[0]
        if not clean_domain:
            return JSONResponse({"valid": False, "ip": None, "msg": "Domeniu nevalid."})

        try:
            resolved_ip = socket.gethostbyname(clean_domain)
            is_match = (resolved_ip == SERVER_TARGET_IP)
            return JSONResponse({
                "valid": is_match,
                "domain": clean_domain,
                "ip": resolved_ip,
                "target_ip": SERVER_TARGET_IP,
                "msg": f"Domeniul indică către {resolved_ip}" if is_match else f"Domeniul indică către {resolved_ip} (se așteaptă {SERVER_TARGET_IP})"
            })
        except Exception as e:
            logger.info(f"check_domain_dns resolve error for {clean_domain}: {e}")
            return JSONResponse({
                "valid": False,
                "domain": clean_domain,
                "ip": None,
                "target_ip": SERVER_TARGET_IP,
                "msg": f"Domeniul {clean_domain} nu a putut fi rezolvat încă în DNS."
            })

    @router.get("/hosting/check-availability")
    async def check_domain_availability_route(domain: str = Query(...)):
        from app.utils.check_availability import check_domain_availability
        clean_domain = domain.strip().lower().replace("http://", "").replace("https://", "").split("/")[0]
        if not clean_domain:
            return JSONResponse({"available": False, "status": "invalid", "message": "Domeniu nevalid."})

        res = await check_domain_availability(clean_domain)
        return JSONResponse({
            "domain": res.domain,
            "available": res.available,
            "status": res.status,
            "message": res.message,
            "provider": res.provider
        })

    @router.get("/hosting/packages", response_class=HTMLResponse)
    async def hosting_packages(request: Request, domain: str = Query(""), own: str = Query("0")):
        from app.core.i18n import resolve_locale, get_translation
        loc = resolve_locale(request)
        pkg_title = get_translation(loc, "hosting.packagesTitle")
        pkg_sub = get_translation(loc, "hosting.packagesSubtitle")
        clean_domain = domain.strip().lower().replace("http://", "").replace("https://", "").split("/")[0]
        return render_template(
            templates,
            request=request,
            name="hosting/packages.html",
            context={
                "title": f"{pkg_title} — VlahX Core",
                "seo_title": f"{pkg_title} — VlahX Core",
                "seo_description": pkg_sub,
                "domain": clean_domain,
                "own_domain": own == "1",
                "target_ip": SERVER_TARGET_IP,
            },
        )

    @router.get("/hosting/checkout", response_class=HTMLResponse)
    @router.get("/hosting/pay", response_class=HTMLResponse)
    async def hosting_checkout(request: Request, pkg: str = Query("starter"), domain: str = Query("")):
        clean_domain = domain.strip().lower().replace("http://", "").replace("https://", "").split("/")[0]
        return render_template(
            templates,
            request=request,
            name="hosting/checkout_coming_soon.html",
            context={
                "title": "Stripe Checkout & Provisioning — VlahX Core",
                "seo_title": "Stripe Checkout & Provisioning — VlahX Core",
                "seo_description": "Pagina de plată și activare automatizată este în curs de dezvoltare.",
                "domain": clean_domain,
                "pkg": pkg,
            },
        )

    @router.post("/hosting/brokerage-request")
    async def domain_brokerage_request(
        request: Request,
        domain: str = Form(...),
        budget: str = Form(""),
        phone: str = Form(""),
        notes: str = Form(""),
        db: Session = Depends(get_db)
    ):
        from app.utils.auth import get_current_user_from_request
        from app.core.config import get_public_site_url
        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        clean_domain = domain.strip().lower()
        user_name = f"{user.first_name if user else 'Vizitator'} {user.last_name if user else ''}".strip()
        user_email = user.email if user else "Nespecificat"
        base_url = (get_public_site_url() or str(request.base_url)).rstrip("/")

        msg = (
            f"🤝 *SOLICITARE BROKERAJ DOMENIU OCUPAT!*\n\n"
            f"👤 *Client:* {user_name} (`{user_email}`)\n"
            f"🌐 *Domeniu Vizat:* `{clean_domain}`\n"
            f"💰 *Buget Propus:* {budget.strip() or 'Nespecificat'}\n"
            f"📱 *Telefon/Contact:* {phone.strip() or 'Nespecificat'}\n"
            f"💬 *Note Client:* {notes.strip() or 'Fără detalii suplimentare'}\n\n"
            f"⚡ *Vezi în Admin:* {base_url}/admin/users"
        )
        try:
            from app.utils.telegram_notify import send_telegram_message
            send_telegram_message(msg)
        except Exception as e:
            logger.warning(f"domain_brokerage_request: Telegram notify error: {e}")

        return RedirectResponse(
            url=f"/hosting?domain={clean_domain}&msg_key=hosting.brokerageSuccess",
            status_code=303
        )

    return router
