from __future__ import annotations

from typing import Any

from app.models.db_models import TranslationEntry, TranslationLocale
from app.utils.db import SessionLocal, init_db

DEFAULT_LOCALE = "ro"
SUPPORTED_DEFAULT_LOCALES = {"en"}

DEFAULT_TRANSLATION_CATALOG: dict[str, str] = {
    "blog.empty.title": "No posts yet",
    "blog.empty.description": "The first post will appear soon. In the meantime, you can explore available categories.",
    "blog.empty.cta": "Create the first post",
    "blog.notFound.message": "There is no article with this slug:",
    "blog.notFound.backToBlog": "Back to blog",
    "ui.admin": "Admin Panel",
    "ui.profile": "My Profile",
    "ui.new_post": "New Post",
    "ui.logout": "Logout",
    "ui.login": "Login",
    "ui.member": "Member",
    "profile.title": "My Profile",
    "profile.activeAccount": "Active Account",
    "profile.member": "Club Member",
    "profile.memberSince": "Member since",
    "profile.recent": "recent",
    "profile.adminPanel": "⚡ Admin Panel",
    "profile.logout": "Logout",
    "profile.requestRole": "🚀 Request a New Community Role?",
    "profile.requestRoleHelp": "Do you want to write articles as an Author or get elevated permissions? Send a request to administrators.",
    "profile.requestRoleBtn": "✍️ Request New Role",
    "profile.selectRole": "Select Desired Role *",
    "profile.motivation": "Motivation / Message (Optional)",
    "profile.motivationPlaceholder": "Briefly tell us how you would like to contribute...",
    "profile.sendRequest": "📲 Send Request via Telegram to Admins",
    "profile.tabInfo": "👤 Account Details & Profile",
    "profile.editTitle": "✍️ Edit Your Information",
    "profile.updatedSuccess": "Your profile has been updated successfully!",
    "profile.firstName": "First Name / Display Name *",
    "profile.lastName": "Last Name",
    "profile.email": "Email Address",
    "profile.phone": "Phone Number",
    "profile.avatarUrl": "Avatar / Profile Picture (URL)",
    "profile.avatarHelp": "Or use the picture automatically retrieved from",
    "profile.bio": "About me / Bio",
    "profile.bioPlaceholder": "Write a few words about yourself...",
    "profile.saveChanges": "💾 Save Changes",
    "site.title": "Blog",
    "site.tagline": "A simple blog",
    "home.categories.title": "Explore by category",
    "home.categories.all": "All",
    "home.postCard.readMore": "Read story →",
    "home.breadcrumb.home": "Home",
    "home.postPage.backToBlog": "Back to Journal",
    "blog.prevPost": "Previous Article",
    "blog.nextPost": "Next Article",
    "admin.dashboard.title": "Admin Dashboard",
    "admin.dashboard.subtitle": "Manage blog articles, categories, and site settings.",
    "admin.nav.dashboard": "Dashboard",
    "admin.nav.users": "Users",
    "admin.nav.settings": "Settings",
    "admin.nav.translations": "Translations",
    "admin.nav.themes": "Themes",
    "admin.nav.plugins": "Plugins",
    "admin.nav.categories": "Categories",
    "admin.nav.newPost": "New Post",
    "admin.dashboard.existingCategories": "Existing Categories:",
    "admin.dashboard.colImage": "Image",
    "admin.dashboard.colTitleSlug": "Title / Slug",
    "admin.dashboard.colCategory": "Category",
    "admin.dashboard.colStatus": "Status",
    "admin.dashboard.colActions": "Actions",
    "admin.dashboard.noPhoto": "No Photo",
    "admin.status.draft": "Draft",
    "admin.status.public": "Public",
    "admin.actions.viewLive": "View Live",
    "admin.actions.edit": "Edit",
    "admin.actions.delete": "Delete",
    "admin.confirm.deletePost": "Are you sure you want to delete this post?",
    "admin.translations.localeCode": "Locale Code",
    "admin.translations.localeName": "Locale Name",
    "admin.translations.selectLocale": "Select Locale",
    "admin.translations.saveAll": "Save All",
    "media.modal.title": "Media Library",
    "media.modal.libraryTab": "Media Library",
    "media.modal.uploadTab": "Upload New Files",
    "media.modal.searchPlaceholder": "Search by file name...",
    "media.modal.allCategories": "All Categories (Blog, Shop, General)",
    "media.modal.refresh": "Refresh",
    "media.modal.dragAndDrop": "Drag files here or click to upload",
    "media.modal.uploadHint": "You can select multiple images (JPG, PNG, WEBP, GIF, SVG).",
    "media.modal.destinationCategory": "Destination Category",
    "media.modal.selectFromDevice": "Select Images from Device",
    "media.modal.cancel": "Cancel",
    "media.modal.insertSelected": "Insert / Select Image",
    "media.modal.emptyLibrary": "Loading files...",
    "media.modal.noFiles": "No images found in the library.",
    "media.modal.selectHint": "Select an image from the grid to see details.",
    "media.modal.fileUrl": "File URL:",
    "media.modal.deleteBtn": "Delete Permanently",
    "media.modal.uploadDescription": "Add or remove images from the Media Library (processed and optimized automatically with Pillow).",
    "media.modal.openLibrary": "Open Media Library (Add / Upload Images)",
    "admin.users.title": "User & Role Management",
    "admin.users.subtitle": "Manage team members and assign multiple roles per user.",
    "admin.common.backToAdmin": "Back to Admin",
    "admin.common.viewSite": "View Site",
    "admin.users.registeredUsers": "Registered Users on Platform",
    "admin.users.colUser": "User",
    "admin.users.colTelegram": "Telegram Username",
    "admin.users.colCurrentRoles": "Current Roles",
    "admin.users.colAssignRoles": "Assign Multiple Roles",
    "admin.users.colActionsDate": "Actions & Date",
    "admin.roles.admin": "Admin",
    "admin.roles.editor": "Editor",
    "admin.roles.seller": "Seller",
    "admin.roles.author": "Author",
    "admin.roles.reader": "Reader",
    "admin.roles.pending": "Pending",
    "admin.users.checkRoles": "Check Roles:",
    "admin.users.saveRoles": "Save Roles",
    "admin.users.confirmDelete": "Are you sure you want to delete user",
    "admin.users.you": "You",
    "admin.settings.title": "Site Settings",
    "admin.settings.subtitle": "Adjust name and visual identity without changing code.",
    "admin.settings.nameAndDescription": "Name and Description",
    "admin.settings.siteName": "Site Name",
    "admin.settings.siteTagline": "Site Tagline",
    "admin.settings.translationsPerLanguage": "Translations per Language",
    "admin.settings.articleUrls": "Article URLs",
    "admin.settings.publicArticlePath": "Public Article Path",
    "admin.settings.pathClassic": "Classic: /blog/slug",
    "admin.settings.pathShort": "Short: /slug (without /blog/ prefix)",
    "admin.settings.theme": "Theme",
    "admin.settings.activeTheme": "Active Theme",
    "admin.settings.postImageProcessing": "Post Image Processing",
    "admin.settings.postImageProcessingSubtitle": "Affects images uploaded in editor (dimensions/crop for OG).",
    "admin.settings.processingMode": "Processing Mode",
    "admin.settings.modeThumbnail": "Thumbnail (keep aspect ratio)",
    "admin.settings.modeCrop": "Centered Crop (OG ratio)",
    "admin.settings.maxEdge": "Max Edge (px)",
    "admin.settings.cropWidth": "Crop Width",
    "admin.settings.cropHeight": "Crop Height",
    "admin.settings.saveSettings": "Save Settings",
    "admin.settings.imagesPreviewUpload": "Images — Preview and Upload",
    "admin.settings.imagesHelp": "Uploaded files go to /static/images/site_uploads/ and automatically update settings.",
    "admin.translations.title": "Translations & Languages",
    "admin.translations.subtitle": "Simple workflow: source English text on the left, translation for selected language on the right.",
    "admin.translations.languages": "Languages",
    "admin.translations.setDefault": "Set Default",
    "admin.translations.translationsHeader": "Translations",
    "admin.translations.tableHelp": "On the left you see English source text, and on the right you complete the translation for the selected language.",
    "admin.translations.enterTranslation": "Enter translation here",
    "admin.translations.noTranslationsAlert": "No English translations exist yet for this catalog.",
    "admin.themes.title": "Themes",
    "admin.themes.subtitle": "Upload a theme as a .zip archive (templates + CSS).",
    "admin.themes.installHelp": "Themes install into /themes/<slug>/ and /static/themes/<slug>/.",
    "admin.themes.uploadTitle": "Upload Theme",
    "admin.themes.zipArchive": "ZIP Archive",
    "admin.themes.overwriteExisting": "Overwrite if theme already exists",
    "admin.actions.install": "Install",
    "admin.themes.installedThemes": "Installed Themes",
    "admin.themes.colName": "Name",
    "admin.themes.colAuthor": "Author",
    "admin.themes.colActive": "Active",
    "admin.themes.yes": "Yes",
    "admin.themes.no": "No",
    "admin.themes.confirmDelete": "Are you sure you want to delete theme",
    "admin.themes.changeThemeHelp": "Changing active theme is done from Settings.",
    "admin.plugins.title": "Plugins",
    "admin.plugins.subtitle": "Management and installation of additional modules via .zip archives.",
    "admin.plugins.uploadTitle": "Upload Plugin",
    "admin.plugins.zipArchive": "ZIP Archive",
    "admin.plugins.overwriteExisting": "Overwrite if already exists",
    "admin.plugins.restartContainer": "Restart Container",
    "admin.plugins.installedPlugins": "Installed Plugins",
    "admin.plugins.colName": "Name",
    "admin.plugins.colVersion": "Version",
    "admin.plugins.confirmDelete": "Are you sure you want to delete plugin",
    "admin.plugins.noPluginsFound": "No plugins found in /plugins.",
    "admin.categories.title": "Categories",
    "admin.categories.subtitle": "Add and organize blog categories.",
    "admin.categories.depthPrefix": "Subcategory",
    "admin.categories.empty": "No categories exist yet.",
    "admin.categories.addTitle": "Add Category",
    "admin.categories.nameLabel": "Category Name",
    "admin.categories.parentLabel": "Parent Category (optional)",
    "admin.categories.noParent": "None (Root Category)",
    "admin.categories.saveBtn": "Save Category",
    "admin.editor.editTitle": "Edit Post",
    "admin.editor.newTitle": "New Post",
    "admin.editor.subtitle": "Multilingual editor: fill in the title, excerpt, and content for each language.",
    "admin.editor.slugLabel": "URL Slug",
    "admin.editor.categoryLabel": "Category",
    "admin.editor.status": "Status",
    "admin.editor.isDraft": "Save as Draft",
    "admin.editor.staticPageHeader": "Static Page / Fixed Link in Navigation Header",
    "admin.editor.staticPageHelp": "Check if you want this article/page to appear as a fixed link in the main top menu (e.g. About, Contact, Terms).",
    "admin.editor.navLabel": "Menu Label (optional)",
    "admin.editor.heroImageLabel": "Hero Image (Main Article Cover)",
    "admin.editor.selectFromMedia": "Select Image from Media Library",
    "admin.editor.removeHeroImage": "Remove Hero Image",
    "admin.editor.postTitleLabel": "Post Title",
    "admin.editor.excerptLabel": "Excerpt",
    "admin.editor.contentLabel": "Content",
    "admin.editor.saveBtn": "Save Post",
    "admin.editor.cancelBtn": "Cancel",
    "admin.actions.add": "Add",
    "admin.actions.change": "Change",
    "footer.quickNav": "Quick Navigation",
    "footer.home": "🏠 Home",
    "footer.categories": "📁 Categories",
    "footer.admin": "⚡ Admin Panel",
    "footer.aboutBlog": "About Blog",
    "footer.theme": "Theme",
    "footer.communityTitle": "VlahX Community",
    "footer.communityText": "Join the VlahX community — sharing ideas, projects, and technological innovations.",
    "footer.rights": "All rights reserved.",
    "footer.management": "Administration",
    "footer.myAccount": "👤 My Account",
    "footer.adminPanel": "⚡ Admin Control Panel",
    "footer.pluginsManager": "🔌 Plugins Management",
    "footer.themesManager": "🎨 Themes Management",
    "footer.systemInfo": "System & Technology",
    "footer.systemPoweredBy": "Powered by Blog 2.0 Core (FastAPI, Jinja2 & SQLite).",
    "footer.backToTop": "⬆️ Back to top",
    "footer.craftedBy": "Crafted with ❤️ by Antigravity AI",
}


