from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import APP_DIR, PROJECT_ROOT

logger = logging.getLogger(__name__)

_SITE_UPLOADS_ROOT = (APP_DIR / "static" / "images" / "site_uploads").resolve()


def unlink_site_upload_file(public_path: str) -> bool:
    """
    Șterge fișierul de pe disc dacă calea publică e sub static/images/site_uploads/.
    Nu atinge fișierele din .env care trimit la alte directoare (ex. favicon.ico în static/).
    """
    raw = (public_path or "").strip()
    if not raw.startswith("/static/images/site_uploads/"):
        return False
    rel_fs = raw.lstrip("/")
    target = (APP_DIR / rel_fs).resolve()
    try:
        target.relative_to(_SITE_UPLOADS_ROOT)
    except ValueError:
        logger.warning("unlink_site_upload_file: rejected path outside site_uploads: %s", public_path)
        return False
    if not target.is_file():
        return False
    try:
        target.unlink()
        logger.info("Removed site upload: %s", target)
        return True
    except OSError as e:
        logger.warning("unlink_site_upload_file: could not remove %s: %s", target, e)
        return False
