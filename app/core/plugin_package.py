from __future__ import annotations

import logging
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

from app.core.config import APP_DIR, PROJECT_ROOT
from app.core.plugin_manager import register_plugin_in_db

logger = logging.getLogger(__name__)

_PLUGIN_ID_OK = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_-")
_PLUGIN_ID_RESERVED = frozenset(
    {"default", "static", "themes", "core", "templates", "admin", "api", "plugins"}
)


def safe_plugin_id(raw: str) -> str | None:
    s = (raw or "").strip().lower()
    if not s or s in _PLUGIN_ID_RESERVED:
        return None
    if any(ch not in _PLUGIN_ID_OK for ch in s):
        return None
    return s


def _zip_members(zipf: ZipFile) -> list[str]:
    return [n for n in zipf.namelist() if n and not n.endswith("/")]


def extract_plugin_zip(data: bytes, *, overwrite: bool) -> tuple[str, str]:
    with tempfile.TemporaryDirectory(prefix="plugin-upload-") as tmp:
        zpath = Path(tmp) / "plugin.zip"
        zpath.write_bytes(data)
        with ZipFile(zpath) as zipf:
            members = _zip_members(zipf)
            plugin_id: str | None = None
            mode: str = "plugins_root"

            for n in members:
                parts = Path(n).parts
                if len(parts) >= 3 and parts[0] == "plugins" and parts[2] == "plugin.py":
                    cand = safe_plugin_id(parts[1])
                    if cand:
                        plugin_id = cand
                        mode = "plugins_prefix"
                        break
                elif len(parts) >= 2 and parts[1] == "plugin.py":
                    cand = safe_plugin_id(parts[0])
                    if cand:
                        plugin_id = cand
                        mode = "single_folder"
                        break

            if not plugin_id:
                raise ValueError("Arhiva ZIP nu conține un plugin.py valid la nivel de plugin.")

            dest_dir = APP_DIR / "plugins" / plugin_id
            if dest_dir.exists() and not overwrite:
                raise FileExistsError(f"Plugin-ul '{plugin_id}' există deja.")

            tmp_extract = Path(tmp) / "out"
            tmp_extract.mkdir(parents=True, exist_ok=True)
            zipf.extractall(tmp_extract)

            if mode == "plugins_prefix":
                src_dir = tmp_extract / "plugins" / plugin_id
            else:
                src_dir = tmp_extract / plugin_id

            if not src_dir.is_dir() or not (src_dir / "plugin.py").is_file():
                raise ValueError("Eroare la extragerea structurii plugin-ului din ZIP.")

            dest_dir.parent.mkdir(parents=True, exist_ok=True)
            if dest_dir.exists() and overwrite:
                shutil.rmtree(dest_dir)

            shutil.copytree(src_dir, dest_dir)
            register_plugin_in_db(plugin_id)
            return plugin_id, f"Plugin-ul '{plugin_id}' a fost instalat cu succes."


@dataclass
class PluginInfo:
    id: str
    name: str
    description: str
    version: str | None
    vlahx_version: str | None = "2.0.0"
    is_compatible: bool = False
    badge_class: str = "bg-warning text-dark"
    badge_text: str = "⚠️ VlahX 2.0 (Migrare 3.0)"


def list_installed_plugins() -> list[PluginInfo]:
    root = APP_DIR / "plugins"
    out: list[PluginInfo] = []
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith(("_", ".")):
            continue
        if not (d / "plugin.py").is_file():
            continue
        pid = d.name
        manifest = d / "plugin.json"
        name = pid
        description = ""
        version = None
        vlahx_ver = "2.0.0"
        if manifest.is_file():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    name = str(data.get("name") or pid).strip() or pid
                    description = str(data.get("description") or "").strip()
                    if data.get("version"):
                        version = str(data.get("version")).strip()
                    vlahx_ver = str(data.get("vlahx_version") or data.get("min_core_version") or "2.0.0").strip()
            except (OSError, json.JSONDecodeError):
                pass

        is_comp = vlahx_ver.startswith("3.")
        b_class = "bg-success text-white" if is_comp else "bg-warning text-dark"
        b_text = f"🟢 VlahX {vlahx_ver} Compatibil" if is_comp else f"⚠️ VlahX {vlahx_ver} (Migrare 3.0)"

        out.append(
            PluginInfo(
                id=pid,
                name=name,
                description=description,
                version=version,
                vlahx_version=vlahx_ver,
                is_compatible=is_comp,
                badge_class=b_class,
                badge_text=b_text,
            )
        )
    return out
