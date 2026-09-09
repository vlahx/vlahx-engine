from __future__ import annotations

import logging

from fastapi import FastAPI

from app.core import events, template_hooks
from app.core.plugin_manager import load_plugins_with_metadata

logger = logging.getLogger(__name__)


def load_plugins(app: FastAPI) -> None:
    """
    Încarcă plugin-uri folosind noul sistem de management.
    Curăță hook-urile și evenimentele, apoi încarcă plugin-urile active.
    """
    template_hooks.clear_post_article_footers()
    events.clear_handlers()

    load_plugins_with_metadata(app)
