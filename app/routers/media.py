from __future__ import annotations

from PIL import Image, ImageOps

from datetime import datetime, timezone
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import APP_DIR, PROJECT_ROOT
from app.models.db_models import MediaFile, User
from app.utils.auth import get_current_user_from_request, login_required, user_has_role
from app.utils.db import get_db

logger = logging.getLogger(__name__)


def crop_and_resize_image(input_file_path: Path, target_w: int = 1200, target_h: int = 630, quality: int = 85) -> Path:
    try:
        with Image.open(input_file_path) as img:
            fmt = (img.format or "JPEG").upper()
            if fmt in ("SVG", "PDF"):
                return input_file_path
            if fmt == "GIF" and getattr(img, "n_frames", 1) > 1:
                return input_file_path

            img = ImageOps.exif_transpose(img)

            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                rgba = img.convert("RGBA")
                bg.paste(rgba, mask=rgba.split()[3])
                img = bg
            else:
                img = img.convert("RGB")

            target_ratio = target_w / target_h
            orig_w, orig_h = img.size
            orig_ratio = orig_w / orig_h

            if orig_ratio > target_ratio:
                new_w = int(orig_h * target_ratio)
                left = (orig_w - new_w) // 2
                top = 0
                right = left + new_w
                bottom = orig_h
            else:
                new_h = int(orig_w / target_ratio)
                left = 0
                top = (orig_h - new_h) // 2
                right = orig_w
                bottom = top + new_h

            img_cropped = img.crop((left, top, right, bottom))
            img_resized = img_cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)

            target_jpg_path = input_file_path.with_suffix(".jpg")
            img_resized.save(target_jpg_path, format="JPEG", quality=quality, optimize=True, progressive=True)

            if target_jpg_path != input_file_path and input_file_path.exists() and target_jpg_path.exists():
                try:
                    input_file_path.unlink()
                except Exception:
                    pass

            return target_jpg_path
    except Exception as e:
        logger.warning(f"Error cropping image {input_file_path}: {e}")
        return input_file_path

def process_and_optimize_image(input_file_path: Path, max_dimension: int = 1920, quality: int = 85) -> Path:
    ext = input_file_path.suffix.lower()
    if ext in (".zip", ".rar", ".7z", ".pdf", ".gz", ".tar", ".doc", ".docx", ".xls", ".xlsx"):
        return input_file_path
    try:
        with Image.open(input_file_path) as img:
            fmt = (img.format or "").upper()
            if fmt in ("SVG", "PDF"):
                return input_file_path
            if fmt == "GIF" and getattr(img, "n_frames", 1) > 1:
                return input_file_path

            img = ImageOps.exif_transpose(img)

            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                rgba = img.convert("RGBA")
                bg.paste(rgba, mask=rgba.split()[3])
                img = bg
            else:
                img = img.convert("RGB")

            width, height = img.size
            if width > max_dimension or height > max_dimension:
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

            target_jpg_path = input_file_path.with_suffix(".jpg")
            img.save(target_jpg_path, format="JPEG", quality=quality, optimize=True, progressive=True)

            if target_jpg_path != input_file_path and input_file_path.exists() and target_jpg_path.exists():
                try:
                    input_file_path.unlink()
                except Exception:
                    pass

            return target_jpg_path
    except Exception as e:
        logger.warning(f"Pillow optimization skipped/failed for {input_file_path}: {e}")
        return input_file_path

router = APIRouter(tags=["media"])