def _normalize_locale(locale: str | None) -> str:
    if not locale:
        return DEFAULT_LOCALE
    return locale.strip().lower()


def _flatten_translation_rows(rows: list[TranslationEntry]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for row in rows:
        if not row.key:
            continue
        parts = row.key.split(".")
        cur = data
        for part in parts[:-1]:
            if part not in cur or not isinstance(cur[part], dict):
                cur[part] = {}
            cur = cur[part]
        cur[parts[-1]] = row.value
    return data


def _merge_translation_maps(locale_data: dict[str, Any], fallback_data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in sorted(set(locale_data) | set(fallback_data)):
        locale_value = locale_data.get(key)
        fallback_value = fallback_data.get(key)
        if isinstance(locale_value, dict) and isinstance(fallback_value, dict):
            result[key] = _merge_translation_maps(locale_value, fallback_value)
        elif isinstance(locale_value, str) and locale_value.strip():
            result[key] = locale_value
        elif fallback_value is not None:
            result[key] = fallback_value
        elif key in locale_data:
            result[key] = locale_value
    return result


_AVAILABLE_LOCALES_CACHE: list[dict[str, Any]] | None = None


def get_available_locales() -> list[dict[str, Any]]:
    global _AVAILABLE_LOCALES_CACHE
    if _AVAILABLE_LOCALES_CACHE is not None:
        return _AVAILABLE_LOCALES_CACHE
    ensure_default_locale()
    init_db()
    with SessionLocal() as db:
        rows = db.query(TranslationLocale).filter(TranslationLocale.enabled.is_(True)).order_by(TranslationLocale.is_default.desc(), TranslationLocale.code.asc()).all()
        res = [
            {"code": row.code, "name": row.name or row.code, "enabled": row.enabled, "is_default": row.is_default}
            for row in rows
        ]
        _AVAILABLE_LOCALES_CACHE = res
        return res


def list_translation_catalog(locale: str, *, source_locale: str = DEFAULT_LOCALE) -> list[dict[str, Any]]:
    locale = _normalize_locale(locale)
    source_locale = _normalize_locale(source_locale)
    init_db()
    with SessionLocal() as db:
        source_rows = (
            db.query(TranslationEntry)
            .filter(TranslationEntry.locale_code == source_locale)
            .order_by(TranslationEntry.key)
            .all()
        )
        if not source_rows:
            seed_default_translation_catalog()
            source_rows = (
                db.query(TranslationEntry)
                .filter(TranslationEntry.locale_code == source_locale)
                .order_by(TranslationEntry.key)
                .all()
            )
        target_rows = (
            db.query(TranslationEntry)
            .filter(TranslationEntry.locale_code == locale)
            .order_by(TranslationEntry.key)
            .all()
        ) if locale != source_locale else source_rows

    target_lookup = {row.key: row.value for row in target_rows if row.key}
    return [
        {
            "key": row.key,
            "source_value": row.value or "",
            "target_value": target_lookup.get(row.key, ""),
        }
        for row in source_rows
        if row.key
    ]


def seed_default_translation_catalog() -> None:
    init_db()
    with SessionLocal() as db:
        for key, value in DEFAULT_TRANSLATION_CATALOG.items():
            row = (
                db.query(TranslationEntry)
                .filter(TranslationEntry.locale_code == DEFAULT_LOCALE, TranslationEntry.key == key)
                .first()
            )
            if row is None:
                db.add(TranslationEntry(locale_code=DEFAULT_LOCALE, key=key, value=value))
            elif not (row.value or "").strip():
                row.value = value
        db.commit()


def ensure_default_locale() -> None:
    init_db()
    with SessionLocal() as db:
        en_row = db.query(TranslationLocale).filter(TranslationLocale.code == "en").first()
        if en_row is None:
            db.add(TranslationLocale(code="en", name="English", enabled=True, is_default=True))
        else:
            en_row.enabled = True
            en_row.is_default = True
        db.commit()
    seed_default_translation_catalog()


_TRANSLATION_CACHE: dict[str, dict[str, Any]] = {}


def invalidate_translation_cache(locale: str | None = None) -> None:
    global _TRANSLATION_CACHE, _AVAILABLE_LOCALES_CACHE
    _AVAILABLE_LOCALES_CACHE = None
    try:
        from app.core.i18n import clear_i18n_cache
        clear_i18n_cache()
    except Exception:
        pass
    try:
        from app.core.config import invalidate_nav_fixed_post_links_cache
        invalidate_nav_fixed_post_links_cache()
    except Exception:
        pass
    if locale:
        _TRANSLATION_CACHE.pop(_normalize_locale(locale), None)
    else:
        _TRANSLATION_CACHE.clear()


def get_translations_from_db(locale: str) -> dict[str, Any]:
    norm = _normalize_locale(locale)
    if norm in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[norm]
    init_db()
    with SessionLocal() as db:
        rows = db.query(TranslationEntry).filter(TranslationEntry.locale_code == norm).all()
        fallback_rows = []
        if norm != DEFAULT_LOCALE:
            fallback_rows = db.query(TranslationEntry).filter(TranslationEntry.locale_code == DEFAULT_LOCALE).all()
    data = _flatten_translation_rows(rows)
    if norm != DEFAULT_LOCALE and fallback_rows:
        fallback_data = _flatten_translation_rows(fallback_rows)
        data = _merge_translation_maps(data, fallback_data)
    _TRANSLATION_CACHE[norm] = data
    return data


def get_translation_from_db(locale: str, key: str, default: str | None = None) -> str:
    norm = _normalize_locale(locale)
    catalog = get_translations_from_db(norm)
    if key in catalog and isinstance(catalog[key], str) and catalog[key].strip():
        return catalog[key].strip()
    return ""


def set_translation_entry(locale: str, key: str, value: str) -> None:
    locale = _normalize_locale(locale)
    invalidate_translation_cache(locale)
    init_db()
    with SessionLocal() as db:
        locale_row = db.query(TranslationLocale).filter(TranslationLocale.code == locale).first()
        if locale_row is None:
            db.add(TranslationLocale(code=locale, name=locale.upper(), enabled=True, is_default=False))
            db.commit()
        row = (
            db.query(TranslationEntry)
            .filter(TranslationEntry.locale_code == locale, TranslationEntry.key == key)
            .first()
        )
        if row is None:
            db.add(TranslationEntry(locale_code=locale, key=key, value=value or ""))
        else:
            row.value = value or ""
        db.commit()


def set_translation_values(locale: str, values: dict[str, str]) -> None:
    locale = _normalize_locale(locale)
    invalidate_translation_cache(locale)
    init_db()
    if not values:
        return
    with SessionLocal() as db:
        locale_row = db.query(TranslationLocale).filter(TranslationLocale.code == locale).first()
        if locale_row is None:
            db.add(TranslationLocale(code=locale, name=locale.upper(), enabled=True, is_default=False))
            db.commit()

        for key, value in values.items():
            if not key:
                continue
            row = (
                db.query(TranslationEntry)
                .filter(TranslationEntry.locale_code == locale, TranslationEntry.key == key)
                .first()
            )
            if row is None:
                db.add(TranslationEntry(locale_code=locale, key=key, value=value or ""))
            else:
                row.value = value or ""
        db.commit()


def seed_locale_from_default(locale: str) -> None:
    locale = _normalize_locale(locale)
    if locale == DEFAULT_LOCALE:
        return
    init_db()
    with SessionLocal() as db:
        locale_row = db.query(TranslationLocale).filter(TranslationLocale.code == locale).first()
        if locale_row is None:
            db.add(TranslationLocale(code=locale, name=locale.upper(), enabled=True, is_default=False))
            db.flush()

        source_rows = db.query(TranslationEntry).filter(TranslationEntry.locale_code == DEFAULT_LOCALE).all()
        for source_row in source_rows:
            target_row = (
                db.query(TranslationEntry)
                .filter(TranslationEntry.locale_code == locale, TranslationEntry.key == source_row.key)
                .first()
            )
            if target_row is None:
                db.add(TranslationEntry(locale_code=locale, key=source_row.key, value=source_row.value or ""))
            elif not (target_row.value or "").strip():
                target_row.value = source_row.value or ""
        db.commit()


def delete_translation_entry(locale_code: str, key: str) -> None:
    locale = _normalize_locale(locale_code)
    init_db()
    with SessionLocal() as db:
        row = (
            db.query(TranslationEntry)
            .filter(TranslationEntry.locale_code == locale, TranslationEntry.key == key)
            .first()
        )
        if row is not None:
            db.delete(row)
            db.commit()
    invalidate_translation_cache(locale)


def delete_locale(locale_code: str) -> bool:
    locale = _normalize_locale(locale_code)
    init_db()
    with SessionLocal() as db:
        locale_row = db.query(TranslationLocale).filter(TranslationLocale.code == locale).first()
        if locale_row is None:
            return False
        if locale_row.is_default:
            return False
        db.query(TranslationEntry).filter(TranslationEntry.locale_code == locale).delete()
        db.delete(locale_row)
        db.commit()
    invalidate_translation_cache()
    return True


def set_translation_locale_enabled(locale_code: str, enabled: bool) -> bool:
    locale = _normalize_locale(locale_code)
    init_db()
    with SessionLocal() as db:
        locale_row = db.query(TranslationLocale).filter(TranslationLocale.code == locale).first()
        if locale_row is None:
            return False
        locale_row.enabled = enabled
        db.commit()
    invalidate_translation_cache()
    return True


def set_default_locale(locale_code: str) -> bool:
    """Setează limba implicită a platformei (is_default=True)"""
    locale = _normalize_locale(locale_code)
    init_db()
    with SessionLocal() as db:
        db.query(TranslationLocale).update({TranslationLocale.is_default: False})
        row = db.query(TranslationLocale).filter(TranslationLocale.code == locale).first()
        if row is None:
            db.add(TranslationLocale(code=locale, name=locale.upper(), enabled=True, is_default=True))
        else:
            row.is_default = True
            row.enabled = True
        db.commit()
    invalidate_translation_cache()
    return True