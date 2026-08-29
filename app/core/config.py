from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from app.models.db_models import AppSetting

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = PROJECT_ROOT / "app"
load_dotenv(PROJECT_ROOT / ".env", override=False)

VLAH_CORE_VERSION = "2.0.0"


def _get_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


SESSION_SECRET = (
    os.environ.get("SESSION_SECRET", "").strip() or "dev-insecure-session-secret"
)

# URL public (https://domeniu.tld) — doar din .env (Caddy / domeniu). Folosit la OG, TinyMCE, canonice.
# Nu se suprascrie din admin; fiecare container își are .env-ul lui.
def _normalize_public_site_url(raw: str) -> str:
    u = (raw or "").strip().rstrip("/")
    if not u or u.lower() in ("none", "null", "undefined") or "camionagiul.club" in u:
        return ""
    return u


PUBLIC_SITE_URL = _normalize_public_site_url(os.environ.get("PUBLIC_SITE_URL", ""))

# Nume afișat (navbar, meta og:site_name). Suprascrie din admin (site_settings.json) sau .env.
SITE_DISPLAY_NAME = (
    os.environ.get("SITE_DISPLAY_NAME", "").strip() or "Blog"
)
SITE_TAGLINE = (
    os.environ.get("SITE_TAGLINE", "").strip()
)

# Favicon (`<link rel="icon">`). Cale relativă, începe cu `/`.
SITE_FAVICON_PATH = (
    os.environ.get("SITE_FAVICON_PATH", "/static/images/favicon.ico").strip()
    or "/static/images/post_images/favicon.ico"
)

# Apple touch / fallback brand. Cale relativă, începe cu `/`.
SITE_BRAND_IMAGE_PATH = (
    os.environ.get("SITE_BRAND_IMAGE_PATH", "/static/images/site-brand.svg").strip()
    or "/static/images/site-brand.svg"
)

# og:image / twitter:image — fișier static PNG sau JPEG (~1200×630), cale relativă cu `/`.
# Dacă articolul are doar WebP sau altceva, meta folosește tot acest fișier.
OG_CARD_IMAGE_PATH = (
    os.environ.get("OG_CARD_IMAGE_PATH", "").strip()
)

# Icon navbar / hero (opțional). Gol → SVG implicit în template.
SITE_NAV_ICON_PATH = os.environ.get("SITE_NAV_ICON_PATH", "").strip()

# Link fix în navbar către un articol publicat: slug-ul din `/blog/<slug>`. Suprascrie din admin.
NAV_FIXED_POST_SLUG = os.environ.get("NAV_FIXED_POST_SLUG", "").strip()
NAV_FIXED_POST_LABEL = os.environ.get("NAV_FIXED_POST_LABEL", "").strip()

# Tema activă (numele folderului din `themes/<name>/templates`). Suprascrie din admin.
ACTIVE_THEME = os.environ.get("ACTIVE_THEME", "").strip() or "minimal"


# La upload, fără crop: imaginea încape în max_edge×max_edge (PIL thumbnail). Folosit dacă POST_IMAGE_CROP_OG=false.
def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        v = int(raw)
        return v if v > 0 else default
    except ValueError:
        return default


POST_IMAGE_MAX_EDGE = _int_env("POST_IMAGE_MAX_EDGE", 1200)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return default


# Articole la /slug în loc de /blog/slug (redirect 301 de la /blog/slug când e activ).
FLAT_POST_URLS = _bool_env("FLAT_POST_URLS", False)

# Sluguri interzise la rădăcină când FLAT_POST_URLS e activ (nu pot fi articole).
ROOT_SLUG_BLOCKLIST = frozenset(
    {
        "admin",
        "api",
        "static",
        "docs",
        "redoc",
        "openapi.json",
        "robots.txt",
        "favicon.ico",
        "login",
        "logout",
        "newsletter",
        "hosting",
        "blog",
        "shop",
        "cart",
        "checkout",
        "lang",
    }
)

# Cu CROP_OG=true: crop centrat + resize exact la OUTPUT_* (implicit 1200×630 ≈ 1,91:1, ca OG clasic / ~19:10).
# Pentru upload TinyMCE, default-ul este fără crop și dimensiunea maximă a laturei la 1200px.
POST_IMAGE_CROP_OG = _bool_env("POST_IMAGE_CROP_OG", False)
POST_IMAGE_OUTPUT_WIDTH = _int_env("POST_IMAGE_OUTPUT_WIDTH", 1200)
POST_IMAGE_OUTPUT_HEIGHT = _int_env("POST_IMAGE_OUTPUT_HEIGHT", 630)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "").strip()
TELEGRAM_AUTH_TTL_SECONDS = int(
    os.environ.get("TELEGRAM_AUTH_TTL_SECONDS", "86400").strip()
)
TELEGRAM_AUTH_URL = (
    os.environ.get("TELEGRAM_AUTH_URL", "").strip() or "/admin/login/telegram"
)