@router.get("/api/media/files")
@login_required
async def api_list_media_files(
    request: Request,
    category: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    query = select(MediaFile)
    if not user_has_role(user, "admin", "editor"):
        query = query.where(MediaFile.user_id == user.id)

    if category and category.strip().lower() != "all":
        query = query.where(MediaFile.category == category.strip().lower())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(MediaFile.filename.ilike(term) | MediaFile.alt_text.ilike(term))

    query = query.order_by(MediaFile.created_at.desc())
    records = db.scalars(query).all()

    res = []
    for r in records:
        res.append(
            {
                "id": r.id,
                "user_id": r.user_id,
                "filename": r.filename,
                "file_path": r.file_path,
                "file_url": r.file_url,
                "file_size": r.file_size,
                "mime_type": r.mime_type,
                "alt_text": r.alt_text or r.filename,
                "category": r.category,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return JSONResponse({"ok": True, "files": res})


@router.post("/api/media/upload")
@login_required
async def api_upload_media(
    request: Request,
    category: str = Form("general"),
    upload_files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    cat_clean = category.strip().lower() if category else "general"
    if cat_clean not in ("blog", "shop", "general"):
        cat_clean = "general"

    user_media_dir = APP_DIR / "static" / "uploads" / "users" / str(user.id) / cat_clean
    user_media_dir.mkdir(parents=True, exist_ok=True)

    saved_records = []
    now = datetime.now(timezone.utc)
    ts = int(time.time())

    for idx, uf in enumerate(upload_files):
        if not uf.filename:
            continue

        raw_name = Path(uf.filename).name.replace(" ", "_")
        safe_filename = f"{ts}_{idx}_{raw_name}"
        dest_file = user_media_dir / safe_filename

        with dest_file.open("wb") as buffer:
            shutil.copyfileobj(uf.file, buffer)

        if cat_clean in ("blog", "shop"):
            dest_file = crop_and_resize_image(dest_file, target_w=1200, target_h=630)
        else:
            dest_file = process_and_optimize_image(dest_file)

        final_filename = dest_file.name
        file_size = dest_file.stat().st_size
        rel_url = f"/static/uploads/users/{user.id}/{cat_clean}/{final_filename}"
        rel_path = f"static/uploads/users/{user.id}/{cat_clean}/{final_filename}"

        m_record = MediaFile(
            user_id=user.id,
            filename=final_filename,
            file_path=rel_path,
            file_url=rel_url,
            file_size=file_size,
            mime_type="image/jpeg" if final_filename.endswith(".jpg") else uf.content_type,
            alt_text=uf.filename.rsplit(".", 1)[0].replace("_", " "),
            category=cat_clean,
            created_at=now,
        )
        db.add(m_record)
        db.commit()
        db.refresh(m_record)

        saved_records.append(
            {
                "id": m_record.id,
                "user_id": m_record.user_id,
                "filename": m_record.filename,
                "file_url": m_record.file_url,
                "file_size": m_record.file_size,
                "mime_type": m_record.mime_type,
                "alt_text": m_record.alt_text,
                "category": m_record.category,
                "created_at": m_record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    return JSONResponse({"ok": True, "files": saved_records})


@router.post("/api/media/delete")
@login_required
async def api_delete_media(
    request: Request,
    file_id: int = Form(...),
    db: Session = Depends(get_db),
):
    user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    media = db.execute(select(MediaFile).where(MediaFile.id == file_id)).scalar_one_or_none()
    if not media:
        return JSONResponse({"error": "File not found"}, status_code=404)

    if media.user_id != user.id and not user_has_role(user, "admin"):
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    if media.file_url and media.file_url.startswith("/static/"):
        rel_p = media.file_url.lstrip("/")
        phys = APP_DIR / rel_p
        if phys.is_file():
            try:
                phys.unlink()
            except Exception as e:
                logger.warning(f"Error unlinking {phys}: {e}")

    db.delete(media)
    db.commit()

    return JSONResponse({"ok": True, "deleted_id": file_id})


@router.post("/api/media/crop")
@login_required
async def api_crop_media(
    request: Request,
    file_id: int = Form(...),
    preset: str = Form("og"),
    width: int = Form(1200),
    height: int = Form(630),
    db: Session = Depends(get_db),
):
    user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    media = db.execute(select(MediaFile).where(MediaFile.id == file_id)).scalar_one_or_none()
    if not media:
        return JSONResponse({"error": "File not found"}, status_code=404)

    if media.user_id != user.id and not user_has_role(user, "admin"):
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    if preset == "og":
        target_w, target_h = 1200, 630
    elif preset == "square":
        target_w, target_h = 500, 500
    else:
        target_w = max(100, min(3840, width))
        target_h = max(100, min(3840, height))

    rel_p = media.file_url.lstrip("/")
    phys = APP_DIR / rel_p
    if not phys.is_file():
        return JSONResponse({"error": "Physical file missing"}, status_code=404)

    ok = crop_and_resize_image(phys, target_w, target_h)
    if ok:
        media.file_size = phys.stat().st_size
        db.commit()
        db.refresh(media)
        return JSONResponse({
            "ok": True,
            "file": {
                "id": media.id,
                "file_url": media.file_url,
                "file_size": media.file_size,
                "width": target_w,
                "height": target_h
            }
        })
    else:
        return JSONResponse({"error": "Error processing image crop"}, status_code=500)
