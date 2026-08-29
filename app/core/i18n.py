from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from starlette.requests import Request
from starlette.responses import Response

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = PROJECT_ROOT / "app"
LOCALES_DIR = APP_DIR / "locales"

DEFAULT_LOCALE = "ro"
SUPPORTED_LOCALES = {"en", "ro"}

_IN_MEMORY_TRANSLATIONS: dict[str, dict[str, Any]] = {}
_IN_MEMORY_LOCALES_META: dict[str, dict[str, Any]] = {}


def _ensure_locales_dir() -> Path:
    LOCALES_DIR.mkdir(parents=True, exist_ok=True)
    return LOCALES_DIR


def load_all_translations() -> None:
    global _IN_MEMORY_TRANSLATIONS, _IN_MEMORY_LOCALES_META
    _ensure_locales_dir()
    
    new_translations: dict[str, dict[str, Any]] = {}
    new_meta: dict[str, dict[str, Any]] = {}

    for file_path in LOCALES_DIR.glob("*.json"):
        code = file_path.stem.lower().strip()
        if not code:
            continue
        try:
            with file_path.open("r", encoding="utf-8") as f:
                content = json.load(f)
                meta = content.get("_meta", {})
                trans = content.get("translations", {})
                
                new_meta[code] = {
                    "code": code,
                    "name": meta.get("name") or code.upper(),
                    "enabled": meta.get("enabled", True),
                    "is_default": meta.get("is_default", code == DEFAULT_LOCALE),
                }
                new_translations[code] = trans if isinstance(trans, dict) else {}
        except Exception:
            pass

    if DEFAULT_LOCALE not in new_meta:
        new_meta[DEFAULT_LOCALE] = {
            "code": DEFAULT_LOCALE,
            "name": "English",
            "enabled": True,
            "is_default": True,
        }
        new_translations[DEFAULT_LOCALE] = {}

    _IN_MEMORY_TRANSLATIONS = new_translations
    _IN_MEMORY_LOCALES_META = new_meta


load_all_translations()


def get_available_locales() -> list[dict[str, Any]]:
    if not _IN_MEMORY_LOCALES_META:
        load_all_translations()
    locales = list(_IN_MEMORY_LOCALES_META.values())
    locales.sort(key=lambda x: (not x.get("is_default", False), x.get("code", "")))
    return locales


def get_supported_locales() -> set[str]:
    locs = get_available_locales()
    return {loc["code"] for loc in locs if loc.get("enabled")}


def get_site_default_locale() -> str:
    locs = get_available_locales()
    for loc in locs:
        if loc.get("is_default"):
            return loc["code"]
    return DEFAULT_LOCALE


def resolve_locale(request: Request | None = None, fallback: str = DEFAULT_LOCALE) -> str:
    if request is None:
        return fallback

    lang = None
    try:
        query_params = request.query_params
    except (AttributeError, KeyError, RuntimeError):
        query_params = None
    if query_params:
        lang = query_params.get("lang", "").strip().lower()

    headers = None
    if hasattr(request, "scope") and isinstance(getattr(request, "scope", None), dict) and "headers" in request.scope:
        try:
            headers = request.headers
        except (KeyError, RuntimeError, AttributeError):
            headers = None
    if not lang and headers is not None:
        lang = headers.get("x-locale", "").strip().lower()

    cookies = None
    if hasattr(request, "scope") and isinstance(getattr(request, "scope", None), dict) and "headers" in request.scope:
        try:
            cookies = request.cookies
        except (KeyError, RuntimeError, AttributeError):
            cookies = None
    if not lang and cookies is not None:
        lang = cookies.get("blog_locale", "").strip().lower()

    if not lang and headers is not None:
        accept_lang = headers.get("accept-language", "").strip().lower()
        if accept_lang:
            supported = get_supported_locales()
            for part in accept_lang.split(","):
                code_sub = part.split(";")[0].strip().split("-")[0]
                if code_sub in supported:
                    lang = code_sub
                    break

    if not lang:
        app = getattr(request, "app", None)
        lang = getattr(getattr(app, "state", None), "default_locale", None)
    if not lang:
        lang = fallback
    if lang not in get_supported_locales():
        lang = fallback
    return lang


def set_locale_cookie(response: Response, locale: str, *, path: str = "/", max_age: int = 60 * 60 * 24 * 365) -> None:
    normalized = locale if locale in get_supported_locales() else DEFAULT_LOCALE
    response.set_cookie(
        key="blog_locale",
        value=normalized,
        path=path,
        max_age=max_age,
        httponly=False,
        samesite="lax",
        secure=False,
    )


