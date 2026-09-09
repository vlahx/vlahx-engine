"""Upload imagini articol: JPEG; implicit crop centrat + resize la POST_IMAGE_OUTPUT_* (implicit 1200×630, raport OG).

Additional functionality: generate small thumbnails for preview in admin settings."""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageFile, ImageOps

from app.core.config import (
    get_post_image_crop_og,
    get_post_image_max_edge,
    get_post_image_output_height,
    get_post_image_output_width,
)

logger = logging.getLogger(__name__)

ImageFile.LOAD_TRUNCATED_IMAGES = True


DISPLAY_JPEG_QUALITY = 85


def _flatten_for_jpeg(img: Image.Image) -> Image.Image:
    """Convert image with transparency to RGB by pasting onto white background."""
    if img.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[3])
        return bg
    if img.mode == "P" and "transparency" in img.info:
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[3])
        return bg
    return img.convert("RGB")


def _safe_exif_transpose(img: Image.Image) -> Image.Image:
    """Transpose image based on EXIF data to ensure correct orientation."""
    try:
        return ImageOps.exif_transpose(img)
    except Exception:
        return img


def _encode_display_jpeg(img: Image.Image) -> bytes:
    """Encode image as JPEG with display quality settings."""
    buf = BytesIO()
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgb = _flatten_for_jpeg(img)
    else:
        rgb = img.convert("RGB")
    rgb.save(
        buf,
        format="JPEG",
        quality=DISPLAY_JPEG_QUALITY,
        optimize=True,
        progressive=True,
    )
    return buf.getvalue()


def _center_crop_to_target_aspect(im: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Crop centered to target aspect ratio (before resize to final dimensions)."""
    iw, ih = im.size
    if iw < 1 or ih < 1:
        return im
    ta = target_w / target_h
    sa = iw / ih
    if sa > ta:
        nw = max(1, int(round(ih * ta)))
        nh = ih
        x0 = max(0, (iw - nw) // 2)
        y0 = 0
        return im.crop((x0, y0, x0 + nw, y0 + nh))
    nw = iw
    nh = max(1, int(round(iw / ta)))
    x0 = 0
    y0 = max(0, (ih - nh) // 2)
    return im.crop((x0, y0, x0 + nw, y0 + nh))


def _resize_longest_edge(img: Image.Image, max_edge: int) -> Image.Image:
    """Resize image to max_edge by longest edge while preserving aspect ratio."""
    iw, ih = img.size
    if iw <= 0 or ih <= 0:
        return img
    if max_edge <= 0:
        return img

    if iw >= ih:
        if iw <= max_edge:
            return img.copy()
        ratio = max_edge / iw
    else:
        if ih <= max_edge:
            return img.copy()
        ratio = max_edge / ih

    new_width = max(1, int(round(iw * ratio)))
    new_height = max(1, int(round(ih * ratio)))
    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def _og_crop_and_resize(img: Image.Image, out_w: int, out_h: int) -> Image.Image:
    """Inner function: crop centered to OG aspect ratio, then resize exact to out_w×out_h."""
    work = img.copy()
    if work.mode in ("RGBA", "LA") or (
        work.mode == "P" and "transparency" in work.info
    ):
        work = _flatten_for_jpeg(work)
    else:
        work = work.convert("RGB")
    cropped = _center_crop_to_target_aspect(work, out_w, out_h)
    return cropped.resize((out_w, out_h), Image.Resampling.LANCZOS)


def generate_thumbnail_preview(
    image_data: BinaryIO,
    target_width: int = 80,
    target_height: int = None,
) -> tuple[bytes, str]:
    """
    Generate a small thumbnail for preview display (e.g., in admin settings).

    Args:
        image_data: The image file-like object (BytesIO or similar).
        target_width: Target width for thumbnail. Default 80px.
        target_height: Target height, if None then keep aspect ratio.

    Returns:
        Tuple of (jpeg_bytes, extension) - ready to be displayed as preview.
    """
    try:
        image_data.seek(0)
        with Image.open(image_data) as src:
            img = _safe_exif_transpose(src)
            img.load()

            # Determine target dimensions
            if target_height is None:
                target_height = int(target_width * (img.height / max(img.width, 1)))
            else:
                target_width = int(target_width * (img.width / max(img.height, 1)))

            # Resize to thumbnail size with high quality
            thumb = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

            # Encode as JPEG
            buf = BytesIO()
            if thumb.mode in ("RGBA", "LA") or (thumb.mode == "P" and "transparency" in thumb.info):
                rgb = _flatten_for_jpeg(thumb)
            else:
                rgb = thumb.convert("RGB")

            rgb.save(buf, format="JPEG", quality=DISPLAY_JPEG_QUALITY, optimize=True, progressive=True)
            jpeg_bytes = buf.getvalue()

        # Return JPEG bytes with .jpg extension (thumbnail is always saved as JPG)
        return jpeg_bytes, ".jpg"

    except Exception as e:
        logger.warning(f"Error generating thumbnail preview: {e}")
        return b"", ".jpg"


def process_post_upload(data: bytes, ext: str) -> tuple[bytes, str]:
    """
    O singură imagine pentru articol (JPEG).

    - Implicit (``POST_IMAGE_CROP_OG``): crop centrat la raport ``OUTPUT_WIDTH:OUTPUT_HEIGHT``
      (implicit 1200×630), apoi resize exact la acele dimensiuni.
    - Altfel: thumbnail în dreptunghi ``POST_IMAGE_MAX_EDGE``², păstrează raportul.

    GIF animat: returnează bytes originale + extensia originală.

    Args:
        data: Image bytes data.
        ext: File extension (e.g., '.jpg', '.png').

    Returns:
        Tuple of (processed_jpeg_bytes, output_extension).
    """
    ext = (ext or "").lower()
    if not ext.startswith("."):
        ext = f".{ext}"

    try:
        with Image.open(BytesIO(data)) as src:
            if ext == ".gif" and getattr(src, "n_frames", 1) > 1:
                return data, ext
            if (
                getattr(src, "format", None) == "MPO"
                and getattr(src, "n_frames", 1) > 0
            ):
                src.seek(0)

            img = _safe_exif_transpose(src)
            img.load()
            ow = get_post_image_output_width()
            oh = get_post_image_output_height()
            if get_post_image_crop_og() and ow > 0 and oh > 0:
                out = _og_crop_and_resize(img, ow, oh)
                return _encode_display_jpeg(out), ".jpg"

            disp = _resize_longest_edge(img, get_post_image_max_edge())
            return _encode_display_jpeg(disp), ".jpg"
    except Exception as e:
        logger.warning(
            "post_image: conversie JPEG eșuată (%s); păstrez fișierul original", e
        )
        return data, ext
