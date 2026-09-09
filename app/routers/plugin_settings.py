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

    @router.get("/admin/plugins/{plugin_id}", response_class=HTMLResponse)
    @router.get("/admin/plugins/{plugin_id}/settings", response_class=HTMLResponse)
    @role_required("admin")
    async def plugin_settings_page(request: Request, plugin_id: str, db: Session = Depends(get_db)):
        if plugin_id == "newsletter":
            return RedirectResponse(url="/admin/newsletter#tab-settings", status_code=303)
        elif plugin_id == "minishop":
            return RedirectResponse(url="/admin/minishop#tab-settings", status_code=303)
        elif plugin_id == "comments":
            return RedirectResponse(url="/admin/comments#tab-settings", status_code=303)
        elif plugin_id == "devstudio":
            return RedirectResponse(url="/admin/plugins/devstudio#tab-settings", status_code=303)
        elif plugin_id == "google_seo":
            return RedirectResponse(url="/admin/plugins/google_seo#tab-settings", status_code=303)
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
        if plugin_id == "telegram_notify":
            from app.plugins.telegram_notify.db import get_all_settings
            current_settings = get_all_settings()
        else:
            current_settings = get_plugin_settings(plugin_id)
        
        custom_template = plugin_dir / "templates" / "admin" / f"{plugin_id}_settings.html"
        custom_template_rel = f"admin/{plugin_id}_settings.html" if custom_template.is_file() else None

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
                from app.plugins.vlahx_oauth.plugin import PROVIDERS
                from app.plugins.vlahx_oauth.db import get_setting
                base_url = public_site_origin(request)
                provider_data = {}
                for key, p in PROVIDERS.items():
                    enabled = get_setting( f"{key}_enabled", "false").strip().lower() in ("true", "1", "yes")
                    client_id = get_setting( f"{key}_client_id", "")
                    client_secret = get_setting( f"{key}_client_secret", "")
                    json_credentials = get_setting( f"{key}_json", "")
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
        

        from app.core.plugin_manager import get_plugin_admin_context
        ctx = get_plugin_admin_context(plugin_id, db, context)
        template_name = f"admin/{plugin_id}_settings.html" if custom_template.is_file() else "admin/plugin_settings.html"
        return render_template(
            templates,
            request=request,
            name=template_name,
            context=ctx
        )

    @router.post("/admin/plugins/{plugin_id}")
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

        if plugin_id == "vlahx_oauth":
            try:
                from app.plugins.vlahx_oauth.db import set_setting
                from app.plugins.vlahx_oauth.plugin import PROVIDERS
                for p_key in PROVIDERS.keys():
                    enabled_val = "true" if form.get(f"{p_key}_enabled") else "false"
                    client_id_val = (form.get(f"{p_key}_client_id") or "").strip()
                    client_secret_val = (form.get(f"{p_key}_client_secret") or "").strip()
                    json_val = (form.get(f"{p_key}_json") or "").strip()

                    set_setting(f"{p_key}_enabled", enabled_val)
                    set_setting(f"{p_key}_client_id", client_id_val)
                    set_setting(f"{p_key}_client_secret", client_secret_val)
                    set_setting(f"{p_key}_json", json_val)
            except Exception as e:
                logger.warning(f"Error saving vlahx_oauth settings: {e}")
        
        if "enabled" in form:
            enabled = form.get("enabled") == "1"
            set_plugin_enabled(plugin_id, enabled)
        
        if settings_updates:
            if plugin_id == "telegram_notify":
                from app.plugins.telegram_notify.db import set_setting
                for k, v in settings_updates.items():
                    set_setting(k, str(v))
            else:
                set_plugin_settings(plugin_id, settings_updates)
        
        if plugin_id == "comments":
            redirect_target = "/admin/comments?saved_settings=1#tab-settings"
        elif plugin_id == "devstudio":
            redirect_target = "/admin/plugins/devstudio?saved_settings=1#tab-settings"
        elif plugin_id == "google_seo":
            redirect_target = "/admin/plugins/google_seo?saved_settings=1#tab-settings"
        elif plugin_id == "vlahx_oauth":
            redirect_target = "/admin/plugins/vlahx_oauth/settings?saved=1#tab-providers"
        else:
            redirect_target = f"/admin/plugins/{plugin_id}/settings"
        return RedirectResponse(url=redirect_target, status_code=303)

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

    @router.post("/admin/plugins/{plugin_id}/translations")
    @router.post("/admin/plugins/{plugin_id}/i18n/save")
    @role_required("admin")
    async def save_plugin_translations(request: Request, plugin_id: str, db: Session = Depends(get_db)):
        form = await request.form()
        import json
        from pathlib import Path

        form_locale = (form.get("locale_code") or "").strip().lower()

        # Group translations by locale code
        locale_translations: dict[str, dict[str, str]] = {}
        for form_key, form_val in form.items():
            if form_key.startswith("trans_"):
                parts = form_key.split("_", 2)
                if len(parts) == 3:
                    loc_code = parts[1].strip().lower()
                    clean_key = parts[2]
                    val_str = (form_val or "").strip()

                    if loc_code not in locale_translations:
                        locale_translations[loc_code] = {}
                    locale_translations[loc_code][clean_key] = val_str

        # Save and update the plugin's physical JSON locale files.
        plugin_locales_dir = APP_DIR / "plugins" / plugin_id / "locales"
        plugin_locales_dir.mkdir(parents=True, exist_ok=True)

        target_locales = list(locale_translations.keys())
        if form_locale and form_locale not in target_locales:
            target_locales.append(form_locale)

        for loc_code, trans_dict in locale_translations.items():
            loc_file = plugin_locales_dir / f"{loc_code}.json"
            file_data: dict[str, Any] = {"_meta": {"name": loc_code.upper(), "enabled": True}, "translations": {}}
            if loc_file.is_file():
                try:
                    with loc_file.open("r", encoding="utf-8") as f:
                        existing = json.load(f)
                        if isinstance(existing, dict):
                            file_data = existing
                except Exception:
                    pass

            if "translations" in file_data and isinstance(file_data["translations"], dict):
                for k, v in trans_dict.items():
                    file_data["translations"][k] = v
            else:
                for k, v in trans_dict.items():
                    file_data[k] = v

            with loc_file.open("w", encoding="utf-8") as f:
                json.dump(file_data, f, ensure_ascii=False, indent=2)

        from app.core.i18n import clear_i18n_cache
        clear_i18n_cache()

        if plugin_id == "comments":
            redirect_i18n = "/admin/comments?saved_i18n=1#tab-i18n"
        elif plugin_id == "devstudio":
            redirect_i18n = "/admin/plugins/devstudio?saved_i18n=1#tab-i18n"
        elif plugin_id == "google_seo":
            redirect_i18n = "/admin/plugins/google_seo?saved_i18n=1#tab-i18n"
        elif plugin_id == "minishop":
            redirect_i18n = "/admin/minishop?saved_i18n=1#tab-i18n"
        elif plugin_id == "newsletter":
            redirect_i18n = "/admin/newsletter?saved_i18n=1#tab-i18n"
        elif plugin_id == "vlahx_blog":
            redirect_i18n = "/admin/posts?saved_i18n=1#tab-i18n"
        else:
            redirect_i18n = f"/admin/plugins/{plugin_id}/settings?saved_i18n=1#tab-i18n"
        return RedirectResponse(url=redirect_i18n, status_code=303)

    @router.post("/admin/plugins/{plugin_id}/i18n/add_key")
    @role_required("admin")
    async def add_plugin_translation_key(request: Request, plugin_id: str, db: Session = Depends(get_db)):
        form = await request.form()
        import json
        from pathlib import Path

        new_key = str(form.get("new_key") or "").strip().lower().replace(" ", "_")
        locale_code = str(form.get("locale_code") or "").strip().lower() or "ro"
        new_val = str(form.get("new_val") or form.get("new_en_val") or "").strip()

        if new_key:
            plugin_locales_dir = APP_DIR / "plugins" / plugin_id / "locales"
            plugin_locales_dir.mkdir(parents=True, exist_ok=True)

            json_files = list(plugin_locales_dir.glob("*.json"))
            if not json_files:
                json_files = [plugin_locales_dir / f"{locale_code}.json"]

            target_file_found = False
            for loc_file in json_files:
                current_code = loc_file.stem.lower()
                data: dict[str, Any] = {"_meta": {"name": current_code.upper(), "enabled": True}, "translations": {}}
                if loc_file.is_file():
                    try:
                        with loc_file.open("r", encoding="utf-8") as f:
                            parsed = json.load(f)
                            if isinstance(parsed, dict):
                                data = parsed
                    except Exception:
                        pass

                trans_dict = data.get("translations", data) if isinstance(data.get("translations"), dict) else data

                if current_code == locale_code:
                    target_file_found = True
                    val_to_set = new_val
                else:
                    val_to_set = trans_dict.get(new_key, new_val)

                if "translations" in data and isinstance(data["translations"], dict):
                    data["translations"][new_key] = val_to_set
                else:
                    data[new_key] = val_to_set

                with loc_file.open("w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

            if not target_file_found and locale_code:
                loc_file = plugin_locales_dir / f"{locale_code}.json"
                data = {"_meta": {"name": locale_code.upper(), "enabled": True}, "translations": {new_key: new_val}}
                with loc_file.open("w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

            from app.core.i18n import clear_i18n_cache
            clear_i18n_cache()

        if plugin_id == "comments":
            redirect_i18n = "/admin/comments?saved_i18n=1#tab-i18n"
        elif plugin_id == "devstudio":
            redirect_i18n = "/admin/plugins/devstudio?saved_i18n=1#tab-i18n"
        elif plugin_id == "google_seo":
            redirect_i18n = "/admin/plugins/google_seo?saved_i18n=1#tab-i18n"
        elif plugin_id == "minishop":
            redirect_i18n = "/admin/minishop?saved_i18n=1#tab-i18n"
        elif plugin_id == "newsletter":
            redirect_i18n = "/admin/newsletter?saved_i18n=1#tab-i18n"
        elif plugin_id == "vlahx_blog":
            redirect_i18n = "/admin/posts?saved_i18n=1#tab-i18n"
        else:
            redirect_i18n = f"/admin/plugins/{plugin_id}/settings?saved_i18n=1#tab-i18n"
        return RedirectResponse(url=redirect_i18n, status_code=303)

    return router
