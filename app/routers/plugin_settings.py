from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Any, Dict

from app.core.config import APP_DIR, PROJECT_ROOT
from app.core.plugin_manager import (
    get_installed_plugins,
    get_plugin_settings,
    set_plugin_settings,
    set_plugin_enabled,
    load_plugin_metadata,
)
from app.core.templates import render_template
from app.utils.auth import login_required, role_required
from app.utils.db import get_db


def build_plugin_settings_router(templates) -> APIRouter:
    router = APIRouter(tags=["plugin_settings"])

    @router.get("/admin/plugins/{plugin_id}/settings", response_class=HTMLResponse)
    @role_required("admin")
    async def plugin_settings_page(request: Request, plugin_id: str, db: Session = Depends(get_db)):
        plugins = get_installed_plugins()
        plugin = None
        for p in plugins:
            if p.id == plugin_id:
                plugin = p
                break
        
        if not plugin:
            return HTMLResponse("<h1>Plugin not found</h1>", status_code=404)
        
        plugin_dir = APP_DIR / "plugins" / plugin_id
        metadata = load_plugin_metadata(plugin_dir)
        current_settings = get_plugin_settings(plugin_id)
        
        custom_template = plugin_dir / "templates" / "admin" / f"{plugin_id}_settings.html"
        custom_template_rel = f"admin/{plugin_id}_settings.html" if (custom_template.is_file() and plugin_id != "vlahx_oauth") else None

        context = {
            "title": f"Setări - {plugin.name}",
            "plugin": plugin,
            "metadata": metadata,
            "settings": current_settings,
            "settings_schema": metadata.settings if metadata else {},
            "custom_settings_template": custom_template_rel,
            "newsletter_subscribers": [],
        }
        if plugin_id == "vlahx_oauth":
            try:
                from app.utils.open_graph import public_site_origin
                from app.plugins.vlahx_oauth.plugin import PROVIDERS, get_plugin_setting
                base_url = public_site_origin(request)
                provider_data = {}
                for key, p in PROVIDERS.items():
                    enabled = get_plugin_setting(db, f"{key}_enabled", "false").strip().lower() in ("true", "1", "yes")
                    client_id = get_plugin_setting(db, f"{key}_client_id", "")
                    client_secret = get_plugin_setting(db, f"{key}_client_secret", "")
                    json_credentials = get_plugin_setting(db, f"{key}_json", "")
                    provider_data[key] = {
                        "name": p["name"],
                        "icon": p["icon"],
                        "color": p["color"],
                        "enabled": enabled,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "json_credentials": json_credentials,
                    }
                context["providers"] = provider_data
                context["base_url"] = base_url
            except Exception as e:
                pass

        if plugin_id == "newsletter":
            try:
                from app.plugins.newsletter.db import list_all_subscribers
                context["newsletter_subscribers"] = [s["email"] for s in list_all_subscribers()]
            except Exception:
                context["newsletter_subscribers"] = []
        

        plugin_locales = {}
        locales_dir = plugin_dir / "locales"
        if locales_dir.is_dir():
            import json
            for loc_file in locales_dir.glob("*.json"):
                loc_code = loc_file.stem
                try:
                    with loc_file.open("r", encoding="utf-8") as handle:
                        plugin_locales[loc_code] = json.load(handle)
                except Exception:
                    pass

        from app.models.db_models import TranslationEntry
        from sqlalchemy import select
        db_entries = db.execute(
            select(TranslationEntry).where(TranslationEntry.key.like(f"plugins.{plugin_id}.%"))
        ).scalars().all()

        db_overrides = {}
        for entry in db_entries:
            loc_code = entry.locale_code
            clean_key = entry.key.replace(f"plugins.{plugin_id}.", "")
            if loc_code not in db_overrides:
                db_overrides[loc_code] = {}
            db_overrides[loc_code][clean_key] = entry.value

        from app.core.i18n import get_site_default_locale
        def_loc = get_site_default_locale()
        sorted_locales = dict(sorted(plugin_locales.items(), key=lambda item: (0 if item[0] == def_loc else 1, item[0])))
        context["plugin_locales"] = sorted_locales
        context["default_site_locale"] = def_loc
        context["plugin_db_overrides"] = db_overrides

        return render_template(
            templates,
            request=request,
            name="admin/plugin_settings.html",
            context=context
        )

    @router.post("/admin/plugins/{plugin_id}/settings")
    @role_required("admin")
    async def save_plugin_settings(request: Request, plugin_id: str, db: Session = Depends(get_db)):
        form = await request.form()
        settings_updates: Dict[str, str] = {}
        
        plugin_dir = APP_DIR / "plugins" / plugin_id
        metadata = load_plugin_metadata(plugin_dir)
        
        if metadata and metadata.settings:
            for key, schema in metadata.settings.items():
                field_type = schema.get("type", "text")
                if field_type == "checkbox":
                    settings_updates[key] = "1" if form.get(key) else "0"
                elif field_type == "password":
                    value = form.get(key, "").strip()
                    if value:
                        settings_updates[key] = value
                else:
                    value = form.get(key, "").strip()
                    settings_updates[key] = value
        
        if "enabled" in form:
            enabled = form.get("enabled") == "1"
            set_plugin_enabled(plugin_id, enabled)
        
        if settings_updates:
            set_plugin_settings(plugin_id, settings_updates)
        
        return HTMLResponse(
            f"""
            <script>
                alert('Setările au fost salvate!');
                window.location.href = '/admin/plugins/{plugin_id}/settings';
            </script>
            """
        )

    @router.post("/admin/plugins/{plugin_id}/toggle")
    @role_required("admin")
    async def toggle_plugin(request: Request, plugin_id: str, db: Session = Depends(get_db)):
        form = await request.form()
        enabled = form.get("enabled") == "1"
        
        set_plugin_enabled(plugin_id, enabled)
        
        status_text = "activat" if enabled else "dezactivat"
        return HTMLResponse(
            f"""
            <script>
                alert('Plugin-ul a fost {status_text}!');
                window.location.href = '/admin/plugins';
            </script>
            """
        )

    @router.post("/admin/plugins/newsletter/subscriber-remove")
    @role_required("admin")
    async def newsletter_subscriber_remove(
        request: Request, email: str = Form(...)
    ):
        try:
            from app.plugins.newsletter.db import delete_subscriber
            delete_subscriber(email)
        except Exception:
            pass
        return RedirectResponse(
            url="/admin/plugins/newsletter/settings", status_code=303
        )

    @router.post("/admin/plugins/newsletter/test-email")
    @role_required("admin")
    async def newsletter_test_email(request: Request):
        try:
            from app.plugins.newsletter.email import get_smtp_params, send_single_email
            p = get_smtp_params()
            if not p:
                msg = "Eroare: Nu ai completat Host-ul SMTP sau adresa de e-mail expeditor (from_email)."
                return HTMLResponse(f"<script>alert('{msg}'); window.location.href='/admin/plugins/newsletter/settings';</script>")

            from app.core.plugin_manager import get_plugin_setting
            to_addr = get_plugin_setting("newsletter", "notify_email") or p["from_addr"]
            if not to_addr:
                msg = "Eroare: Vă rugăm să specificați adresa E-mail notificări sau E-mail expeditor."
                return HTMLResponse(f"<script>alert('{msg}'); window.location.href='/admin/plugins/newsletter/settings';</script>")

            success = send_single_email(
                to_email=to_addr,
                subject="Test SMTP Newsletter - Blog 2.0",
                body_text="Felicitări! Setările SMTP ale newsletter-ului funcționează cu succes."
            )
            if success:
                res_msg = f"✅ E-mail de test trimis cu succes către {to_addr}!"
            else:
                res_msg = "❌ Trimiterea a eșuat. Verificați logurile serverului SMTP."
        except Exception as e:
            res_msg = f"❌ Trimiterea a eșuat. Eroare: {e}"

        return HTMLResponse(f"<script>alert('{res_msg}'); window.location.href='/admin/plugins/newsletter/settings';</script>")

    return router

    @router.post("/admin/plugins/{plugin_id}/translations")
    @role_required("admin")
    async def save_plugin_translations(request: Request, plugin_id: str, db: Session = Depends(get_db)):
        form = await request.form()
        from app.models.db_models import TranslationEntry
        from sqlalchemy import select

        for form_key, form_val in form.items():
            if form_key.startswith("trans_"):
                parts = form_key.split("_", 2)
                if len(parts) == 3:
                    loc_code = parts[1]
                    clean_key = parts[2]
                    db_key = f"plugins.{plugin_id}.{clean_key}"
                    val_str = (form_val or "").strip()

                    entry = db.execute(
                        select(TranslationEntry).where(
                            TranslationEntry.locale_code == loc_code,
                            TranslationEntry.key == db_key
                        )
                    ).scalar_one_or_none()

                    if entry:
                        entry.value = val_str
                    else:
                        entry = TranslationEntry(locale_code=loc_code, key=db_key, value=val_str)
                        db.add(entry)

        db.commit()
        return HTMLResponse(
            f"<script>alert('Traducerile plugin-ului au fost salvate cu succes!'); window.location.href='/admin/plugins/{plugin_id}/settings';</script>"
        )