# Chat ID (sau @channel) unde trimite botul notificări (ex. abonare newsletter). Același TELEGRAM_BOT_TOKEN ca la login.
TELEGRAM_NOTIFY_CHAT_ID = os.environ.get("TELEGRAM_NOTIFY_CHAT_ID", "").strip()

# Admin → Plugin-uri: buton care trimite SIGTERM procesului (Docker cu restart: unless-stopped repornește containerul).
ADMIN_ENABLE_CONTAINER_RESTART = _bool_env("ADMIN_ENABLE_CONTAINER_RESTART", False)

# Newsletter / SMTP: log hexdump tranzacție; fără verificare cert (ex. server intern Docker cu cert self-signed).
SMTP_DEBUG = _bool_env("SMTP_DEBUG", False)
SMTP_SKIP_TLS_VERIFY = _bool_env("SMTP_SKIP_TLS_VERIFY", False)


def _runtime() -> dict:
    from app.core.site_settings import read_settings

    return read_settings()


def _db_runtime() -> dict[str, str]:
    try:
        from app.utils.db import SessionLocal

        with SessionLocal() as db:
            rows = db.query(AppSetting).all()
            return {row.key: row.value for row in rows if row and row.key}
    except Exception:
        return {}


def get_public_site_url() -> str:
    """Baza absolută a site-ului — exclusiv din PUBLIC_SITE_URL (.env)."""
    return PUBLIC_SITE_URL


def _get_localized_setting(d: dict, key: str, locale: str | None = None, fallback: str = "") -> str:
    if not isinstance(d, dict):
        return fallback
    if locale:
        locale_key = f"{key}_{locale}"
        raw = d.get(locale_key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    raw = d.get(key)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return fallback


def get_site_display_name(locale: str | None = None) -> str:
    d = {**_runtime(), **_db_runtime()}
    raw = _get_localized_setting(d, "SITE_DISPLAY_NAME", locale, SITE_DISPLAY_NAME)
    return raw or SITE_DISPLAY_NAME


def get_site_tagline(locale: str | None = None) -> str:
    d = {**_runtime(), **_db_runtime()}
    raw = _get_localized_setting(d, "SITE_TAGLINE", locale, SITE_TAGLINE)
    if raw:
        return raw
    if locale == "ro":
        return "O platformă web modulară. Construiește, extinde și personalizează aplicația ta cu plugin-uri și teme."
    return "A modular web platform. Build, extend and customize your web application with plugins and themes."


def get_site_favicon_path() -> str:
    d = _runtime()
    raw = d.get("SITE_FAVICON_PATH")
    if isinstance(raw, str) and raw.strip():
        v = raw.strip()
        return v if v.startswith("/") else f"/{v}"
    return SITE_FAVICON_PATH


def get_site_brand_image_path() -> str:
    d = _runtime()
    raw = d.get("SITE_BRAND_IMAGE_PATH")
    if isinstance(raw, str) and raw.strip():
        v = raw.strip()
        return v if v.startswith("/") else f"/{v}"
    return SITE_BRAND_IMAGE_PATH


def get_og_card_image_path() -> str:
    d = {**_runtime(), **_db_runtime()}
    raw = d.get("OG_CARD_IMAGE_PATH")
    if isinstance(raw, str) and raw.strip():
        v = raw.strip()
        if "camionagiul" not in v:
            return v if v.startswith("/") else f"/{v}"
    if OG_CARD_IMAGE_PATH and "camionagiul" not in OG_CARD_IMAGE_PATH:
        return OG_CARD_IMAGE_PATH if OG_CARD_IMAGE_PATH.startswith("/") else f"/{OG_CARD_IMAGE_PATH}"
    b = get_site_brand_image_path()
    if b:
        return b if b.startswith("/") else f"/{b}"
    return ""


def get_twitter_site() -> str:
    d = _runtime()
    raw = d.get("TWITTER_SITE")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return os.environ.get("TWITTER_SITE", "").strip()


def get_site_nav_icon_path() -> str:
    """Cale relativă cu `/` sau gol pentru fallback SVG în template."""
    d = _runtime()
    raw = d.get("SITE_NAV_ICON_PATH")
    if isinstance(raw, str) and raw.strip():
        v = raw.strip()
        return v if v.startswith("/") else f"/{v}"
    if SITE_NAV_ICON_PATH:
        v = SITE_NAV_ICON_PATH.strip()
        return v if v.startswith("/") else f"/{v}"
    return ""


def get_homepage_mode() -> str:
    """
    Modul primei pagini (root '/'):
    - 'blog': lista de articole pe blog (implicit).
    - 'page:<slug>': o pagină statică cu slug-ul respectiv.
    - 'shop': magazinul minishop (dacă pluginul e activ).
    """
    d = _runtime()
    raw = d.get("HOMEPAGE_MODE")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return os.environ.get("HOMEPAGE_MODE", "blog").strip() or "blog"


def _runtime_static_nav_items(d: dict) -> list[dict[str, str]]:
    raw_links = d.get("STATIC_NAV_LINKS")
    items: list[dict[str, str]] = []
    if isinstance(raw_links, str):
        try:
            raw_links = __import__("json").loads(raw_links)
        except Exception:
            raw_links = []
    if isinstance(raw_links, list):
        for item in raw_links:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or item.get("href") or "").strip()
            slug = str(item.get("slug") or item.get("value") or "").strip()
            label = str(item.get("label") or item.get("fixed_label") or item.get("title") or slug or url).strip()
            labels_dict = item.get("labels") if isinstance(item.get("labels"), dict) else {}
            target = str(item.get("target") or "_self").strip()
            loc = str(item.get("location") or "navbar").strip().lower()
            if loc not in ("navbar", "footer", "both"):
                loc = "navbar"
            if not label and not url and not slug and not labels_dict:
                continue
            items.append({
                "slug": slug,
                "label": label,
                "fixed_label": label,
                "labels": labels_dict,
                "url": url,
                "href": url if url else (f"/{slug.strip('/')}" if slug else "/"),
                "target": target if target in ("_self", "_blank") else "_self",
                "location": loc,
            })
    return items


