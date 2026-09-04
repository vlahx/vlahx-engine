from __future__ import annotations
import sys, os

base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)


from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import SESSION_SECRET, ROOT_SLUG_BLOCKLIST, is_static_page_slug, get_flat_post_urls
from app.core.i18n import DEFAULT_LOCALE, get_supported_locales, get_translations, resolve_locale, set_locale_cookie
from app.core.plugins import load_plugins
from app.core.templates import build_templates, render_template
from app.routers.admin import build_admin_router
from app.routers.install import build_install_router
from app.routers.api import router as api_router
from app.routers.auth import build_auth_router
from app.routers.hosting import build_hosting_router
from app.routers.plugin_settings import build_plugin_settings_router
from app.routers import media
from app.core.translation_db import ensure_default_locale
from app.utils.db import get_db, init_db, SessionLocal
from app.models.db_models import User
from sqlalchemy import func, select


def create_app() -> FastAPI:
    app = FastAPI()
    app.state.default_locale = DEFAULT_LOCALE

    init_db()
    ensure_default_locale()

    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    app.add_middleware(
        SessionMiddleware,
        secret_key=SESSION_SECRET,
        same_site="lax",
        https_only=False,
    )

    templates = build_templates("app/templates")
    app.state.templates = templates

    load_plugins(app)

    @app.middleware("http")
    async def install_and_locale_middleware(request: Request, call_next):
        path = request.url.path
        if not (path.startswith("/static") or path.startswith("/install") or path.startswith("/lang") or path.startswith("/.well-known")):
            try:
                with SessionLocal() as db:
                    users_count = db.execute(select(func.count(User.id))).scalar() or 0
                    if users_count == 0:
                        return RedirectResponse(url="/install", status_code=303)
            except Exception:
                pass

        locale = resolve_locale(request)
        request.state.locale = locale
        request.state.translations = get_translations(locale)
        response = await call_next(request)
        return response

    app.include_router(api_router, prefix="/api")
    app.include_router(build_install_router(templates))
    app.include_router(build_admin_router(templates))
    app.include_router(build_auth_router(templates))
    app.include_router(build_hosting_router(templates))
    app.include_router(build_plugin_settings_router(templates))
    app.include_router(media.router)

    @app.api_route("/lang", methods=["GET", "POST"], include_in_schema=False)
    @app.api_route("/change-language/{code}", methods=["GET", "POST"], include_in_schema=False)
    async def set_language(request: Request, code: str | None = None):
        import urllib.parse
        selected = None
        form_data = {}
        if request.method == "POST":
            try:
                form_data = dict(await request.form())
            except Exception:
                form_data = {}
        
        selected = code or form_data.get("locale") or form_data.get("lang") or request.query_params.get("locale") or request.query_params.get("lang")
        selected = (selected or DEFAULT_LOCALE).strip().lower()
        if selected not in get_supported_locales():
            selected = DEFAULT_LOCALE

        next_url = form_data.get("next") or request.query_params.get("next") or request.headers.get("referer") or "/"
        candidate = str(next_url).strip()

        # Strip lang and locale query parameters from target URL to prevent URL locking
        if "?" in candidate:
            base_p, query_p = candidate.split("?", 1)
            q_params = urllib.parse.parse_qs(query_p)
            q_params.pop("lang", None)
            q_params.pop("locale", None)
            new_query = urllib.parse.urlencode(q_params, doseq=True)
            candidate = f"{base_p}?{new_query}" if new_query else base_p

        redirect_target = "/"
        if candidate.startswith("/") and not candidate.startswith("//"):
            redirect_target = candidate

        response = RedirectResponse(url=redirect_target, status_code=303)
        set_locale_cookie(response, selected)
        return response

    @app.get("/", response_class=HTMLResponse)
    @app.get("/{slug}", response_class=HTMLResponse)
    async def root_level_post(
        request: Request, slug: str = "", db: Session = Depends(get_db)
    ):
        clean_slug = (slug or "").strip("/")
        if clean_slug:
            if clean_slug not in ROOT_SLUG_BLOCKLIST and (get_flat_post_urls() or is_static_page_slug(clean_slug)):
                try:
                    from app.plugins.vlahx_blog.plugin import serve_blog_post
                    return serve_blog_post(request, templates, db, clean_slug)
                except Exception:
                    pass
            raise HTTPException(status_code=404, detail="Page not found")

        # Root homepage (GET /)
        from app.core.config import get_homepage_mode
        hp_mode = get_homepage_mode()

        if hp_mode == "blog":
            try:
                from app.plugins.vlahx_blog.plugin import _render_blog_index
                from app.plugins.vlahx_blog.db import BlogSessionLocal
                with BlogSessionLocal() as blog_db:
                    return _render_blog_index(request, blog_db)
            except Exception:
                pass
        elif hp_mode.startswith("page:"):
            target_slug = hp_mode[5:].strip()
            if target_slug:
                try:
                    from app.plugins.vlahx_blog.plugin import serve_blog_post
                    return serve_blog_post(request, templates, db, target_slug)
                except Exception:
                    pass
        elif hp_mode == "shop":
            try:
                from app.plugins.minishop.plugin import render_shop_home
                return render_shop_home(request)
            except Exception:
                pass

        return render_template(templates, request=request, name="welcome.html", context={})

    @app.get("/.well-known/appspecific/com.chrome.devtools.json")
    async def chrome_devtools_json():
        return {}

    return app


app = create_app()

__all__ = ["app", "create_app"]
