from __future__ import annotations

import json
import logging
import pathlib
import shutil
import tempfile
from datetime import datetime, timezone
from zipfile import ZipFile
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.db_models import Post as PostModel, User, Category

from app.core.config import (
    APP_DIR,
    ADMIN_ENABLE_CONTAINER_RESTART,
    PROJECT_ROOT,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_BOT_USERNAME,
    TELEGRAM_NOTIFY_CHAT_ID,
    _get_static_nav_items_raw,
    get_active_theme,
    get_flat_post_urls,
    get_nav_fixed_post_label_setting,
    get_nav_fixed_post_links,
    get_nav_fixed_post_slug_setting,
    get_og_card_image_path,
    get_post_image_crop_og,
    get_post_image_max_edge,
    get_post_image_output_height,
    get_post_image_output_width,
    get_public_site_url,
    get_site_brand_image_path,
    get_site_display_name,
    get_site_favicon_path,
    get_site_nav_icon_path,
    get_site_tagline,
    get_homepage_mode,
    is_static_page_slug,
    post_public_path,
)
from app.core.posts_db import (
    create_category,
    delete_category_by_id,
    delete_post,
    get_post,
    list_categories,
    list_posts,
    save_post,
    slugify,
)
from app.core.site_settings import read_settings, write_settings
from app.utils.db import SessionLocal
from app.models.db_models import AppSetting
from app.core.plugin_db_settings import (
    get_plugin_setting,
    has_plugin_setting,
    set_plugin_settings,
)
from app.core.plugin_package import (
    extract_plugin_zip,
    list_installed_plugins,
    safe_plugin_id,
)
from app.core.process_restart import sigterm_self_after_delay
from app.core.site_uploads import unlink_site_upload_file
from app.core.templates import render_template
from app.core.themes import list_installed_themes, set_active_theme
from app.core.i18n import (
    DEFAULT_LOCALE,
    get_available_locales,
)
from app.utils.auth import login_required, role_required
from app.utils.db import get_db
from app.utils.post_image import process_post_upload

logger = logging.getLogger(__name__)

_IMAGE_SETTING_KEYS = frozenset(
    {
        "SITE_FAVICON_PATH",
        "SITE_BRAND_IMAGE_PATH",
        "OG_CARD_IMAGE_PATH",
        "SITE_NAV_ICON_PATH",
    }
)
_SITE_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg"})

_THEME_SLUG_OK = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_-")
_THEME_SLUG_RESERVED = frozenset({"default", "static", "themes", "core"})