def _get_static_nav_items_raw() -> list[dict[str, str]]:
    d = {**_runtime(), **_db_runtime()}
    if "STATIC_NAV_LINKS" in d:
        return _runtime_static_nav_items(d)

    raw_single = d.get("NAV_FIXED_POST_SLUG")
    if isinstance(raw_single, str) and raw_single.strip():
        slug = raw_single.strip()
        label = str(d.get("NAV_FIXED_POST_LABEL") or slug).strip()
        return [{"slug": slug, "label": label, "fixed_label": label, "labels": {}, "url": f"/{slug}", "href": f"/{slug}", "target": "_self", "location": "navbar"}]

    return []


def get_nav_fixed_post_slug_setting() -> str:
    d = _runtime()
    raw = d.get("NAV_FIXED_POST_SLUG")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()

    for item in _runtime_static_nav_items(d):
        slug = str(item.get("slug") or "").strip()
        if slug:
            return slug

    raw_env = NAV_FIXED_POST_SLUG
    if isinstance(raw_env, str) and raw_env.strip():
        return raw_env.strip()
    return ""


def get_nav_fixed_post_label_setting() -> str:
    d = _runtime()
    raw = d.get("NAV_FIXED_POST_LABEL")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()

    for item in _runtime_static_nav_items(d):
        label = item.get("label") or item.get("fixed_label") or ""
        if label:
            return label

    raw_env = NAV_FIXED_POST_LABEL
    if isinstance(raw_env, str) and raw_env.strip():
        return raw_env.strip()
    return ""


_NAV_FIXED_POST_LINKS_CACHE: dict[str, list[dict[str, str]]] = {}


def invalidate_nav_fixed_post_links_cache() -> None:
    global _NAV_FIXED_POST_LINKS_CACHE
    _NAV_FIXED_POST_LINKS_CACHE.clear()


