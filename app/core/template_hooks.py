from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import Request

logger = logging.getLogger(__name__)

_post_article_footer: list[tuple[int, Callable[[Any, Request], str]]] = []
_post_header_meta: list[tuple[int, Callable[[Any, Request], str]]] = []
_admin_nav: list[tuple[int, Callable[[Request], str]]] = []
_admin_top_bar: list[tuple[int, Callable[[Request], str]]] = []

_footer_col1: list[tuple[int, Callable[[Request], str]]] = []
_footer_col2: list[tuple[int, Callable[[Request], str]]] = []
_footer_col3: list[tuple[int, Callable[[Request], str]]] = []
_footer_col4: list[tuple[int, Callable[[Request], str]]] = []
_footer_col5: list[tuple[int, Callable[[Request], str]]] = []
_footer_bottom: list[tuple[int, Callable[[Request], str]]] = []
_navbar_link: list[tuple[int, Callable[[Request], str]]] = []
_navbar_search: list[tuple[int, Callable[[Request], str]]] = []

_sidebar_top: list[tuple[int, Callable[[Request], str]]] = []
_sidebar_search: list[tuple[int, Callable[[Request], str]]] = []
_sidebar_widgets: list[tuple[int, Callable[[Request], str]]] = []
_sidebar_bottom: list[tuple[int, Callable[[Request], str]]] = []
_login_options: list[tuple[int, Callable[[Request], str]]] = []


def clear_post_article_footers() -> None:
    _post_article_footer.clear()
    _post_header_meta.clear()
    _admin_nav.clear()
    _admin_top_bar.clear()
    _footer_col1.clear()
    _footer_col2.clear()
    _footer_col3.clear()
    _footer_col4.clear()
    _footer_col5.clear()
    _footer_bottom.clear()
    _navbar_link.clear()
    _navbar_search.clear()
    _sidebar_top.clear()
    _sidebar_search.clear()
    _sidebar_widgets.clear()
    _sidebar_bottom.clear()
    _login_options.clear()


def register_navbar_link(renderer: Callable[[Request], str], *, order: int = 100) -> None:
    _navbar_link.append((order, renderer))
    _navbar_link.sort(key=lambda t: t[0])


def render_navbar_links(request: Request) -> str:
    parts = []
    for _, fn in _navbar_link:
        try:
            c = (fn(request) or "").strip()
            if c: parts.append(c)
        except Exception:
            logger.exception("navbar_link renderer failed")
    return "\n".join(parts)


def register_post_article_footer(
    renderer: Callable[[Any, Request], str],
    *,
    order: int = 100,
) -> None:
    _post_article_footer.append((order, renderer))
    _post_article_footer.sort(key=lambda t: t[0])


def render_post_article_footers(post: Any, request: Request) -> str:
    parts: list[str] = []
    for _, fn in _post_article_footer:
        try:
            chunk = (fn(post, request) or "").strip()
            if chunk:
                parts.append(chunk)
        except Exception:
            logger.exception("post_article_footer renderer failed")
    return "\n".join(parts)


def register_post_header_meta(
    renderer: Callable[[Any, Request], str],
    *,
    order: int = 100,
) -> None:
    _post_header_meta.append((order, renderer))
    _post_header_meta.sort(key=lambda t: t[0])


def render_post_header_metas(post: Any, request: Request) -> str:
    parts: list[str] = []
    for _, fn in _post_header_meta:
        try:
            chunk = (fn(post, request) or "").strip()
            if chunk:
                parts.append(chunk)
        except Exception:
            logger.exception("post_header_meta renderer failed")
    return " ".join(parts)


def register_admin_nav(
    renderer: Callable[[Request], str],
    *,
    order: int = 100,
) -> None:
    if any(r is renderer or r == renderer for _, r in _admin_nav):
        return
    _admin_nav.append((order, renderer))
    _admin_nav.sort(key=lambda t: t[0])


def render_admin_navs(request: Request) -> str:
    parts: list[str] = []
    for _, fn in _admin_nav:
        try:
            chunk = (fn(request) or "").strip()
            if chunk:
                parts.append(chunk)
        except Exception:
            logger.exception("admin_nav renderer failed")
    return "\n".join(parts)


def register_admin_top_bar(
    renderer: Callable[[Request], str],
    *,
    order: int = 100,
) -> None:
    if any(r is renderer or r == renderer for _, r in _admin_top_bar):
        return
    _admin_top_bar.append((order, renderer))
    _admin_top_bar.sort(key=lambda t: t[0])


def render_admin_top_bars(request: Request) -> str:
    parts: list[str] = []
    for _, fn in _admin_top_bar:
        try:
            chunk = (fn(request) or "").strip()
            if chunk:
                parts.append(chunk)
        except Exception:
            logger.exception("admin_top_bar renderer failed")
    return "\n".join(parts)


# Footer Column Hooks
def register_footer_col1(renderer: Callable[[Request], str], *, order: int = 100) -> None:
    _footer_col1.append((order, renderer))
    _footer_col1.sort(key=lambda t: t[0])

def render_footer_col1(request: Request) -> str:
    parts = []
    for _, fn in _footer_col1:
        try:
            c = (fn(request) or "").strip()
            if c: parts.append(c)
        except Exception:
            logger.exception("footer_col1 renderer failed")
    return "\n".join(parts)

def register_footer_col2(renderer: Callable[[Request], str], *, order: int = 100) -> None:
    _footer_col2.append((order, renderer))
    _footer_col2.sort(key=lambda t: t[0])

def render_footer_col2(request: Request) -> str:
    parts = []
    for _, fn in _footer_col2:
        try:
            c = (fn(request) or "").strip()
            if c: parts.append(c)
        except Exception:
            logger.exception("footer_col2 renderer failed")
    return "\n".join(parts)

