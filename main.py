from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import SESSION_SECRET, get_flat_post_urls
from app.core.i18n import DEFAULT_LOCALE, get_supported_locales, get_translations, resolve_locale, set_locale_cookie
from app.core.plugins import load_plugins
from app.core.templates import build_templates
from app.routers.admin import build_admin_router
from app.routers.api import router as api_router
from app.routers.blog import build_blog_router, serve_blog_post
from app.routers.auth import build_auth_router
from app.routers.hosting import build_hosting_router
from app.routers.plugin_settings import build_plugin_settings_router
from app.routers import media
from app.core.translation_db import ensure_default_locale
from app.utils.db import get_db, init_db


def create_app() -> FastAPI:
    app = FastAPI()
    app.state.default_locale = DEFAULT_LOCALE

    init_db()
    ensure_default_locale()
    load_plugins(app)

    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # Cookie-based sessions for auth (admin only).
    app.add_middleware(
        SessionMiddleware,
        secret_key=SESSION_SECRET,
        same_site="lax",
        https_only=False,
    )

    templates = build_templates("app/templates")
    app.state.templates = templates

    @app.middleware("http")
    async def locale_middleware(request: Request, call_next):
        locale = resolve_locale(request)
        request.state.locale = locale
        request.state.translations = get_translations(locale)
        response = await call_next(request)
        return response

    # Blog la rădăcină: / = listă articole; /blog → redirect 301 la /. API sub /api.
    app.include_router(build_blog_router(templates))
    app.include_router(api_router, prefix="/api")
    app.include_router(build_admin_router(templates))
    app.include_router(build_auth_router(templates))
    app.include_router(build_hosting_router(templates))
    app.include_router(build_plugin_settings_router(templates))
    app.include_router(media.router)

    @app.api_route("/lang", methods=["GET", "POST"], include_in_schema=False)
    async def set_language(request: Request):
        form = await request.form() if request.method == "POST" else {}
        selected = (
            (form.get("locale") or request.query_params.get("lang") or request.cookies.get("blog_locale") or DEFAULT_LOCALE)
            .strip()
            .lower()
        )
        if selected not in get_supported_locales():
            selected = DEFAULT_LOCALE

        next_url = form.get("next") or request.query_params.get("next") or "/"
        candidate = str(next_url).strip()
        redirect_target = "/"
        if candidate.startswith("/") and not candidate.startswith("//"):
            redirect_target = candidate

        response = RedirectResponse(url=redirect_target, status_code=303)
        set_locale_cookie(response, selected)
        return response

    @app.api_route("/{slug}", methods=["GET", "HEAD"], include_in_schema=False)
    async def root_level_post(
        request: Request, slug: str, db: Session = Depends(get_db)
    ):
        """Articole / pagini statice la rădăcină când FLAT_POST_URLS e activ sau e pagină statică."""
        from app.core.config import ROOT_SLUG_BLOCKLIST, is_static_page_slug
        if slug in ROOT_SLUG_BLOCKLIST:
            raise HTTPException(status_code=404)
        if not (get_flat_post_urls() or is_static_page_slug(slug)):
            raise HTTPException(status_code=404)
        return serve_blog_post(request, templates, db, slug)

    return app


app = create_app()


__all__ = ["app", "create_app"]