def get_nav_fixed_post_links(locale: str | None = None, location: str | None = None) -> list[dict[str, str]]:
    global _NAV_FIXED_POST_LINKS_CACHE
    cache_key = f"{locale or 'default'}_{location or 'all'}".strip().lower()
    if cache_key in _NAV_FIXED_POST_LINKS_CACHE:
        return _NAV_FIXED_POST_LINKS_CACHE[cache_key]

    items: list[dict[str, str]] = []
    from sqlalchemy import select

    from app.models.db_models import Post as PostModel
    from app.models.db_models import PostTranslation as PostTranslationModel
    from app.utils.db import SessionLocal

    try:
        with SessionLocal() as db:
            rows = db.execute(select(PostModel)).scalars().all()
            post_lookup = {row.slug: row for row in rows if getattr(row, "slug", None)}
            translated_titles = {}
            if locale:
                translated_rows = db.execute(
                    select(PostTranslationModel).where(PostTranslationModel.locale_code == locale)
                ).scalars().all()
                for tr in translated_rows:
                    translated_titles.setdefault(tr.post_id, tr.title.strip())

            for item in _get_static_nav_items_raw():
                item_loc = str(item.get("location") or "navbar").strip().lower()
                if location and item_loc not in (location.lower(), "both"):
                    continue

                url = str(item.get("url") or item.get("href") or "").strip()
                slug = str(item.get("slug") or "").strip()
                target = str(item.get("target") or "_self").strip()
                target = target if target in ("_self", "_blank") else "_self"
                labels_dict = item.get("labels") if isinstance(item.get("labels"), dict) else {}
                loc_label = labels_dict.get(locale) if (locale and labels_dict.get(locale)) else None
                fallback = str(loc_label or item.get("label") or item.get("fixed_label") or slug or url).strip()

                if url and not slug:
                    items.append({
                        "slug": "",
                        "label": fallback,
                        "fixed_label": fallback,
                        "url": url,
                        "href": url,
                        "target": target,
                        "location": item_loc,
                    })
                    continue

                if not slug:
                    if url:
                        items.append({
                            "slug": "",
                            "label": fallback,
                            "fixed_label": fallback,
                            "url": url,
                            "href": url,
                            "target": target,
                            "location": item_loc,
                        })
                    continue

                row = post_lookup.get(slug)
                if row and not getattr(row, "draft", False):
                    label = row.title.strip() or fallback
                    if locale:
                        title = translated_titles.get(row.id)
                        if title and title.strip():
                            label = title.strip()
                        elif loc_label and loc_label.strip():
                            label = loc_label.strip()
                    item_href = url if url else post_public_path(slug)
                    items.append({
                        "slug": slug,
                        "label": label,
                        "fixed_label": label,
                        "url": item_href,
                        "href": item_href,
                        "target": target,
                        "location": item_loc,
                    })
                elif url:
                    items.append({
                        "slug": slug,
                        "label": fallback,
                        "fixed_label": fallback,
                        "url": url,
                        "href": url,
                        "target": target,
                        "location": item_loc,
                    })
    except Exception:
        pass

    _NAV_FIXED_POST_LINKS_CACHE[cache_key] = items
    return items


def get_flat_post_urls() -> bool:
    """True → articole la /slug; False → /blog/slug."""
    d = _runtime()
    if "FLAT_POST_URLS" not in d:
        return FLAT_POST_URLS
    v = d["FLAT_POST_URLS"]
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return FLAT_POST_URLS


def get_active_theme() -> str:
    """
    Numele temei active (ex. "default", "minimal").
    Limităm la caractere sigure ca să evităm path traversal.
    """
    d = _runtime()
    raw = d.get("ACTIVE_THEME")
    if isinstance(raw, str) and raw.strip():
        v = raw.strip()
    else:
        v = ACTIVE_THEME
    v = (v or "").strip().lower()
    if not v or v == "default":
        return "minimal"
    ok = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
    if any(ch not in ok for ch in v):
        return "minimal"
    theme_templates = APP_DIR / "themes" / v / "templates"
    if not theme_templates.is_dir():
        return "minimal"
    return v


def is_static_page_slug(slug: str) -> bool:
    if not slug:
        return False
    s = slug.strip().lower()
    if s in ROOT_SLUG_BLOCKLIST:
        return False
    if s in ("home", "about", "despre", "contact", "privacy", "terms", "termeni", "politica"):
        return True
    return any(str(item.get("slug") or "").strip().lower() == s for item in _get_static_nav_items_raw())


def post_public_path(slug: str) -> str:
    s = (slug or "").strip().strip("/")
    if not s:
        return "/"
    if get_homepage_mode() == f"page:{s}":
        return "/"
    if get_flat_post_urls() or is_static_page_slug(s):
        return f"/{s}"
    return f"/blog/{s}"