def register_footer_col3(renderer: Callable[[Request], str], *, order: int = 100) -> None:
    _footer_col3.append((order, renderer))
    _footer_col3.sort(key=lambda t: t[0])

def render_footer_col3(request: Request) -> str:
    parts = []
    for _, fn in _footer_col3:
        try:
            c = (fn(request) or "").strip()
            if c: parts.append(c)
        except Exception:
            logger.exception("footer_col3 renderer failed")
    return "\n".join(parts)

def register_footer_col4(renderer: Callable[[Request], str], *, order: int = 100) -> None:
    _footer_col4.append((order, renderer))
    _footer_col4.sort(key=lambda t: t[0])

def render_footer_col4(request: Request) -> str:
    parts = []
    for _, fn in _footer_col4:
        try:
            c = (fn(request) or "").strip()
            if c: parts.append(c)
        except Exception:
            logger.exception("footer_col4 renderer failed")
    return "\n".join(parts)

def register_footer_col5(renderer: Callable[[Request], str], *, order: int = 100) -> None:
    _footer_col5.append((order, renderer))
    _footer_col5.sort(key=lambda t: t[0])

def render_footer_col5(request: Request) -> str:
    parts = []
    for _, fn in _footer_col5:
        try:
            c = (fn(request) or "").strip()
            if c: parts.append(c)
        except Exception:
            logger.exception("footer_col5 renderer failed")
    return "\n".join(parts)

def register_footer_bottom(renderer: Callable[[Request], str], *, order: int = 100) -> None:
    _footer_bottom.append((order, renderer))
    _footer_bottom.sort(key=lambda t: t[0])

def render_footer_bottom(request: Request) -> str:
    parts = []
    for _, fn in _footer_bottom:
        try:
            c = (fn(request) or "").strip()
            if c: parts.append(c)
        except Exception:
            logger.exception("footer_bottom renderer failed")
    return "\n".join(parts)


# Navbar Search Hook
def register_navbar_search(renderer: Callable[[Request], str], *, order: int = 100) -> None:
    _navbar_search.append((order, renderer))
    _navbar_search.sort(key=lambda t: t[0])

def render_navbar_search(request: Request) -> str:
    parts = []
    for _, fn in _navbar_search:
        try:
            c = (fn(request) or "").strip()
            if c: parts.append(c)
        except Exception:
            logger.exception("navbar_search renderer failed")
    return "\n".join(parts)


# Sidebar Hooks
def register_sidebar_top(renderer: Callable[[Request], str], *, order: int = 100) -> None:
    _sidebar_top.append((order, renderer))
    _sidebar_top.sort(key=lambda t: t[0])

def render_sidebar_top(request: Request) -> str:
    parts = []
    for _, fn in _sidebar_top:
        try:
            c = (fn(request) or "").strip()
            if c: parts.append(c)
        except Exception:
            logger.exception("sidebar_top renderer failed")
    return "\n".join(parts)


def register_sidebar_search(renderer: Callable[[Request], str], *, order: int = 100) -> None:
    _sidebar_search.append((order, renderer))
    _sidebar_search.sort(key=lambda t: t[0])

def render_sidebar_search(request: Request) -> str:
    parts = []
    for _, fn in _sidebar_search:
        try:
            c = (fn(request) or "").strip()
            if c: parts.append(c)
        except Exception:
            logger.exception("sidebar_search renderer failed")
    return "\n".join(parts)


def register_sidebar_widgets(renderer: Callable[[Request], str], *, order: int = 100) -> None:
    _sidebar_widgets.append((order, renderer))
    _sidebar_widgets.sort(key=lambda t: t[0])

def render_sidebar_widgets(request: Request) -> str:
    parts = []
    for _, fn in _sidebar_widgets:
        try:
            c = (fn(request) or "").strip()
            if c: parts.append(c)
        except Exception:
            logger.exception("sidebar_widgets renderer failed")
    return "\n".join(parts)


def register_sidebar_bottom(renderer: Callable[[Request], str], *, order: int = 100) -> None:
    _sidebar_bottom.append((order, renderer))
    _sidebar_bottom.sort(key=lambda t: t[0])

def render_sidebar_bottom(request: Request) -> str:
    parts = []
    for _, fn in _sidebar_bottom:
        try:
            c = (fn(request) or "").strip()
            if c: parts.append(c)
        except Exception:
            logger.exception("sidebar_bottom renderer failed")
    return "\n".join(parts)


def register_login_options(renderer: Callable[[Request], str], *, order: int = 100) -> None:
    _login_options.append((order, renderer))
    _login_options.sort(key=lambda t: t[0])


def render_login_options(request: Request) -> str:
    parts = []
    for _, fn in _login_options:
        try:
            c = (fn(request) or "").strip()
            if c: parts.append(c)
        except Exception:
            logger.exception("login_options renderer failed")
    return "\n".join(parts)


_sitemap_providers: list[tuple[int, Callable[[Request], list[dict]]]] = []

def register_sitemap_provider(
    provider: Callable[[Request], list[dict]],
    *,
    order: int = 100,
) -> None:
    if any(p is provider or p == provider for _, p in _sitemap_providers):
        return
    _sitemap_providers.append((order, provider))
    _sitemap_providers.sort(key=lambda t: t[0])

def collect_sitemap_entries(request: Request) -> list[dict]:
    entries: list[dict] = []
    for _, fn in _sitemap_providers:
        try:
            res = fn(request)
            if res and isinstance(res, list):
                entries.extend(res)
        except Exception as e:
            logger.exception("sitemap_provider failed: %s", e)
    return entries
