from __future__ import annotations

from app.models.db_models import AppSetting
from app.utils.db import SessionLocal

PLUGIN_SETTING_KEYS = frozenset(
    {
        "telegram_bot_token",
        "telegram_notify_chat_id",
        "telegram_bot_username",
        "newsletter_from_email",
        "newsletter_notify_email",
        "smtp_host",
        "smtp_port",
        "smtp_user",
        "smtp_password",
        "smtp_use_tls",
    }
)


def get_plugin_setting(key: str) -> str:
    if key not in PLUGIN_SETTING_KEYS:
        return ""
    with SessionLocal() as db:
        row = db.get(AppSetting, key)
        if row is None:
            return ""
        return (row.value or "").strip()


def has_plugin_setting(key: str) -> bool:
    return bool(get_plugin_setting(key))


def set_plugin_settings(updates: dict[str, str | None]) -> None:
    """
    Persistă setări plugin. Valoare None șterge cheia.
    Chei necunoscute sunt ignorate.
    """
    with SessionLocal() as db:
        for k, v in updates.items():
            if k not in PLUGIN_SETTING_KEYS:
                continue
            row = db.get(AppSetting, k)
            if v is None:
                if row is not None:
                    db.delete(row)
                continue
            s = str(v).strip()
            if row is None:
                db.add(AppSetting(key=k, value=s))
            else:
                row.value = s
        db.commit()