def get_nav_fixed_post_link(locale: str | None = None) -> dict[str, str] | None:
    """Returnează primul link static valid pentru navbar."""
    links = get_nav_fixed_post_links(locale=locale)
    if not links:
        return None
    slug = links[0]["slug"]
    from sqlalchemy import select

    from app.models.db_models import Post as PostModel
    from app.utils.db import SessionLocal

    with SessionLocal() as db:
        row = db.execute(select(PostModel).where(PostModel.slug == slug)).scalars().first()
        if row is None or bool(row.draft):
            return None
        label = links[0].get("label") or row.title
        return {
            "slug": slug,
            "href": post_public_path(slug),
            "label": label,
            "fixed_label": label,
        }


def get_post_image_crop_og() -> bool:
    d = _runtime()
    if "POST_IMAGE_CROP_OG" not in d:
        return POST_IMAGE_CROP_OG
    v = d["POST_IMAGE_CROP_OG"]
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return POST_IMAGE_CROP_OG


def get_post_image_max_edge() -> int:
    d = _runtime()
    if "POST_IMAGE_MAX_EDGE" not in d:
        return POST_IMAGE_MAX_EDGE
    try:
        n = int(d["POST_IMAGE_MAX_EDGE"])
        return n if n > 0 else POST_IMAGE_MAX_EDGE
    except (TypeError, ValueError):
        return POST_IMAGE_MAX_EDGE


def get_post_image_output_width() -> int:
    d = _runtime()
    if "POST_IMAGE_OUTPUT_WIDTH" not in d:
        return POST_IMAGE_OUTPUT_WIDTH
    try:
        n = int(d["POST_IMAGE_OUTPUT_WIDTH"])
        return n if n > 0 else POST_IMAGE_OUTPUT_WIDTH
    except (TypeError, ValueError):
        return POST_IMAGE_OUTPUT_WIDTH


def get_post_image_output_height() -> int:
    d = _runtime()
    if "POST_IMAGE_OUTPUT_HEIGHT" not in d:
        return POST_IMAGE_OUTPUT_HEIGHT
    try:
        n = int(d["POST_IMAGE_OUTPUT_HEIGHT"])
        return n if n > 0 else POST_IMAGE_OUTPUT_HEIGHT
    except (TypeError, ValueError):
        return POST_IMAGE_OUTPUT_HEIGHT


def get_telegram_bot_token() -> str:
    """Token: app_settings, apoi setarea plugin `telegram_notify`, apoi .env."""
    from app.core.plugin_db_settings import get_plugin_setting as legacy_get
    from app.core.plugin_manager import get_plugin_setting as plugin_get

    v = legacy_get("telegram_bot_token")
    if v:
        return v
    v2 = plugin_get("telegram_notify", "bot_token")
    return v2 if v2 else TELEGRAM_BOT_TOKEN


def get_telegram_notify_chat_id() -> str:
    from app.core.plugin_db_settings import get_plugin_setting as legacy_get
    from app.core.plugin_manager import get_plugin_setting as plugin_get

    v = legacy_get("telegram_notify_chat_id")
    if v:
        return v
    v2 = plugin_get("telegram_notify", "chat_id")
    return v2 if v2 else TELEGRAM_NOTIFY_CHAT_ID


def get_telegram_bot_username() -> str:
    import os
    d = _runtime()
    if d.get("TELEGRAM_BOT_USERNAME"):
        v = str(d.get("TELEGRAM_BOT_USERNAME")).strip().lstrip("@")
        if v:
            return v
    from app.core.plugin_db_settings import get_plugin_setting as legacy_get
    from app.core.plugin_manager import get_plugin_setting as plugin_get

    v = legacy_get("telegram_bot_username")
    if v:
        return v.strip().lstrip("@")
    v2 = plugin_get("telegram_notify", "bot_username")
    if v2:
        return v2.strip().lstrip("@")
    return os.environ.get("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")


def get_repo_api_url() -> str:
    import os
    env_val = os.environ.get("REPO_API_URL", "").strip()
    if env_val:
        return env_val
    from app.core.plugin_db_settings import get_plugin_setting as legacy_get
    v = legacy_get("repo_api_url")
    if v:
        return v.strip()

    official_url = "https://repo.vlahx.org/api/v1/catalog.json"
    try:
        import urllib.request, ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(official_url, headers={"User-Agent": "VlahX-Core-2.0"})
        with urllib.request.urlopen(req, timeout=3, context=ctx) as resp:
            if resp.status == 200:
                return official_url
    except Exception:
        pass

    return "http://vlahx-repo:8080/api/v1/catalog.json"
