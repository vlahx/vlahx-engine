from __future__ import annotations

import json
from typing import Any


def read_settings() -> dict[str, Any]:
    data: dict[str, Any] = {}
    try:
        from app.utils.db import SessionLocal
        from app.models.db_models import AppSetting
        with SessionLocal() as db:
            rows = db.query(AppSetting).all()
            for row in rows:
                if not row or not row.key:
                    continue
                k = row.key
                v = row.value
                if k == "STATIC_NAV_LINKS" and v:
                    try:
                        data[k] = json.loads(v)
                    except Exception:
                        data[k] = []
                elif k in ("POST_IMAGE_CROP_OG", "FLAT_POST_URLS"):
                    data[k] = str(v).strip().lower() in ("1", "true", "yes", "on")
                elif k in ("POST_IMAGE_MAX_EDGE", "POST_IMAGE_OUTPUT_WIDTH", "POST_IMAGE_OUTPUT_HEIGHT"):
                    try:
                        data[k] = int(v)
                    except (ValueError, TypeError):
                        pass
                else:
                    data[k] = str(v).strip() if v is not None else ""
    except Exception:
        pass

    return data


def write_settings(updates: dict[str, Any]) -> None:
    """Actualizează setările direct în tabela `app_settings` din baza de date SQLite."""
    try:
        from app.utils.db import SessionLocal
        from app.models.db_models import AppSetting
        with SessionLocal() as db:
            for key, val in updates.items():
                row = db.query(AppSetting).filter(AppSetting.key == key).first()
                if val is None or str(val).strip() == "":
                    if row:
                        db.delete(row)
                else:
                    val_str = json.dumps(val) if isinstance(val, (list, dict)) else str(val).strip()
                    if row:
                        row.value = val_str
                    else:
                        db.add(AppSetting(key=key, value=val_str))
            db.commit()

        if "STATIC_NAV_LINKS" in updates:
            from app.core.config import invalidate_nav_fixed_post_links_cache
            invalidate_nav_fixed_post_links_cache()
    except Exception:
        pass


DEFAULT_SSO_APPS = [
    {
        "id": "vlahx_repo",
        "name": "VlahX Repo Store",
        "base_url": "https://repo.vlahx.org",
        "logout_url": "https://repo.vlahx.org/auth/logout",
        "is_active": True,
    }
]


def get_sso_applications() -> list[dict[str, Any]]:
    s = read_settings()
    raw = s.get("SSO_APPLICATIONS")
    apps = DEFAULT_SSO_APPS
    if raw:
        if isinstance(raw, list):
            apps = raw
        else:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    apps = parsed
            except Exception:
                pass

    res = []
    for a in apps:
        if not isinstance(a, dict):
            continue
        v = a.get("is_active")
        if isinstance(v, bool):
            active_bool = v
        elif isinstance(v, str):
            active_bool = v.lower() in ("1", "true", "on", "yes")
        elif isinstance(v, (int, float)):
            active_bool = bool(v)
        else:
            active_bool = True

        a_copy = dict(a)
        a_copy["is_active"] = active_bool
        res.append(a_copy)
    return res

def save_sso_applications(apps: list[dict[str, Any]]) -> None:
    write_settings({"SSO_APPLICATIONS": apps})

def is_sso_app_active_for_url(url: str) -> bool:
    """Verifică dacă un URL/domeniu aparține unei aplicații SSO active în baza de date."""
    if not url:
        return False
    url_clean = str(url).strip().rstrip("/").lower()
    apps = get_sso_applications()
    for a in apps:
        base = str(a.get("base_url", "")).strip().rstrip("/").lower()
        if base and (url_clean == base or url_clean.startswith(base)):
            return bool(a.get("is_active"))
    return False

