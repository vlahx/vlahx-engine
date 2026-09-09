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
    """
    Instalează un plugin din zip în `plugins/<id>/`.
    Acceptă:
    - `plugins/<id>/plugin.py` (+ fișiere alăturate)
    - sau un singur folder la rădăcină `<id>/plugin.py`
    """
    with tempfile.TemporaryDirectory(prefix="plugin-upload-") as tmp:
        zpath = Path(tmp) / "plugin.zip"
        zpath.write_bytes(data)
        with ZipFile(zpath) as zipf:
            members = _zip_members(zipf)
            plugin_id: str | None = None
            mode: str = "plugins_root"

            for n in members:
                if n.startswith("plugins/") and n.endswith("/plugin.py"):
                    parts = n.split("/", 2)
                    if len(parts) >= 2 and parts[1]:
                        cand = safe_plugin_id(parts[1])
                        if cand:
                            plugin_id = cand
                            mode = "plugins_root"
                            break

            if not plugin_id:
                ignore = {"__macosx", ".ds_store"}
                tops: set[str] = set()
                for n in members:
                    if "/" in n:
                        top = n.split("/", 1)[0].strip()
                        if top and top.lower() not in ignore:
                            tops.add(top)
                candidates: list[str] = []
                for top in sorted(tops):
                    cand = safe_plugin_id(top)
                    if not cand:
                        continue
                    if any(m == f"{top}/plugin.py" for m in members):
                        candidates.append(cand)
                if len(candidates) == 1:
                    plugin_id = candidates[0]
                    mode = "id_root"
                elif len(candidates) > 1:
                    raise ValueError(
                        "Zip invalid: mai multe plugin-uri la rădăcină: "
                        + ", ".join(candidates[:8])
                    )

            if not plugin_id and any(m == "plugin.py" for m in members):
                try:
                    if "plugin.json" in members:
                        with zipf.open("plugin.json") as jf:
                            meta = json.loads(jf.read().decode("utf-8"))
                            cand = safe_plugin_id(meta.get("id")) or safe_plugin_id(meta.get("slug"))
                            if cand:
                                plugin_id = cand
                                mode = "root_flat"
                except Exception:
                    pass

            if not plugin_id:
                sample = ", ".join(members[:8]) if members else "(gol)"
                raise ValueError(
                    "Zip invalid: aștept `plugins/<id>/plugin.py` sau `<id>/plugin.py` sau `plugin.py`. "
                    f"Exemple: {sample}"
                )

            extract_root = Path(tmp) / "extract"
            extract_root.mkdir(parents=True, exist_ok=True)
            for n in members:
                if ".." in n or n.startswith("/") or n.startswith("\\"):
                    raise ValueError("Zip invalid (path traversal).")
                if mode == "plugins_root":
                    if not n.startswith(f"plugins/{plugin_id}/"):
                        continue
                    dest = extract_root / n
                elif mode == "root_flat":
                    dest = extract_root / "plugins" / plugin_id / n
                else:
                    if not n.startswith(f"{plugin_id}/"):
                        continue
                    rel = n[len(plugin_id) + 1 :]
                    dest = extract_root / "plugins" / plugin_id / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zipf.open(n) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)

            plugin_src = extract_root / "plugins" / plugin_id
            if not (plugin_src / "plugin.py").is_file():
                raise ValueError(
                    f"Lipsește `plugins/{plugin_id}/plugin.py` după extract."
                )

            dest_dir = APP_DIR / "plugins" / plugin_id
            if dest_dir.exists():
                if not overwrite:
                    raise ValueError(
                        "Pluginul există deja. Bifează „Suprascrie” ca să reinstalezi."
                    )
                shutil.rmtree(dest_dir)

            dest_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(plugin_src, dest_dir)

            # Auto-install plugin dependencies if requirements.txt exists in plugin zip
            req_file = dest_dir / "requirements.txt"
            if req_file.is_file():
                try:
                    import sys
                    import subprocess
                    import logging
                    logger.info(f"Auto-installing requirements for plugin `{plugin_id}` from {req_file}...")
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                        check=False
                    )

                    # Merge missing lines into root requirements.txt
                    root_req = PROJECT_ROOT / "requirements.txt"
                    if root_req.is_file():
                        root_content = root_req.read_text(encoding="utf-8")
                        root_lines = set(root_content.splitlines())
                        plugin_lines = req_file.read_text(encoding="utf-8").splitlines()
                        new_reqs = [
                            line.strip() for line in plugin_lines
                            if line.strip() and not line.strip().startswith("#") and line.strip() not in root_lines
                        ]
                        if new_reqs:
                            with open(root_req, "a", encoding="utf-8") as f:
                                f.write("\n" + "\n".join(new_reqs) + "\n")
                except Exception as ex:
                    logger.warning(f"Could not auto-install requirements for plugin `{plugin_id}`: {ex}")

            # Înregistrăm plugin-ul în baza de date
            from app.core.plugin_manager import load_plugin_metadata
            metadata = load_plugin_metadata(dest_dir)
            register_plugin_in_db(plugin_id, metadata)

            return plugin_id, f"Plugin `{plugin_id}` instalat și înregistrat în baza de date."


@dataclass(frozen=True)
class PluginInfo:
    id: str
    name: str
    description: str
    version: str | None


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
        if manifest.is_file():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    name = str(data.get("name") or pid).strip() or pid
                    description = str(data.get("description") or "").strip()
                    if data.get("version"):
                        version = str(data.get("version")).strip()
            except (OSError, json.JSONDecodeError):
                pass
        out.append(
            PluginInfo(id=pid, name=name, description=description, version=version)
        )
    return out
