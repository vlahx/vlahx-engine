from __future__ import annotations

"""
Hub evenimente sincrone (fără cozi): pluginurile se abonează cu ``subscribe``,
codul din nucleu sau pluginuri emite cu ``publish``.

Convenție nume: ``domeniu.verb``.

Evenimentele sunt extensibile și sunt definite de pluginurile care le emit.
"""

import logging
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)

_handlers: dict[str, list[Callable[..., Any]]] = defaultdict(list)


def clear_handlers() -> None:
    """La fiecare ``load_plugins`` — aceleași handler-e nu trebuie acumulate între două ``create_app``."""
    _handlers.clear()


def subscribe(event: str, handler: Callable[..., Any]) -> None:
    """Înregistrează un handler sincron; apelat la ``publish`` cu kwargs."""
    _handlers[event].append(handler)


def publish(event: str, **kwargs: Any) -> None:
    """Apelează toți handlerii pentru eveniment; erorile sunt logate, nu propagă."""
    for fn in list(_handlers.get(event, [])):
        try:
            fn(**kwargs)
        except Exception:
            logger.exception("Eroare în handler eveniment %r", event)
