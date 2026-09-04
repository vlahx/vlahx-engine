from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI

from app.core.config import APP_DIR, PROJECT_ROOT
from app.models.db_models import Plugin, PluginSetting
from app.utils.db import SessionLocal

logger = logging.getLogger(__name__)

PLUGINS_DIR = APP_DIR / "plugins"


class PluginMetadata:
    """Metadata pentru un plugin din fișierul plugin.json"""
    
    def __init__(self, data: Dict[str, Any]):
        self.name = data.get("name", "")
        self.version = data.get("version", "1.0.0")
        self.description = data.get("description", "")
        self.author = data.get("author", "")
        self.dependencies = data.get("dependencies", [])
        self.min_app_version = data.get("min_app_version", "1.0.0")
        self.permissions = data.get("permissions", [])
        self.settings_schema = data.get("settings", {})  # Schema pentru setări
        self.settings = data.get("settings", {})  # Alias pentru compatibilitate


def load_plugin_metadata(plugin_dir: Path) -> Optional[PluginMetadata]:
    """Încarcă metadata din plugin.json"""
    manifest_file = plugin_dir / "plugin.json"
    if not manifest_file.exists():
        return None
    
    try:
        with open(manifest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PluginMetadata(data)
    except Exception as e:
        logger.warning(f"Failed to load plugin metadata from {manifest_file}: {e}")
        return None


def register_plugin_in_db(plugin_id: str, metadata: Optional[PluginMetadata]) -> None:
    """Înregistrează plugin-ul în baza de date"""
    with SessionLocal() as db:
        existing = db.get(Plugin, plugin_id)
        if existing:
            # Actualizăm metadata dacă există
            if metadata:
                existing.name = metadata.name
                existing.version = metadata.version
                existing.description = metadata.description
                existing.author = metadata.author
            db.commit()
        else:
            # Creare nouă
            plugin = Plugin(
                id=plugin_id,
                name=metadata.name if metadata else plugin_id.title(),
                version=metadata.version if metadata else "1.0.0",
                description=metadata.description if metadata else "",
                author=metadata.author if metadata else "",
                enabled=False,
                installed_at=datetime.now(timezone.utc)
            )
            db.add(plugin)
            db.commit()


def unregister_plugin_from_db(plugin_id: str) -> None:
    """Șterge plugin-ul și toate setările din baza de date"""
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        if plugin:
            db.delete(plugin)  # Cascade va șterge și setările
            db.commit()


def is_plugin_enabled(plugin_id: str) -> bool:
    """Verifică dacă un plugin este activat"""
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        return plugin.enabled if plugin else False


def set_plugin_enabled(plugin_id: str, enabled: bool) -> None:
    """Activează/dezactivează un plugin"""
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        if plugin:
            plugin.enabled = enabled
            db.commit()
        else:
            plugin_dir = PLUGINS_DIR / plugin_id
            metadata = load_plugin_metadata(plugin_dir)
            now = datetime.now(timezone.utc)
            plugin = Plugin(
                id=plugin_id,
                name=metadata.name if metadata else plugin_id.replace("_", " ").title(),
                version=metadata.version if metadata else "1.0.0",
                description=metadata.description if metadata else "",
                author=metadata.author if metadata else "",
                enabled=enabled,
                installed_at=now
            )
            db.add(plugin)
            db.commit()


def get_plugin_setting(plugin_id: str, key: str, default: str = "") -> str:
    """Obține o setare specifică pentru un plugin"""
    with SessionLocal() as db:
        setting = db.query(PluginSetting).filter(
            PluginSetting.plugin_id == plugin_id,
            PluginSetting.key == key
        ).first()
        return setting.value if setting else default


def set_plugin_setting(plugin_id: str, key: str, value: str) -> None:
    """Setează o valoare pentru un plugin"""
    with SessionLocal() as db:
        setting = db.query(PluginSetting).filter(
            PluginSetting.plugin_id == plugin_id,
            PluginSetting.key == key
        ).first()
        
        now = datetime.now(timezone.utc)
        if setting:
            setting.value = value
            setting.updated_at = now
        else:
            setting = PluginSetting(
                plugin_id=plugin_id,
                key=key,
                value=value,
                created_at=now,
                updated_at=now
            )
            db.add(setting)
        db.commit()


def get_plugin_settings(plugin_id: str) -> Dict[str, str]:
    """Obține toate setările pentru un plugin"""
    with SessionLocal() as db:
        settings = db.query(PluginSetting).filter(
            PluginSetting.plugin_id == plugin_id
        ).all()
        return {s.key: s.value for s in settings}


def set_plugin_settings(plugin_id: str, settings: Dict[str, str]) -> None:
    """Setează multiple valori pentru un plugin"""
    with SessionLocal() as db:
        for key, value in settings.items():
            setting = db.query(PluginSetting).filter(
                PluginSetting.plugin_id == plugin_id,
                PluginSetting.key == key
            ).first()
            
            now = datetime.now(timezone.utc)
            if setting:
                setting.value = value
                setting.updated_at = now
            else:
                setting = PluginSetting(
                    plugin_id=plugin_id,
                    key=key,
                    value=value,
                    created_at=now,
                    updated_at=now
                )
                db.add(setting)
        db.commit()


def clear_plugin_settings(plugin_id: str) -> None:
    """Șterge toate setările pentru un plugin"""
    with SessionLocal() as db:
        db.query(PluginSetting).filter(
            PluginSetting.plugin_id == plugin_id
        ).delete()
        db.commit()


def get_installed_plugins() -> List[Plugin]:
    """Obține lista de plugin-uri instalate din DB"""
    with SessionLocal() as db:
        return db.query(Plugin).order_by(Plugin.name).all()


def get_enabled_plugins() -> List[Plugin]:
    """Obține lista de plugin-uri active"""
    with SessionLocal() as db:
        return db.query(Plugin).filter(Plugin.enabled == True).order_by(Plugin.name).all()


def load_plugins_with_metadata(app: FastAPI) -> None:
    """Încarcă plugin-urile cu metadata și înregistrare în DB"""
    if not PLUGINS_DIR.is_dir():
        return
    
    for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith(("_", ".")) or "to_del" in plugin_dir.name or "bak" in plugin_dir.name:
            continue
        
        plugin_file = plugin_dir / "plugin.py"
        if not plugin_file.is_file():
            continue
        
        plugin_id = plugin_dir.name
        
        # Încărcăm metadata
        metadata = load_plugin_metadata(plugin_dir)
        
        # Înregistrăm în DB
        register_plugin_in_db(plugin_id, metadata)
        
        # Verificăm dacă e enabled
        if not is_plugin_enabled(plugin_id):
            logger.info(f"Plugin {plugin_id} is disabled, skipping load")
            continue
        
        # Încărcăm codul plugin-ului
        try:
            import importlib.util
            mod_name = f"site_plugin_{plugin_id}"
            spec = importlib.util.spec_from_file_location(mod_name, plugin_file)
            if spec is None or spec.loader is None:
                logger.warning("Plugin %s: nu pot încărca spec", plugin_id)
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            register = getattr(mod, "register", None)
            if not callable(register):
                logger.warning("Plugin %s: lipsește register(app)", plugin_id)
                continue
            
            # Apelăm register cu context suplimentar dacă e necesar
            if hasattr(register, "__code__") and register.__code__.co_argcount > 1:
                # Dacă register acceptă mai mulți parametri, trimitem și plugin_id
                register(app, plugin_id)
            else:
                register(app)
            
            top_bar_fn = getattr(mod, "render_admin_top_bar", None)
            if callable(top_bar_fn):
                from app.core.template_hooks import register_admin_top_bar
                register_admin_top_bar(top_bar_fn)

            logger.info("Plugin încărcat: %s", plugin_id)
        except Exception:
            logger.exception("Plugin %s: eroare la încărcare", plugin_id)


def list_installed_plugins():
    from app.core.plugin_package import list_installed_plugins as _list
    return _list()



def get_plugin_admin_context(plugin_id: str, db: Any = None, extra_context: dict[str, Any] | None = None) -> dict[str, Any]:
    from app.core.config import APP_DIR
    
    from app.core.i18n import get_site_default_locale
    
    plugins = get_installed_plugins()
    plugin = next((p for p in plugins if p.id == plugin_id), None)
    
    plugin_dir = APP_DIR / "plugins" / plugin_id
    metadata = load_plugin_metadata(plugin_dir)
    settings = get_plugin_settings(plugin_id)
    
    plugin_locales: dict[str, dict[str, Any]] = {}
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
                
    db_overrides: dict[str, dict[str, str]] = {}
    if db:
        try:
            from app.models.db_models import TranslationEntry
            from sqlalchemy import select
            db_entries = db.execute(
                select(TranslationEntry).where(TranslationEntry.key.like(f"plugins.{plugin_id}.%"))
            ).scalars().all()
            for entry in db_entries:
                loc_code = entry.locale_code
                clean_key = entry.key.replace(f"plugins.{plugin_id}.", "")
                if loc_code not in db_overrides:
                    db_overrides[loc_code] = {}
                db_overrides[loc_code][clean_key] = entry.value
        except Exception:
            pass

    def_loc = get_site_default_locale()
    sorted_locales = dict(sorted(plugin_locales.items(), key=lambda item: (0 if item[0] == def_loc else 1, item[0])))

    ctx: dict[str, Any] = {
        "plugin": plugin,
        "plugin_id": plugin_id,
        "metadata": metadata,
        "settings": settings,
        "settings_schema": metadata.settings if metadata else {},
        "plugin_locales": sorted_locales,
        "default_site_locale": def_loc,
        "plugin_db_overrides": db_overrides,
    }
    if extra_context:
        ctx.update(extra_context)
    return ctx
