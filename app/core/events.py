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
    logger.warning(
        "EVENT DEBUG: subscribe event=%r handler=%r",
        event,
        handler,
    )
    _handlers[event].append(handler)


def publish(event: str, **kwargs: Any) -> None:
    logger.warning(
        "EVENT DEBUG: publish event=%r handlers=%r",
        event,
        _handlers.get(event, []),
    )

    for fn in list(_handlers.get(event, [])):
        try:
            fn(**kwargs)
        except Exception:
            logger.exception("Eroare în handler eveniment %r", event)