def get_translation(locale: str, key: str) -> str:
    norm = (locale or DEFAULT_LOCALE).strip().lower()
    if norm not in _IN_MEMORY_TRANSLATIONS:
        norm = DEFAULT_LOCALE

    cat = _IN_MEMORY_TRANSLATIONS.get(norm, {})
    if key in cat and isinstance(cat[key], str) and cat[key].strip():
        return cat[key].strip()

    fb_cat = _IN_MEMORY_TRANSLATIONS.get(DEFAULT_LOCALE, {})
    if key in fb_cat and isinstance(fb_cat[key], str) and fb_cat[key].strip():
        return fb_cat[key].strip()

    load_all_translations()
    cat = _IN_MEMORY_TRANSLATIONS.get(norm, {})
    if key in cat and isinstance(cat[key], str) and cat[key].strip():
        return cat[key].strip()

    fb_cat = _IN_MEMORY_TRANSLATIONS.get(DEFAULT_LOCALE, {})
    if key in fb_cat and isinstance(fb_cat[key], str) and fb_cat[key].strip():
        return fb_cat[key].strip()

    return key


def get_translations(locale: str) -> dict[str, Any]:
    load_all_translations()
    norm = (locale or DEFAULT_LOCALE).strip().lower()
    cat = dict(_IN_MEMORY_TRANSLATIONS.get(DEFAULT_LOCALE, {}))
    if norm != DEFAULT_LOCALE:
        loc_cat = _IN_MEMORY_TRANSLATIONS.get(norm, {})
        for k, v in loc_cat.items():
            if isinstance(v, str) and v.strip():
                cat[k] = v.strip()
    return cat


def get_translation_value(locale: str, key: str) -> str:
    return get_translation(locale, key)


def build_context(locale: str, **extra: Any) -> dict[str, Any]:
    translations = get_translations(locale)
    return {"locale": locale, "translations": translations, **extra}


def clear_i18n_cache() -> None:
    load_all_translations()


def save_translation_values(locale: str, values: dict[str, str]) -> None:
    norm = (locale or DEFAULT_LOCALE).strip().lower()
    file_path = LOCALES_DIR / f"{norm}.json"
    content: dict[str, Any] = {"_meta": {"name": norm.upper(), "is_default": False, "enabled": True}, "translations": {}}
    
    if file_path.is_file():
        try:
            with file_path.open("r", encoding="utf-8") as f:
                content = json.load(f)
        except Exception:
            pass

    trans = content.setdefault("translations", {})
    for k, v in values.items():
        if k:
            trans[k] = v or ""

    with file_path.open("w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

    load_all_translations()


def add_locale(code: str, name: str = "") -> None:
    norm = code.strip().lower()
    if not norm:
        return
    file_path = LOCALES_DIR / f"{norm}.json"
    if not file_path.is_file():
        source_file = LOCALES_DIR / f"{DEFAULT_LOCALE}.json"
        source_trans = {}
        if source_file.is_file():
            try:
                with source_file.open("r", encoding="utf-8") as f:
                    source_trans = json.load(f).get("translations", {})
            except Exception:
                pass
        
        content = {
            "_meta": {
                "name": name.strip() or norm.upper(),
                "is_default": False,
                "enabled": True,
            },
            "translations": source_trans,
        }
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)

    load_all_translations()


def delete_locale(code: str) -> bool:
    norm = code.strip().lower()
    if norm == DEFAULT_LOCALE:
        return False
    file_path = LOCALES_DIR / f"{norm}.json"
    if file_path.is_file():
        meta = _IN_MEMORY_LOCALES_META.get(norm, {})
        if meta.get("is_default"):
            return False
        try:
            file_path.unlink()
            load_all_translations()
            return True
        except Exception:
            return False
    return False


def set_default_locale(code: str) -> bool:
    norm = code.strip().lower()
    if norm not in _IN_MEMORY_LOCALES_META:
        return False

    for file_path in LOCALES_DIR.glob("*.json"):
        c = file_path.stem.lower().strip()
        try:
            with file_path.open("r", encoding="utf-8") as f:
                content = json.load(f)
            meta = content.setdefault("_meta", {})
            meta["is_default"] = (c == norm)
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    load_all_translations()
    return True


def list_translation_catalog(locale: str) -> list[dict[str, Any]]:
    norm = (locale or DEFAULT_LOCALE).strip().lower()
    source_cat = _IN_MEMORY_TRANSLATIONS.get(DEFAULT_LOCALE, {})
    target_cat = _IN_MEMORY_TRANSLATIONS.get(norm, {})

    keys = sorted(set(source_cat.keys()) | set(target_cat.keys()))
    return [
        {
            "key": k,
            "source_value": source_cat.get(k, ""),
            "target_value": target_cat.get(k, ""),
        }
        for k in keys
    ]


def get_plugin_translation(plugin_id: str, locale: str, key: str, default_val: str = "") -> str:
    def_locale = get_site_default_locale()
    norm_locale = (locale or def_locale).strip().lower()

    p_dir = APP_DIR / "plugins" / plugin_id / "locales"

    target_file = p_dir / f"{norm_locale}.json"
    if target_file.is_file():
        try:
            with target_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if key in data and data[key]:
                    return data[key]
        except Exception:
            pass

    def_file = p_dir / f"{def_locale}.json"
    if def_file.is_file():
        try:
            with def_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if key in data and data[key]:
                    return data[key]
        except Exception:
            pass

    ro_file = p_dir / "ro.json"
    if ro_file.is_file():
        try:
            with ro_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if key in data and data[key]:
                    return data[key]
        except Exception:
            pass

    return default_val or key