def build_admin_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter(tags=["admin"])

    @router.get("/admin", response_class=HTMLResponse)
    @role_required("admin", "editor", "author")
    async def admin_home(request: Request, db: Session = Depends(get_db)):
        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        if user and user.role == "author":
            from app.models.db_models import Post
            from sqlalchemy import select
            stmt = select(Post).where(Post.author_id == user.id).order_by(Post.created_at.desc())
            posts = db.execute(stmt).scalars().all()
        else:
            posts = list_posts(db, include_drafts=True)
        categories = list_categories(db)
        return render_template(
            templates,
            request=request,
            name="admin/index.html",
            context={"posts": posts, "categories": categories, "title": "Admin Dashboard"},
        )

    @router.get("/admin/users", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_users(request: Request, msg: str | None = None, err: str | None = None, db: Session = Depends(get_db)):
        from app.models.db_models import User
        from sqlalchemy import select
        users = db.execute(select(User).order_by(User.id.asc())).scalars().all()
        return render_template(
            templates,
            request=request,
            name="admin/users.html",
            context={"users": users, "msg": msg, "err": err, "title": "Utilizatori & Roluri"},
        )

    @router.post("/admin/users/{user_id}/role")
    @role_required("admin")
    async def admin_user_change_role(request: Request, user_id: int, role: str | None = Form(None), db: Session = Depends(get_db)):
        from app.models.db_models import User
        from sqlalchemy import select, func
        target_user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not target_user:
            return RedirectResponse(url="/admin/users?err=Utilizatorul+nu+a+fost+găsit", status_code=303)
        
        current_uid = getattr(request.state, "user_id", None)
        if current_uid and current_uid == user_id and role != "admin":
            admin_count = db.execute(select(func.count()).select_from(User).where(User.role == "admin")).scalar() or 0
            if admin_count <= 1:
                return RedirectResponse(url="/admin/users?err=Nu+îți+poți+revoca+singur+rolul+de+Admin!", status_code=303)
        
        form = await request.form()
        roles_selected = form.getlist("roles")
        if not roles_selected and form.get("role"):
            roles_selected = [form.get("role")]
            
        valid_roles = ("admin", "editor", "seller", "author", "developer", "reader", "pending")
        clean_roles = [r.strip().lower() for r in roles_selected if r.strip().lower() in valid_roles]
        if not clean_roles:
            clean_roles = ["reader"]
            
        final_role_str = ",".join(list(dict.fromkeys(clean_roles)))
        target_user.role = final_role_str
        db.commit()
        return RedirectResponse(url="/admin/users?msg=Roluri+actualizate+cu+succes!", status_code=303)

    @router.post("/admin/users/{user_id}/approve-developer")
    @role_required("admin")
    async def admin_user_approve_developer(request: Request, user_id: int, db: Session = Depends(get_db)):
        from app.models.db_models import User
        from sqlalchemy import select
        target_user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not target_user:
            return RedirectResponse(url="/admin/users?err=Utilizatorul+nu+a+fost+găsit", status_code=303)
        
        current_roles = target_user.roles_list
        if "developer" not in current_roles:
            current_roles.append("developer")
        
        target_user.role = ",".join(list(dict.fromkeys(current_roles)))
        target_user.dev_status = "approved"
        db.commit()
        return RedirectResponse(url="/admin/users?msg=Cerere+Developer+aprobată+cu+succes!", status_code=303)

    @router.post("/admin/users/{user_id}/reject-developer")
    @role_required("admin")
    async def admin_user_reject_developer(request: Request, user_id: int, db: Session = Depends(get_db)):
        from app.models.db_models import User
        from sqlalchemy import select
        target_user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not target_user:
            return RedirectResponse(url="/admin/users?err=Utilizatorul+nu+a+fost+găsit", status_code=303)
        
        target_user.dev_status = "rejected"
        db.commit()
        return RedirectResponse(url="/admin/users?msg=Cererea+de+Developer+a+fost+respinsă.", status_code=303)

    @router.post("/admin/users/{user_id}/delete")
    @role_required("admin")
    async def admin_user_delete(request: Request, user_id: int, db: Session = Depends(get_db)):
        from app.models.db_models import User, Post
        from sqlalchemy import select, func

        target_user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not target_user:
            return RedirectResponse(url="/admin/users?err=Utilizatorul+nu+a+fost+găsit", status_code=303)

        current_uid = getattr(request.state, "user_id", None)
        if current_uid and current_uid == user_id:
            return RedirectResponse(url="/admin/users?err=Nu+îți+poți+șterge+propriul+cont!", status_code=303)

        if target_user.role == "admin":
            admin_count = db.execute(select(func.count()).select_from(User).where(User.role == "admin")).scalar() or 0
            if admin_count <= 1:
                return RedirectResponse(url="/admin/users?err=Nu+poți+șterge+singurul+Admin+din+sistem!", status_code=303)

        from app.core.user_purge import purge_user_data
        purge_user_data(db, user_id)

        return RedirectResponse(url="/admin/users?msg=Utilizatorul+și+toate+datele+sale+au+fost+șterse+definitiv+cu+succes!", status_code=303)

    def _editor_document_base(request: Request) -> str:
        base = get_public_site_url()
        if base:
            return f"{base.rstrip('/')}/"
        u = str(request.base_url).rstrip("/")
        return f"{u}/"

    @router.get("/admin/new", response_class=HTMLResponse)
    @role_required("admin", "editor", "author")
    async def admin_new(request: Request, db: Session = Depends(get_db)):
        categories = list_categories(db)
        locales = get_available_locales()

        return render_template(
            templates,
            request=request,
            name="admin/editor.html",
            context={
                "title": "Post nou",
                "post": None,
                "categories": categories,
                "locales": locales,
                "post_translations": {},
                "editor_document_base": _editor_document_base(request),
                "editor_nav_fixed": False,
                "editor_nav_fixed_label": "",
                "editor_nav_location": "navbar",
            },
        )

    @router.get("/admin/edit/{slug}", response_class=HTMLResponse)
    @role_required("admin", "editor", "author")
    async def admin_edit(request: Request, slug: str, db: Session = Depends(get_db)):
        post = get_post(db, slug)
        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        if post and user and user.role == "author" and getattr(post, "author_id", None) != user.id:
            return RedirectResponse(url="/admin?error=access_denied", status_code=302)
        if not post:
            return RedirectResponse(url="/admin/new", status_code=302)
        categories = list_categories(db)
        locales = get_available_locales()
        post_trans = {}

        with SessionLocal() as db_sess:
            stmt = select(PostModel).where(PostModel.slug == slug)
            row = db_sess.execute(stmt).scalars().first()
            if row:
                from app.core.posts_db import get_post_translations
                post_trans = get_post_translations(db_sess, row.id)

        editor_nav_fixed = False
        editor_nav_fixed_label = ""
        editor_nav_location = "navbar"
        from app.core.config import _get_static_nav_items_raw
        for item in _get_static_nav_items_raw():
            if item.get("slug") == post.slug:
                editor_nav_fixed = True
                editor_nav_fixed_label = item.get("label", "")
                editor_nav_location = item.get("location", "navbar")
                break
        return render_template(
            templates,
            request=request,
            name="admin/editor.html",
            context={
                "title": f"Editează: {post.title}",
                "post": post,
                "categories": categories,
                "locales": locales,
                "post_translations": post_trans,
                "editor_document_base": _editor_document_base(request),
                "editor_nav_fixed": editor_nav_fixed,
                "editor_nav_fixed_label": editor_nav_fixed_label,
                "editor_nav_location": editor_nav_location,
            },
        )

    @router.post("/admin/save")
    @role_required("admin", "editor", "author")
    async def admin_save(request: Request, db: Session = Depends(get_db)):
        form = await request.form()

        def _txt(key: str) -> str:
            v = form.get(key)
            if v is None:
                return ""
            if isinstance(v, str):
                return v.strip()
            if isinstance(v, (bytes, bytearray)):
                return bytes(v).decode("utf-8", errors="replace").strip()
            return ""

        def _chk(key: str) -> bool:
            v = form.get(key)
            if v is None:
                return False
            if isinstance(v, str):
                return v.lower() in ("1", "true", "on", "yes")
            return bool(v)

        title = _txt("title")
        slug_in = _txt("slug")
        excerpt = _txt("excerpt")
        category = _txt("category")
        hero_image_url = _txt("hero_image_url")
        content_html = _txt("content_html")
        draft = _chk("draft")
        published_at_raw = _txt("published_at")
        meta_keywords = _txt("meta_keywords")
        editing_original_slug = _txt("editing_original_slug")
        nav_fixed = _chk("nav_fixed")
        nav_fixed_label = _txt("nav_fixed_label") or None
        nav_location = _txt("nav_location") or "navbar"
        if nav_location not in ("navbar", "footer", "both"):
            nav_location = "navbar"

        locales = get_available_locales()
        translations_to_save = {}
        for loc in locales:
            code_loc = loc["code"]
            t_title = _txt(f"title_{code_loc}")
            t_excerpt = _txt(f"excerpt_{code_loc}")
            t_content = _txt(f"content_html_{code_loc}")
            t_keywords = _txt(f"meta_keywords_{code_loc}")
            if t_title or t_content or t_excerpt or t_keywords:
                translations_to_save[code_loc] = {
                    "title": t_title or "",
                    "excerpt": t_excerpt or "",
                    "content_html": t_content or "",
                    "meta_keywords": t_keywords or "",
                }

        primary_title = title
        if not primary_title and translations_to_save:
            first_code = list(translations_to_save.keys())[0]
            primary_title = translations_to_save[first_code]["title"]

        primary_excerpt = excerpt
        if not primary_excerpt and translations_to_save:
            first_code = list(translations_to_save.keys())[0]
            primary_excerpt = translations_to_save[first_code]["excerpt"]

        primary_content = content_html
        if not primary_content and translations_to_save:
            first_code = list(translations_to_save.keys())[0]
            primary_content = translations_to_save[first_code]["content_html"]

        primary_keywords = meta_keywords
        if not primary_keywords and translations_to_save:
            first_code = list(translations_to_save.keys())[0]
            primary_keywords = translations_to_save[first_code].get("meta_keywords", "")

        slug_final = slugify(slug_in or primary_title)
        dt = None
        if published_at_raw:
            try:
                dt = datetime.fromisoformat(published_at_raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                dt = None

        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        author_id = user.id if user else (getattr(request.state, "user_id", None) or 1)

        post = save_post(
            db,
            author_id=author_id,
            slug=slug_final,
            original_slug=editing_original_slug,
            title=primary_title or "Post",
            excerpt=primary_excerpt,
            category=category or None,
            hero_image_url=hero_image_url or None,
            content_html=primary_content,
            draft=draft,
            meta_keywords=primary_keywords,
            published_at=dt,
        )

        if translations_to_save:
            from sqlalchemy import select
            from app.models.db_models import Post as PostModel
            from app.core.posts_db import save_post_translations
            row = db.execute(select(PostModel).where(PostModel.slug == post.slug)).scalars().first()
            if row:
                save_post_translations(db, row.id, translations_to_save)

        cur_links = read_settings().get("STATIC_NAV_LINKS") or []
        if not isinstance(cur_links, list):
            cur_links = []
        cleaned_links = []
        for item in cur_links:
            if isinstance(item, dict):
                slug = str(item.get("slug") or item.get("value") or "").strip()
                if slug:
                    cleaned_links.append({
                        "slug": slug,
                        "label": str(item.get("label") or item.get("fixed_label") or slug).strip(),
                        "fixed_label": str(item.get("fixed_label") or item.get("label") or slug).strip(),
                        "labels": item.get("labels") if isinstance(item.get("labels"), dict) else {},
                        "url": str(item.get("url") or item.get("href") or f"/{slug}").strip(),
                        "target": str(item.get("target") or "_self").strip(),
                        "location": str(item.get("location") or "navbar").strip().lower(),
                    })

        target_slugs = {s.strip() for s in (editing_original_slug, post.slug) if s and s.strip()}
        if nav_fixed:
            derived_label = post.title or slug_final
            existing_match = next((it for it in cur_links if isinstance(it, dict) and str(it.get("slug") or "").strip() in target_slugs), {})
            existing_labels = existing_match.get("labels") if isinstance(existing_match.get("labels"), dict) else {}
            new_item = {
                "slug": post.slug,
                "label": derived_label,
                "fixed_label": derived_label,
                "labels": existing_labels,
                "url": post_public_path(post.slug),
                "target": "_self",
                "location": nav_location,
            }
            filtered = [item for item in cleaned_links if str(item.get("slug") or "").strip() not in target_slugs]
            filtered.append(new_item)
            write_settings({"STATIC_NAV_LINKS": filtered})
        else:
            if target_slugs:
                filtered = [
                    item for item in cleaned_links
                    if str(item.get("slug") or "").strip() not in target_slugs
                ]
                write_settings({"STATIC_NAV_LINKS": filtered})

        from app.core.config import invalidate_nav_fixed_post_links_cache
        invalidate_nav_fixed_post_links_cache()



        return RedirectResponse(url="/admin?msg=Postare+salvată+cu+succes!", status_code=303)

    @router.get("/admin/categories", response_class=HTMLResponse)
    @router.get("/admin/categories/", response_class=HTMLResponse)
    @role_required("admin", "editor")
    async def admin_categories(request: Request, db: Session = Depends(get_db)):
        categories = list_categories(db)
        return render_template(
            templates,
            request=request,
            name="admin/categories.html",
            context={"title": "Categorii", "categories": categories},
        )

    @router.post("/admin/categories/save")
    @role_required("admin", "editor")
    async def admin_save_category(request: Request, db: Session = Depends(get_db)):
        form = await request.form()

        def _txt(key: str) -> str:
            v = form.get(key)
            if v is None:
                return ""
            if isinstance(v, str):
                return v.strip()
            if isinstance(v, (bytes, bytearray)):
                return bytes(v).decode("utf-8", errors="replace").strip()
            return ""

        cat_id_raw = _txt("category_id")
        name = _txt("name")
        parent_ref = _txt("parent_id") or _txt("parent")
        description = _txt("description")
        translations_json = _txt("translations_json")

        if cat_id_raw and cat_id_raw.isdigit():
            from app.models.db_models import Category as CategoryModel
            from app.core.posts_db import slugify, _resolve_parent_category
            cat_obj = db.get(CategoryModel, int(cat_id_raw))
            if cat_obj and name:
                cat_obj.name = name
                cat_obj.slug = slugify(name)
                cat_obj.description = description
                if translations_json:
                    cat_obj.translations_json = translations_json
                if parent_ref:
                    p_obj = _resolve_parent_category(db, parent_ref)
                    cat_obj.parent_id = p_obj.id if (p_obj and p_obj.id != cat_obj.id) else None
                else:
                    cat_obj.parent_id = None
                db.commit()
                db.refresh(cat_obj)
                return RedirectResponse(url="/admin/categories", status_code=303)

        if name:
            try:
                create_category(
                    db,
                    name=name,
                    parent_slug=parent_ref or None,
                    description=description,
                    translations_json=translations_json or "{}"
                )
            except ValueError:
                pass
        return RedirectResponse(url="/admin/categories", status_code=303)

    @router.post("/admin/categories/delete")
    @role_required("admin", "editor")
    async def admin_delete_category(request: Request, db: Session = Depends(get_db)):
        form = await request.form()

        def _txt(key: str) -> str:
            v = form.get(key)
            if v is None:
                return ""
            if isinstance(v, str):
                return v.strip()
            if isinstance(v, (bytes, bytearray)):
                return bytes(v).decode("utf-8", errors="replace").strip()
            return ""

        raw = _txt("category_id")
        if raw.isdigit():
            delete_category_by_id(db, int(raw))
        return RedirectResponse(url="/admin/categories", status_code=303)

    @router.get("/admin/settings", response_class=HTMLResponse)
    @router.get("/admin/settings/", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_settings_page(request: Request):
        themes = list_installed_themes()
        cur_theme = get_active_theme()
        active_locales = [loc for loc in get_available_locales() if loc.get("enabled")]
        with SessionLocal() as db:
            app_settings = {row.key: row.value for row in db.query(AppSetting).all() if row and row.key}
            all_posts = db.query(PostModel).filter(PostModel.draft == False).order_by(PostModel.title.asc()).all()
            static_pages = [
                {"id": p.id, "slug": p.slug, "title": p.title}
                for p in all_posts
                if p.slug and (
                    is_static_page_slug(p.slug)
                    or (p.category and p.category.lower() in ("pages", "pagini", "pagină", "page", "static"))
                )
            ]
        localized_site_names = {
            loc["code"]: (app_settings.get(f"SITE_DISPLAY_NAME_{loc['code']}") or "").strip()
            for loc in active_locales
        }
        localized_site_taglines = {
            loc["code"]: (app_settings.get(f"SITE_TAGLINE_{loc['code']}") or "").strip()
            for loc in active_locales
        }
        return render_template(
            templates,
            request=request,
            name="admin/settings.html",
            context={
                "title": "Setări site",
                "settings_site_name": get_site_display_name(),
                "settings_site_tagline": get_site_tagline(),
                "active_locales": active_locales,
                "localized_site_names": localized_site_names,
                "localized_site_taglines": localized_site_taglines,
                "env_public_url": get_public_site_url(),
                "site_favicon_path": get_site_favicon_path(),
                "site_brand_image_path": get_site_brand_image_path(),
                "site_nav_icon_path": get_site_nav_icon_path(),
                "og_card_image_path": get_og_card_image_path(),
                "post_image_crop_og": get_post_image_crop_og(),
                "post_image_max_edge": get_post_image_max_edge(),
                "post_image_output_width": get_post_image_output_width(),
                "post_image_output_height": get_post_image_output_height(),
                "flat_post_urls": get_flat_post_urls(),
                "installed_themes": themes,
                "active_theme_slug": cur_theme,
                "homepage_mode": get_homepage_mode(),
                "static_pages": static_pages,
                "nav_items": _get_static_nav_items_raw(),
            },
        )

    @router.get("/admin/translations", response_class=HTMLResponse)
    @router.get("/admin/translations/", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_translations_page(request: Request):
        from app.core.i18n import (
            DEFAULT_LOCALE,
            get_available_locales,
            list_translation_catalog,
        )
        locales = get_available_locales()
        preferred_locale = next((loc["code"] for loc in locales if loc.get("code") and loc["code"] != DEFAULT_LOCALE), None)
        selected_locale = (request.query_params.get("locale") or "").strip() or preferred_locale or (
            next((loc["code"] for loc in locales if loc.get("is_default")), None) or (locales[0]["code"] if locales else DEFAULT_LOCALE)
        )
        translation_items = list_translation_catalog(selected_locale) if selected_locale else []

        grouped_sections: dict[str, list[dict[str, Any]]] = {}
        def get_section_title(key: str) -> str:
            k = (key or "").strip().lower()
            parts = k.split(".")
            prefix = parts[0]
            
            if prefix == "admin" or k.startswith("admin_"):
                sub = parts[1] if len(parts) >= 2 else ""
                if sub in ("dashboard", "nav") or "dashboard" in k or "nav" in k:
                    return "⚡ Admin Dashboard & Navigation"
                elif sub in ("users", "roles") or "user" in k or "role" in k:
                    return "👥 Admin Users & Roles"
                elif sub == "settings" or "setting" in k:
                    return "⚙️ Admin Site Settings"
                elif sub == "translations" or "translation" in k:
                    return "🌐 Admin Translations"
                elif sub == "themes" or "theme" in k:
                    return "🎨 Admin Themes"
                elif sub == "plugins" or "plugin" in k:
                    return "🔌 Admin Plugins"
                elif sub == "categories" or "category" in k:
                    return "📁 Admin Categories"
                elif sub == "editor" or "editor" in k:
                    return "📝 Admin Post Editor"
                else:
                    return "🛠️ Admin Common & Actions"
            elif prefix == "auth" or "login" in k or "register" in k or "password" in k or "email" in k or "account" in k or k in ("blocked", "error_auth_required"):
                return "🔑 Autentificare & Auth"
            elif prefix == "footer" or "footer" in k:
                return "🦶 Footer Section"
            elif prefix in ("home", "blog") or "post" in k or "article" in k or "comment" in k or "reply" in k or "read" in k or "heading" in k or "excerpt" in k:
                return "🏠 Home Page & Blog"
            elif prefix in ("profile", "user") or "profile" in k or "full_name" in k or "customer" in k:
                return "👤 Profil & Utilizatori"
            elif prefix == "hosting" or "domain" in k or "spv" in k:
                return "🌐 Hosting & Cloud"
            elif prefix == "devstudio" or "workspace" in k:
                return "💻 DevStudio IDE"
            elif prefix in ("ui", "nav") or "btn" in k or "badge" in k or "cancel" in k or "copy" in k or "placeholder" in k or "success" in k or "error" in k or "back" in k or "tab" in k or "site" in k or "share" in k:
                return "💻 UI & Interfață"
            elif prefix == "newsletter" or "subscribe" in k:
                return "📧 Newsletter"
            elif prefix in ("shop", "product", "order", "delivery") or "payment" in k or "card_" in k or "col_" in k or "price" in k or "discount" in k or "paid" in k or "cash" in k or "download" in k or "buy" in k:
                return "🛒 Magazin & Comenzi (Shop)"
            elif prefix in ("stats", "analytics") or "view" in k or "total_" in k or "rank" in k or "ref_" in k or "monitored" in k or "pct" in k:
                return "📊 Analitice & Statistici"
            elif "ai_" in k or "gemini" in k or "qwen" in k:
                return "🤖 AI & Automatizări"
            else:
                return "🌐 Diverse Traduceri (General)"

        for item in translation_items:
            sec = get_section_title(item.get("key", ""))
            if sec not in grouped_sections:
                grouped_sections[sec] = []
            grouped_sections[sec].append(item)

        return render_template(
            templates,
            request=request,
            name="admin/translations.html",
            context={
                "title": "Traduceri",
                "locales": locales,
                "selected_locale": selected_locale,
                "translation_items": translation_items,
                "grouped_sections": grouped_sections,
                "default_locale": DEFAULT_LOCALE,
            },
        )

    @router.post("/admin/translations/set-default")
    @role_required("admin")
    async def admin_set_default_locale(request: Request, locale_code: str = Form(...)):
        from app.core.i18n import set_default_locale
        set_default_locale(locale_code)
        return RedirectResponse(url=f"/admin/translations?locale={locale_code}&msg=Limba+implicită+a+fost+schimbată!", status_code=303)

    @router.post("/admin/translations/add-locale")
    @role_required("admin")
    async def admin_add_locale(request: Request):
        from app.core.i18n import add_locale
        form = await request.form()

        def _txt(key: str) -> str:
            v = form.get(key)
            if v is None:
                return ""
            if isinstance(v, str):
                return v.strip()
            if isinstance(v, (bytes, bytearray)):
                return bytes(v).decode("utf-8", errors="replace").strip()
            return ""

        locale_code = _txt("locale_code").strip().lower()
        locale_name = _txt("locale_name") or locale_code.upper()
        if locale_code:
            add_locale(locale_code, locale_name)
        return RedirectResponse(url="/admin/translations?locale=" + locale_code, status_code=303)

    @router.post("/admin/translations/delete-locale")
    @role_required("admin")
    async def admin_delete_locale(request: Request):
        from app.core.i18n import delete_locale
        form = await request.form()
        locale_code = str(form.get("locale_code") or "").strip().lower()
        if locale_code:
            delete_locale(locale_code)
        return RedirectResponse(url="/admin/translations", status_code=303)

    @router.post("/admin/translations/save")
    @role_required("admin")
    async def admin_save_translation(request: Request):
        from app.core.i18n import save_translation_values
        form = await request.form()

        def _txt(key: str) -> str:
            v = form.get(key)
            if v is None:
                return ""
            if isinstance(v, str):
                return v.strip()
            if isinstance(v, (bytes, bytearray)):
                return bytes(v).decode("utf-8", errors="replace").strip()
            return ""

        locale_code = _txt("locale_code").strip().lower()
        values: dict[str, str] = {}
        for name in form.keys():
            if name.startswith("translation_value__"):
                key = name[len("translation_value__") :].strip()
                if key:
                    values[key] = _txt(name)
        if locale_code and not values:
            key = _txt("translation_key")
            value = _txt("translation_value")
            if key:
                values[key] = value
        if locale_code and values:
            save_translation_values(locale_code, values)
        return RedirectResponse(url=f"/admin/translations?locale={locale_code}", status_code=303)

    @router.get("/admin/translations/delete")
    @role_required("admin")
    async def admin_delete_translation(request: Request):
        from app.core.i18n import delete_translation_entry
        locale_code = (request.query_params.get("locale") or "").strip()
        key = (request.query_params.get("key") or "").strip()
        if locale_code and key:
            delete_translation_entry(locale_code, key)
        return RedirectResponse(url=f"/admin/translations?locale={locale_code}", status_code=303)

    @router.get("/admin/themes", response_class=HTMLResponse)
    @router.get("/admin/themes/", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_themes_page(request: Request):
        themes = list_installed_themes()
        cur_theme = get_active_theme()
        return render_template(
            templates,
            request=request,
            name="admin/themes.html",
            context={
                "title": "Teme",
                "installed_themes": themes,
                "active_theme_slug": cur_theme,
                "error": "",
                "message": "",
            },
        )

    def _safe_theme_slug(raw: str) -> str | None:
        s = (raw or "").strip().lower()
        if not s or s in _THEME_SLUG_RESERVED:
            return None
        if any(ch not in _THEME_SLUG_OK for ch in s):
            return None
        return s

    def _zip_members(zipf: ZipFile) -> list[str]:
        return [n for n in zipf.namelist() if n and not n.endswith("/")]

    def _extract_theme_zip(data: bytes, *, overwrite: bool) -> tuple[str, str]:
        """
        Instalează o temă din zip. Returnează (slug, message).
        Așteaptă o structură de forma:
        - themes/<slug>/... (obligatoriu, cel puțin theme.json sau templates/)
        - static/themes/<slug>/... (opțional, ex. theme.css)
        """
        with tempfile.TemporaryDirectory(prefix="theme-upload-") as tmp:
            zpath = pathlib.Path(tmp) / "theme.zip"
            zpath.write_bytes(data)
            with ZipFile(zpath) as zipf:
                members = _zip_members(zipf)
                # Detect slug + layout variants.
                # Accepted zips:
                # 1) themes/<slug>/... + optional static/themes/<slug>/...
                # 2) <slug>/... (one theme folder at zip root)
                slug = None
                mode: str = "themes_root"  # or "slug_root"

                # Prefer explicit manifest path: themes/<slug>/theme.json
                if not slug:
                    for n in members:
                        if n.startswith("themes/") and n.endswith("/theme.json"):
                            parts = n.split("/", 3)
                            if len(parts) >= 3 and parts[1]:
                                cand = _safe_theme_slug(parts[1])
                                if cand:
                                    slug = cand
                                    mode = "themes_root"
                                    break

                # Fallback: any themes/<slug>/... path
                if not slug:
                    for n in members:
                        if n.startswith("themes/"):
                            parts = n.split("/", 2)
                            if len(parts) >= 2 and parts[1]:
                                cand = _safe_theme_slug(parts[1])
                                if cand:
                                    slug = cand
                                    mode = "themes_root"
                                    break

                if not slug:
                    # Try detect a theme folder at zip root: <slug>/theme.json or <slug>/templates/...
                    # Ignore common noise folders created by archivers.
                    ignore = {"__macosx", ".ds_store"}
                    top_levels = set()
                    for n in members:
                        if "/" in n:
                            top = n.split("/", 1)[0].strip()
                            if top and top.lower() not in ignore:
                                top_levels.add(top)

                    candidates = []
                    for top in sorted(top_levels):
                        cand = _safe_theme_slug(top)
                        if not cand:
                            continue
                        has_templates = any(
                            m.startswith(f"{top}/templates/") for m in members
                        )
                        has_manifest = any(m == f"{top}/theme.json" for m in members)
                        if has_templates or has_manifest:
                            candidates.append(cand)

                    if len(candidates) == 1:
                        slug = candidates[0]
                        mode = "slug_root"
                    elif len(candidates) > 1:
                        raise ValueError(
                            "Zip invalid: găsesc mai multe teme la rădăcină. "
                            f"Alege un singur folder temă: {', '.join(candidates[:8])}"
                        )

                if not slug:
                    if "theme.json" in members:
                        try:
                            tj_data = json.loads(zipf.read("theme.json").decode("utf-8"))
                            cand = _safe_theme_slug(tj_data.get("id") or tj_data.get("slug") or tj_data.get("name") or "")
                            if cand:
                                slug = cand
                                mode = "flat_root"
                        except Exception:
                            pass

                if not slug:
                    sample = ", ".join(members[:8]) if members else "(gol)"
                    raise ValueError(
                        "Zip invalid: aștept `themes/<slug>/...` sau `<slug>/...` (un singur folder la rădăcină cu numele temei). "
                        f"Exemple intrări: {sample}"
                    )

                # Secure extraction (prevent zip slip)
                extract_root = pathlib.Path(tmp) / "extract"
                extract_root.mkdir(parents=True, exist_ok=True)
                for n in members:
                    if ".." in n or n.startswith("/") or n.startswith("\\"):
                        raise ValueError("Zip invalid (path traversal).")
                    # Only allow themes/ and static/themes/
                    if mode == "themes_root":
                        # Normal:
                        # - themes/<slug>/...
                        # - static/themes/<slug>/...
                        if n.startswith(f"themes/{slug}/") or n.startswith(
                            f"static/themes/{slug}/"
                        ):
                            dest = extract_root / n
                        else:
                            continue
                    elif mode == "flat_root":
                        if n == "theme.json":
                            dest = extract_root / "themes" / slug / "theme.json"
                        elif n.startswith("templates/"):
                            dest = extract_root / "themes" / slug / n
                        elif n == "theme.css":
                            dest = extract_root / "static" / "themes" / slug / "theme.css"
                        elif n.startswith("static/"):
                            dest = extract_root / "static" / "themes" / slug / n[len("static/"):]
                        else:
                            continue
                    else:
                        # slug_root: accept a single theme folder:
                        # - <slug>/theme.json              -> themes/<slug>/theme.json
                        # - <slug>/templates/...           -> themes/<slug>/templates/...
                        # - <slug>/theme.css               -> static/themes/<slug>/theme.css
                        # - <slug>/static/themes/<slug>/.. -> static/themes/<slug>/...
                        if n.startswith(f"{slug}/"):
                            rel = n[len(slug) + 1 :]
                            if rel == "theme.json":
                                dest = extract_root / "themes" / slug / "theme.json"
                            elif rel.startswith("templates/"):
                                dest = extract_root / "themes" / slug / rel
                            elif rel == "theme.css":
                                dest = (
                                    extract_root
                                    / "static"
                                    / "themes"
                                    / slug
                                    / "theme.css"
                                )
                            elif rel.startswith(f"static/themes/{slug}/"):
                                dest = extract_root / rel
                            else:
                                continue
                        else:
                            continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zipf.open(n) as src:
                        content_bytes = src.read()
                        if n.endswith(".html"):
                            try:
                                text = content_bytes.decode("utf-8")
                                text = text.replace(chr(92) + chr(39), chr(39)).replace(chr(92) + chr(34), chr(34))
                                content_bytes = text.encode("utf-8")
                            except Exception:
                                pass
                        with open(dest, "wb") as out:
                            out.write(content_bytes)

            theme_src = extract_root / "themes" / slug
            if not theme_src.is_dir():
                raise ValueError("Lipsește directorul `themes/<slug>/` din zip.")

            # Validate: must contain theme.json OR templates/
            def _is_theme_root(p: pathlib.Path) -> bool:
                return (p / "theme.json").is_file() or (p / "templates").is_dir()

            # Handle common nesting mistakes:
            # - themes/<slug>/<slug>/...
            # - themes/<slug>/themes/<slug>/...
            if not _is_theme_root(theme_src):
                nested1 = theme_src / slug
                nested2 = theme_src / "themes" / slug
                if nested1.is_dir() and _is_theme_root(nested1):
                    theme_src = nested1
                elif nested2.is_dir() and _is_theme_root(nested2):
                    theme_src = nested2
                else:
                    # If there's exactly one directory, try it (best effort).
                    subdirs = [p for p in theme_src.iterdir() if p.is_dir()]
                    if len(subdirs) == 1 and _is_theme_root(subdirs[0]):
                        theme_src = subdirs[0]

            has_manifest = (theme_src / "theme.json").is_file()
            has_templates = (theme_src / "templates").is_dir()
            if not (has_manifest or has_templates):
                # Try to help debugging by listing entries.
                entries = []
                try:
                    entries = sorted([p.name for p in theme_src.iterdir()])[:12]
                except Exception:
                    entries = []
                hint = f"Conținut găsit în themes/{slug}/: {', '.join(entries) if entries else '(nimic)'}"
                raise ValueError(
                    "Tema trebuie să conțină `themes/<slug>/theme.json` și/sau `themes/<slug>/templates/`. "
                    + hint
                )

            theme_dest = APP_DIR / "themes" / slug
            static_src = extract_root / "static" / "themes" / slug
            static_dest = APP_DIR / "static" / "themes" / slug

            if theme_dest.exists() or static_dest.exists():
                if not overwrite:
                    raise ValueError("Tema există deja. Bifează „Suprascrie” ca să o reinstalezi.")
                if theme_dest.is_dir():
                    shutil.rmtree(theme_dest)
                if static_dest.is_dir():
                    shutil.rmtree(static_dest)

            theme_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(theme_src, theme_dest)
            static_dest.parent.mkdir(parents=True, exist_ok=True)
            static_dest.mkdir(parents=True, exist_ok=True)
            if static_src.is_dir():
                shutil.copytree(static_src, static_dest, dirs_exist_ok=True)
            theme_css = static_dest / "theme.css"
            if not theme_css.exists():
                theme_css.write_text("/* Theme CSS */", encoding="utf-8")

            for folder_name in ("static", "assets", "images", "css", "js", "fonts"):
                src_folder = theme_dest / folder_name
                if src_folder.is_dir():
                    if folder_name == "static":
                        for item in src_folder.iterdir():
                            dst = static_dest / item.name
                            if item.is_dir():
                                shutil.copytree(item, dst, dirs_exist_ok=True)
                            else:
                                shutil.copy2(item, dst)
                    else:
                        target_sub = static_dest / folder_name
                        shutil.copytree(src_folder, target_sub, dirs_exist_ok=True)

            return slug, f"Tema `{slug}` a fost instalată."

    @router.post("/admin/themes/upload", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_themes_upload(
        request: Request,
        file: UploadFile = File(...),
        overwrite: str | None = Form(default=None),
    ):
        raw = await file.read()
        themes = list_installed_themes()
        cur_theme = get_active_theme()
        if not raw:
            return render_template(
                templates,
                request=request,
                name="admin/themes.html",
                context={
                    "title": "Teme",
                    "installed_themes": themes,
                    "active_theme_slug": cur_theme,
                    "error": "Fișier gol.",
                    "message": "",
                },
                status_code=400,
            )
        try:
            slug, msg = _extract_theme_zip(raw, overwrite=overwrite == "1")
            themes = list_installed_themes()
            return render_template(
                templates,
                request=request,
                name="admin/themes.html",
                context={
                    "title": "Teme",
                    "installed_themes": themes,
                    "active_theme_slug": cur_theme,
                    "error": "",
                    "message": msg,
                },
            )
        except Exception as e:
            return render_template(
                templates,
                request=request,
                name="admin/themes.html",
                context={
                    "title": "Teme",
                    "installed_themes": themes,
                    "active_theme_slug": cur_theme,
                    "error": f"Eroare: {str(e)}",
                    "message": "",
                },
                status_code=400,
            )

    @router.post("/admin/themes/activate", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_themes_activate(request: Request, slug: str = Form(...)):
        s = _safe_theme_slug(slug)
        cur_theme = get_active_theme()
        if s and s != cur_theme:
            set_active_theme(s)
        themes = list_installed_themes()
        cur_theme = get_active_theme()
        return render_template(
            templates,
            request=request,
            name="admin/themes.html",
            context={
                "title": "Teme",
                "installed_themes": themes,
                "active_theme_slug": cur_theme,
                "error": "",
                "message": f"Tema '{slug}' a fost activată cu succes!",
            },
        )

    @router.post("/admin/themes/delete", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_themes_delete(request: Request, slug: str = Form(...)):
        s = _safe_theme_slug(slug)
        themes = list_installed_themes()
        cur_theme = get_active_theme()
        if not s:
            return render_template(
                templates,
                request=request,
                name="admin/themes.html",
                context={
                    "title": "Teme",
                    "installed_themes": themes,
                    "active_theme_slug": cur_theme,
                    "error": "Slug invalid.",
                    "message": "",
                },
                status_code=400,
            )

        if s == cur_theme:
            return render_template(
                templates,
                request=request,
                name="admin/themes.html",
                context={
                    "title": "Teme",
                    "installed_themes": themes,
                    "active_theme_slug": cur_theme,
                    "error": "Nu poți șterge tema activă în folosință!",
                    "message": "",
                },
                status_code=400,
            )

        theme_dir = APP_DIR / "themes" / s
        static_dir = APP_DIR / "static" / "themes" / s
        try:
            if theme_dir.is_dir():
                shutil.rmtree(theme_dir)
            if static_dir.is_dir():
                shutil.rmtree(static_dir)
        except Exception as e:
            themes = list_installed_themes()
            return render_template(
                templates,
                request=request,
                name="admin/themes.html",
                context={
                    "title": "Teme",
                    "installed_themes": themes,
                    "active_theme_slug": cur_theme,
                    "error": f"Eroare la ștergere: {str(e)}",
                    "message": "",
                },
                status_code=500,
            )

        # Dacă tema ștearsă era activă, revenim la default în setări.
        if cur_theme == s:
            write_settings({"ACTIVE_THEME": None})
            cur_theme = get_active_theme()

        themes = list_installed_themes()
        return render_template(
            templates,
            request=request,
            name="admin/themes.html",
            context={
                "title": "Teme",
                "installed_themes": themes,
                "active_theme_slug": cur_theme,
                "error": "",
                "message": f"Tema `{s}` a fost ștearsă.",
            },
        )

    def _plugins_page_ctx(
        installed_plugins,
        *,
        error: str = "",
        message: str = "",
    ) -> dict:
        # Obținem plugin-urile din baza de date cu status și setări
        from app.core.plugin_manager import get_installed_plugins, get_plugin_settings
        db_plugins = {p.id: p for p in get_installed_plugins()}
        
        return {
            "title": "Plugin-uri",
            "installed_plugins": installed_plugins,
            "db_plugins": db_plugins,
            "error": error,
            "message": message,
            "container_restart_enabled": ADMIN_ENABLE_CONTAINER_RESTART,
        }

    
    @router.get("/admin/repo", response_class=HTMLResponse)
    @router.get("/admin/repo/", response_class=HTMLResponse)
    @router.get("/admin/repo/store", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_repo_store_page(request: Request, message: str | None = None, error: str | None = None):
        from app.core.config import get_repo_api_url, VLAH_CORE_VERSION
        from app.core.plugin_package import list_installed_plugins
        from app.core.themes import list_installed_themes
        import urllib.request
        import json

        catalog = {"plugins": [], "themes": [], "online": False}
        repo_url = get_repo_api_url()
        try:
            req = urllib.request.Request(
                repo_url,
                headers={
                    "User-Agent": f"VlahX-Core/{VLAH_CORE_VERSION}",
                    "X-VlahX-Version": VLAH_CORE_VERSION,
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw_data = resp.read().decode("utf-8")
                catalog_data = json.loads(raw_data)
                catalog["plugins"] = catalog_data.get("plugins", [])
                catalog["themes"] = catalog_data.get("themes", [])
                catalog["version"] = catalog_data.get("version", "1.0.0")
                catalog["online"] = True
        except Exception as e:
            logger.warning(f"Failed to fetch repo catalog from {repo_url}: {e}")

        installed_p_ids = {p.id for p in list_installed_plugins()}
        installed_t_slugs = {t.slug for t in list_installed_themes()}

        msg = message or request.query_params.get("message")
        err = error or request.query_params.get("error")

        return render_template(
            templates,
            request=request,
            name="admin/repo_store.html",
            context={
                "title": "Magazin Repository (repo.vlahx.org)",
                "catalog": catalog,
                "installed_p_ids": installed_p_ids,
                "installed_t_slugs": installed_t_slugs,
                "repo_url": repo_url,
                "core_version": VLAH_CORE_VERSION,
                "message": msg,
                "error": err,
            },
        )

    @router.get("/admin/plugins", response_class=HTMLResponse)
    @router.get("/admin/plugins/", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_plugins_page(request: Request):
        plugins = list_installed_plugins()
        return render_template(
            templates,
            request=request,
            name="admin/plugins.html",
            context=_plugins_page_ctx(plugins),
        )

    @router.post("/admin/plugins/upload", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_plugins_upload(
        request: Request,
        file: UploadFile = File(...),
        overwrite: str | None = Form(default=None),
    ):
        raw = await file.read()
        if not raw:
            return render_template(
                templates,
                request=request,
                name="admin/plugins.html",
                context=_plugins_page_ctx(
                    list_installed_plugins(),
                    error="Fișier gol.",
                ),
                status_code=400,
            )
        try:
            _pid, msg = extract_plugin_zip(raw, overwrite=overwrite == "1")
            plugins = list_installed_plugins()
            return render_template(
                templates,
                request=request,
                name="admin/plugins.html",
                context=_plugins_page_ctx(plugins, message=msg),
            )
        except Exception as e:
            return render_template(
                templates,
                request=request,
                name="admin/plugins.html",
                context=_plugins_page_ctx(
                    list_installed_plugins(),
                    error=f"Eroare: {str(e)}",
                ),
                status_code=400,
            )

    @router.post("/admin/plugins/repo/install", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_plugins_repo_install(request: Request, download_url: str = Form(...), plugin_id: str = Form(...)):
        from app.core.plugin_package import extract_plugin_zip
        from app.core.plugin_manager import set_plugin_enabled
        from app.core.config import get_repo_api_url
        import urllib.request
        import urllib.parse

        try:
            if download_url.startswith("/"):
                repo_catalog_url = get_repo_api_url()
                parsed = urllib.parse.urlparse(repo_catalog_url)
                pub_origin = f"{parsed.scheme}://{parsed.netloc}"
                
                urls_to_try = [f"{pub_origin}{download_url}"]
                if "vlahx.org" in parsed.netloc:
                    urls_to_try.append(f"http://vlahx-repo:8080{download_url}")

                data = None
                last_err = None
                for u in urls_to_try:
                    try:
                        req = urllib.request.Request(u, headers={"User-Agent": "VlahX-Core-2.0"})
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            if resp.status == 200:
                                read_bytes = resp.read()
                                if read_bytes and len(read_bytes) > 100:
                                    data = read_bytes
                                    break
                    except Exception as e_dl:
                        last_err = e_dl

                if not data:
                    raise ValueError(f"Imposibil de descărcat pachetul din Repo Store ({last_err}). Verificați conexiunea.")

            plugin_id, msg = extract_plugin_zip(data, overwrite=True)
            set_plugin_enabled(plugin_id, True)
            safe_msg = urllib.parse.quote(f"Pluginul  a fost instalat și activat cu succes!")
            return RedirectResponse(url=f"/admin/repo?message={safe_msg}", status_code=303)
        except Exception as e:
            logger.exception("Plugin repo install failed")
            safe_err = urllib.parse.quote(f"Eroare instalare plugin: {e}")
            return RedirectResponse(url=f"/admin/repo?error={safe_err}", status_code=303)

    @router.post("/admin/themes/repo/install", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_themes_repo_install(request: Request, download_url: str = Form(...)):
        from app.core.config import get_repo_api_url
        import urllib.request
        import urllib.parse

        try:
            if download_url.startswith("/"):
                repo_catalog_url = get_repo_api_url()
                parsed = urllib.parse.urlparse(repo_catalog_url)
                pub_origin = f"{parsed.scheme}://{parsed.netloc}"
                
                urls_to_try = [f"{pub_origin}{download_url}"]
                if "vlahx.org" in parsed.netloc:
                    urls_to_try.append(f"http://vlahx-repo:8080{download_url}")

                data = None
                last_err = None
                for u in urls_to_try:
                    try:
                        req = urllib.request.Request(u, headers={"User-Agent": "VlahX-Core-2.0"})
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            if resp.status == 200:
                                read_bytes = resp.read()
                                if read_bytes and len(read_bytes) > 100:
                                    data = read_bytes
                                    break
                    except Exception as e_dl:
                        last_err = e_dl

                if not data:
                    raise ValueError(f"Imposibil de descărcat pachetul din Repo Store ({last_err}). Verificați conexiunea.")

            slug, msg = _extract_theme_zip(data, overwrite=True)
            safe_msg = urllib.parse.quote(f"Tema  a fost instalată cu succes!")
            return RedirectResponse(url=f"/admin/repo?message={safe_msg}", status_code=303)
        except Exception as e:
            logger.exception("Theme repo install failed")
            safe_err = urllib.parse.quote(f"Eroare instalare temă: {e}")
            return RedirectResponse(url=f"/admin/repo?error={safe_err}", status_code=303)

    @router.post("/admin/repo/delete", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_repo_delete_package(request: Request, package_id: str = Form(...), pkg_type: str = Form(...)):
        import urllib.parse
        import urllib.request
        from app.core.config import get_repo_api_url

        pkg_id = package_id.strip()

        try:
            repo_catalog_url = get_repo_api_url()
            parsed = urllib.parse.urlparse(repo_catalog_url)
            delete_url = f"{parsed.scheme}://{parsed.netloc}/api/v1/delete?package_id={pkg_id}&pkg_type={pkg_type}"
            
            req = urllib.request.Request(delete_url, method="POST", headers={"User-Agent": "VlahX-Core-2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                pass

            safe_msg = urllib.parse.quote(f"Pachetul '{pkg_id}' a fost eliminat cu succes din Repo Store!")
            return RedirectResponse(url=f"/admin/repo?message={safe_msg}", status_code=303)
        except Exception as e:
            logger.exception("Failed to delete package from repo store")
            safe_err = urllib.parse.quote(f"Eroare la ștergerea pachetului {pkg_id}: {e}")
            return RedirectResponse(url=f"/admin/repo?error={safe_err}", status_code=303)

    @router.post("/admin/plugins/delete", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_plugins_delete(request: Request, slug: str = Form(...)):
        s = safe_plugin_id(slug)
        if not s:
            return render_template(
                templates,
                request=request,
                name="admin/plugins.html",
                context=_plugins_page_ctx(
                    list_installed_plugins(),
                    error="ID plugin invalid.",
                ),
                status_code=400,
            )
        dest = APP_DIR / "plugins" / s
        try:
            if dest.is_dir():
                shutil.rmtree(dest)
            # Ștergem și din baza de date (inclusiv setările)
            from app.core.plugin_manager import unregister_plugin_from_db
            unregister_plugin_from_db(s)
        except Exception as e:
            return render_template(
                templates,
                request=request,
                name="admin/plugins.html",
                context=_plugins_page_ctx(
                    list_installed_plugins(),
                    error=f"Eroare la ștergere: {str(e)}",
                ),
                status_code=500,
            )
        plugins = list_installed_plugins()
        extra = (
            f"Plugin `{s}` și toate setările sale au fost șterse. Apoi „Repornește containerul” sau restart manual."
            if ADMIN_ENABLE_CONTAINER_RESTART
            else f"Plugin `{s}` și toate setările sale au fost șterse. Repornește aplicația ca schimbarea să fie completă."
        )
        return render_template(
            templates,
            request=request,
            name="admin/plugins.html",
            context=_plugins_page_ctx(plugins, message=extra),
        )

    @router.post("/admin/app/restart", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_app_restart(
        request: Request,
        background_tasks: BackgroundTasks,
    ):
        if not ADMIN_ENABLE_CONTAINER_RESTART:
            return render_template(
                templates,
                request=request,
                name="admin/plugins.html",
                context=_plugins_page_ctx(
                    list_installed_plugins(),
                    error="Restart din Admin nu e activat. Setează ADMIN_ENABLE_CONTAINER_RESTART=true în .env și repornește manual containerul o dată ca să ia variabila.",
                ),
                status_code=403,
            )
        background_tasks.add_task(sigterm_self_after_delay, 0.35)
        return render_template(
            templates,
            request=request,
            name="admin/plugins.html",
            context=_plugins_page_ctx(
                list_installed_plugins(),
                message="Se trimite oprirea procesului; cu Docker (restart: unless-stopped) containerul ar trebui să revină în câteva secunde. Reîncarcă apoi această pagină.",
            ),
        )

    @router.post("/admin/settings/save")
    @role_required("admin")
    async def admin_save_settings(request: Request):
        try:
            form = await request.form()

            def _txt(key: str) -> str:
                v = form.get(key)
                if v is None:
                    return ""
                if isinstance(v, str):
                    return v.strip()
                if isinstance(v, (bytes, bytearray)):
                    return bytes(v).decode("utf-8", errors="replace").strip()
                return ""

            def _opt_int(key: str) -> int | None:
                s = _txt(key)
                if not s:
                    return None
                try:
                    n = int(s)
                    return n if n > 0 else None
                except ValueError:
                    return None

            def _save_app_setting(key: str, value: str | None) -> None:
                with SessionLocal() as db:
                    row = db.get(AppSetting, key)
                    if value is None or str(value).strip() == "":
                        if row is not None:
                            db.delete(row)
                    else:
                        if row is None:
                            db.add(AppSetting(key=key, value=str(value).strip()))
                        else:
                            row.value = str(value).strip()
                    db.commit()

            _save_app_setting("SITE_DISPLAY_NAME", _txt("site_display_name") or None)
            _save_app_setting("SITE_TAGLINE", _txt("site_tagline") or None)
            _save_app_setting("HOMEPAGE_MODE", _txt("homepage_mode") or "blog")

            for loc in get_available_locales():
                code = loc.get("code")
                if code:
                    _save_app_setting(f"SITE_DISPLAY_NAME_{code}", _txt(f"site_display_name_{code}") or None)
                    _save_app_setting(f"SITE_TAGLINE_{code}", _txt(f"site_tagline_{code}") or None)

            active_locales = [loc for loc in get_available_locales() if loc.get("enabled")]
            nav_urls = form.getlist("nav_url")
            nav_targets = form.getlist("nav_target")
            nav_locations = form.getlist("nav_location")
            legacy_labels = form.getlist("nav_label")

            new_nav_links = []
            for i in range(len(nav_urls)):
                u = str(nav_urls[i] if i < len(nav_urls) else "").strip()
                tgt = str(nav_targets[i] if i < len(nav_targets) else "_self").strip()
                loc = str(nav_locations[i] if i < len(nav_locations) else "navbar").strip().lower()
                if loc not in ("navbar", "footer", "both"):
                    loc = "navbar"

                labels_dict = {}
                for loc_obj in active_locales:
                    code = loc_obj["code"]
                    list_vals = form.getlist(f"nav_label_{code}")
                    val = str(list_vals[i] if i < len(list_vals) else "").strip()
                    if val:
                        labels_dict[code] = val

                fallback_lbl = ""
                if i < len(legacy_labels):
                    fallback_lbl = str(legacy_labels[i] or "").strip()

                from app.core.i18n import DEFAULT_LOCALE
                primary_lbl = (
                    labels_dict.get("ro")
                    or labels_dict.get(DEFAULT_LOCALE)
                    or (next(iter(labels_dict.values())) if labels_dict else fallback_lbl)
                    or fallback_lbl
                ).strip()

                if not primary_lbl and not u and not labels_dict:
                    continue

                slug = ""
                if u and not u.startswith("/") and not u.startswith("http://") and not u.startswith("https://") and not u.startswith("#"):
                    slug = u
                    u = f"/{u}"
                elif u.startswith("/"):
                    pot_slug = u.strip("/")
                    if "/" not in pot_slug:
                        slug = pot_slug

                new_nav_links.append({
                    "label": primary_lbl,
                    "fixed_label": primary_lbl,
                    "labels": labels_dict,
                    "url": u,
                    "slug": slug,
                    "target": tgt if tgt in ("_self", "_blank") else "_self",
                    "location": loc,
                })

            _save_app_setting("STATIC_NAV_LINKS", json.dumps(new_nav_links, ensure_ascii=False))
            from app.core.config import invalidate_nav_fixed_post_links_cache
            invalidate_nav_fixed_post_links_cache()

            write_settings(
                {
                    "FLAT_POST_URLS": _txt("flat_post_urls") == "1",
                    "ACTIVE_THEME": _txt("active_theme") or None,
                    "POST_IMAGE_MAX_EDGE": _opt_int("post_image_max_edge"),
                    "POST_IMAGE_OUTPUT_WIDTH": _opt_int("post_image_output_width"),
                    "POST_IMAGE_OUTPUT_HEIGHT": _opt_int("post_image_output_height"),
                    "POST_IMAGE_CROP_OG": _txt("post_image_crop_og") == "1",
                }
            )
            return RedirectResponse(url="/admin/settings?msg=Set%C4%83rile+au+fost+salvate+cu+succes%21", status_code=303)
        except Exception as e:
            logger.error("Error saving admin settings: %s", e, exc_info=True)
            return RedirectResponse(url="/admin/settings?err=A+intervenit+o+eroare+la+salvarea+set%C4%83rilor.", status_code=303)

    @router.post("/admin/settings/upload-image")
    @role_required("admin")
    async def admin_settings_upload_image(
        request: Request,
        setting_key: str = Form(...),
        file: UploadFile = File(...),
    ):
        if setting_key not in _IMAGE_SETTING_KEYS:
            return RedirectResponse(url="/admin/settings", status_code=303)
        raw = await file.read()
        if not raw:
            return RedirectResponse(url="/admin/settings", status_code=303)
        orig = (file.filename or "upload").strip()
        ext = pathlib.Path(orig).suffix.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        if ext not in _SITE_IMAGE_EXTS:
            return RedirectResponse(url="/admin/settings", status_code=303)
        dest_dir = APP_DIR / "static" / "images" / "site_uploads"
        dest_dir.mkdir(parents=True, exist_ok=True)

        if ext in (".png", ".jpg", ".jpeg", ".webp") and setting_key in ("OG_CARD_IMAGE_PATH", "SITE_BRAND_IMAGE_PATH", "SITE_NAV_ICON_PATH"):
            from app.routers.media import crop_and_resize_image, process_and_optimize_image
            temp_dest = dest_dir / f"{uuid4().hex}{ext}"
            temp_dest.write_bytes(raw)
            if setting_key == "OG_CARD_IMAGE_PATH":
                final_dest = crop_and_resize_image(temp_dest, target_w=1200, target_h=630, quality=85)
            else:
                final_dest = process_and_optimize_image(temp_dest, max_dimension=1200, quality=85)
            name = final_dest.name
        else:
            name = f"{uuid4().hex}{ext}"
            dest = dest_dir / name
            dest.write_bytes(raw)

        rel = f"/static/images/site_uploads/{name}"
        prev = read_settings().get(setting_key)
        write_settings({setting_key: rel})
        if isinstance(prev, str) and prev.strip() and prev.strip() != rel:
            unlink_site_upload_file(prev.strip())
        return RedirectResponse(url="/admin/settings", status_code=303)

    @router.post("/admin/settings/clear-image")
    @router.post("/admin/settings/clear-image/")
    @role_required("admin")
    async def admin_settings_clear_image(request: Request):
        form = await request.form()
        raw = form.get("setting_key")
        if raw is None:
            logger.warning("clear-image: missing setting_key")
            return RedirectResponse(url="/admin/settings", status_code=303)
        setting_key = (
            raw.decode("utf-8", errors="replace").strip()
            if isinstance(raw, (bytes, bytearray))
            else str(raw).strip()
        )
        if setting_key not in _IMAGE_SETTING_KEYS:
            logger.warning("clear-image: invalid setting_key=%r", setting_key)
            return RedirectResponse(url="/admin/settings", status_code=303)
        stored = read_settings().get(setting_key)
        if isinstance(stored, str) and stored.strip():
            unlink_site_upload_file(stored.strip())
        write_settings({setting_key: None})
        logger.info("clear-image: cleared %s", setting_key)
        return RedirectResponse(url="/admin/settings", status_code=303)

    @router.post("/admin/upload-image")
    @role_required("admin", "editor", "author")
    async def admin_upload_image(request: Request, file: UploadFile = File(...)):
        try:
            base = APP_DIR / "static" / "images" / "post_images"
            base.mkdir(parents=True, exist_ok=True)

            original = (file.filename or "upload").strip()
            ext = pathlib.Path(original).suffix.lower()
            if not ext.startswith("."):
                ext = f".{ext}"
            allowed = {".png", ".jpg", ".jpeg", ".gif"}
            if ext not in allowed:
                return JSONResponse(
                    {"error": "Acceptăm doar JPEG, PNG sau GIF animat (fără WebP)."},
                    status_code=415,
                )

            data = await file.read()
            data, out_ext = process_post_upload(data, ext)
            name = f"{uuid4().hex}{out_ext}"
            dest = base / name
            dest.write_bytes(data)

            return JSONResponse({"location": f"/static/images/post_images/{name}"})
        except Exception as e:
            logger.exception("Error uploading image")
            return JSONResponse(
                {"error": f"Eroare la upload: {str(e)}"},
                status_code=500,
            )

    @router.get("/admin/post/{slug}/delete")
    @role_required("admin")
    async def delete_my_post(
        request: Request, slug: str, db: Session = Depends(get_db)
    ):
        success = delete_post(db, slug)
        if success:
            cur_links = read_settings().get("STATIC_NAV_LINKS") or []
            if isinstance(cur_links, list):
                filtered = [
                    item for item in cur_links
                    if isinstance(item, dict) and str(item.get("slug") or "").strip() != slug
                ]
                if filtered:
                    write_settings({"STATIC_NAV_LINKS": filtered})
                else:
                    write_settings({"STATIC_NAV_LINKS": []})
            else:
                write_settings({"STATIC_NAV_LINKS": []})
            return RedirectResponse(url="/admin", status_code=303)
        return JSONResponse(
            {"error": "Nu am putut șterge postarea!"},
            status_code=404,
        )

    return router