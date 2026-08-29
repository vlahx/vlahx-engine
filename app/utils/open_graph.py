"""Open Graph — URL simplu pentru og:image (fișier static + opțional PNG/JPEG de post)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from app.core.config import (
    get_og_card_image_path,
    get_post_image_crop_og,
    get_post_image_output_height,
    get_post_image_output_width,
    get_public_site_url,
)

OG_DESCRIPTION_MAX_CHARS = 300


def public_site_origin(request=None) -> str:
    """Originea absolută (scheme + host, fără slash final). Respectă HTTPS prin Reverse Proxy."""
    url = get_public_site_url()
    if url and "camionagiul" not in url:
        return url.rstrip("/")
    if request is not None and hasattr(request, "base_url"):
        headers = getattr(request, "headers", {})
        proto = headers.get("x-forwarded-proto", "").strip().lower()
        host = headers.get("x-forwarded-host") or headers.get("host") or ""
        host = str(host).split(",")[0].strip()

        # Pentru domeniu public sau proxy cu https
        if proto == "https" or (host and not host.startswith("127.") and not host.startswith("localhost") and not host.startswith("192.168.")):
            scheme = "https"
        else:
            scheme = str(request.base_url.scheme or "http")

        if host:
            return f"{scheme}://{host}".rstrip("/")

        base_str = str(request.base_url).rstrip("/")
        if scheme == "https" and base_str.startswith("http://"):
            base_str = "https://" + base_str[7:]
        return base_str
    return "https://vlahx.org"


def truncate_og_description(text: str, max_chars: int = OG_DESCRIPTION_MAX_CHARS) -> str:
    s = " ".join((text or "").split())
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1].rstrip() + "…"


def _card_rel() -> str:
    p = (get_og_card_image_path() or "").strip()
    return p if p.startswith("/") else f"/{p}" if p else ""


# Extensii acceptate în URL (fără verificare pe disc — fișierul poate fi servit de nginx/volume).
_OG_RASTER_SUFFIXES = frozenset({".png", ".jpg", ".jpeg"})

# Upload-uri articol — mereu același URL canonic (PUBLIC_SITE_URL + path), nu host din TinyMCE (localhost etc.).
_POST_IMAGES_PREFIX = "/static/images/post_images/"


def _url_path_for_suffix(url: str) -> str:
    """Path fără query/fragment, pentru extensie."""
    p = urlparse(url)
    return (p.path or "").lower()


def _is_og_raster_url(url: str) -> bool:
    return Path(_url_path_for_suffix(url)).suffix in _OG_RASTER_SUFFIXES


def _is_og_raster_site_path(rel: str) -> bool:
    r = (rel or "").strip()
    if not r.startswith("/"):
        r = f"/{r}"
    return Path(r.split("?", 1)[0].lower()).suffix in _OG_RASTER_SUFFIXES


def _canonical_post_images_og_url(base: str, url_or_rel: str) -> str:
    """
    - ``/static/images/post_images/...``: URL canonic ``{base}/static/images/post_images/...``
      (dacă în HTML era ``http://127.0.0.1:8000/...`` sau alt host local, îl înlocuim cu domeniul public).
    - Alte căi ``/static/...`` relative din HTML: tot ``{base}`` + path, ca ``og:image`` să fie URL absolut.
    - URL-uri ``https`` spre alte domenii: neschimbate.
    """
    b = (base or "").rstrip("/")
    s = (url_or_rel or "").strip()
    if not b or not s:
        return s
    if s.startswith("//"):
        s = f"https:{s}"
    base_host = (urlparse(b).hostname or "").lower()
    path: str
    query = ""
    abs_in: str | None = None
    if s.startswith(("http://", "https://")):
        abs_in = s
        p = urlparse(s)
        path = p.path or ""
        if p.query:
            query = f"?{p.query}"
    else:
        path = s.split("?", 1)[0]
        if "?" in s:
            query = "?" + s.split("?", 1)[1]
        if not path.startswith("/"):
            path = f"/{path}"

    post_prefix = _POST_IMAGES_PREFIX.lower()
    if path.lower().startswith(post_prefix):
        if abs_in:
            h = (urlparse(abs_in).hostname or "").lower()
            if h == base_host or h in ("localhost", "127.0.0.1"):
                return f"{b}{path}{query}"
            return abs_in
        return f"{b}{path}{query}"

    if not abs_in and path.startswith("/") and _is_og_raster_site_path(path):
        return f"{b}{path}{query}"
    return abs_in or s


def resolve_og_image_url(base_url: str, post_image_src: str | None) -> tuple[str | None, bool]:
    """
    URL absolut pentru og:image / twitter:image.

    - Dacă articolul are .png / .jpg / .jpeg (cale absolută pe site sau URL https), construim URL-ul.
      Nu verificăm ``Path.is_file()`` — în producție staticul e adesea în afara ``PROJECT_ROOT`` (Docker etc.).
    - Altfel: ``OG_CARD_IMAGE_PATH`` (PNG/JPEG card, de obicei ~1200×630).

    Al doilea element: ``True`` = card static → meta 1200×630; ``False`` = poză articol
    (cu ``POST_IMAGE_CROP_OG``, meta width/height = ``POST_IMAGE_OUTPUT_*`` pentru .jpg din post_images).
    """
    root = (base_url or "").rstrip("/")
    if not root:
        return None, False
    card_rel = _card_rel()
    card_abs = f"{root}{card_rel}" if card_rel else None

    if post_image_src:
        s = str(post_image_src).strip()
        if s.startswith(("http://", "https://")) and _is_og_raster_url(s):
            return _canonical_post_images_og_url(root, s), False
        if s.startswith("//"):
            full = f"https:{s}"
            if _is_og_raster_url(full):
                return _canonical_post_images_og_url(root, full), False
        rel = s if s.startswith("/") else f"/{s}"
        if _is_og_raster_site_path(rel):
            return _canonical_post_images_og_url(root, rel), False

    return card_abs, True


def og_image_meta_for_url(
    base_url: str,
    seo_image: str | None,
    *,
    is_card: bool,
) -> dict[str, str | int | None]:
    out: dict[str, str | int | None] = {
        "og_image_width": None,
        "og_image_height": None,
        "og_image_type": None,
    }
    if not seo_image:
        return out
    if is_card:
        out["og_image_width"] = 1200
        out["og_image_height"] = 630
    elif get_post_image_crop_og():
        pth = (urlparse(seo_image).path or "").lower()
        if pth.startswith(_POST_IMAGES_PREFIX.lower()) and pth.endswith(".jpg"):
            out["og_image_width"] = get_post_image_output_width()
            out["og_image_height"] = get_post_image_output_height()
    ext = Path(urlparse(seo_image).path).suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
    }.get(ext)
    if mime:
        out["og_image_type"] = mime
    return out
