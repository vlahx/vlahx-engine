from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import APP_DIR, PROJECT_ROOT
from app.models.db_models import Category as CategoryModel
from app.models.db_models import Post as PostModel
from app.models.db_models import PostTranslation as PostTranslationModel
from app.models.db_models import User as UserModel

logger = logging.getLogger(__name__)

_POST_IMAGE_PREFIX = "/static/images/post_images/"
_SLUG_RE = re.compile(r"[^a-z0-9-]+")
_IMG_SRC_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)
_IMG_TAG_SRC_RE = re.compile(r"(<img[^>]+src=[\"']([^\"']+)[\"'][^>]*>)", re.IGNORECASE)


def _clean_optional_image_url(url: str | None) -> str | None:
    """Înlătură gol / placeholder — evită ``<img src="None">`` → browser cere ``GET /None`` de pe ``/admin``."""
    if url is None:
        return None
    t = str(url).strip()
    if not t or t.lower() in ("none", "null", "undefined"):
        return None
    return t


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = value.replace("_", "-").replace(" ", "-")
    value = _SLUG_RE.sub("-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "post"


def extract_images_from_html(content_html: str) -> list[str]:
    return _IMG_SRC_RE.findall(content_html or "")


def _strip_missing_local_post_images(content_html: str) -> str:
    """
    Elimină <img> care pointează la /static/images/post_images/* dar fișierul nu există.
    Asta previne request-uri 404 rămase din configurări vechi (TinyMCE first-image, etc.).
    """
    html = content_html or ""
    if not html:
        return html

    def repl(match: re.Match[str]) -> str:
        tag = match.group(1)
        src = (match.group(2) or "").strip()
        path = _resolve_local_post_image_path(src)
        if path and not path.is_file():
            return ""
        return tag

    return _IMG_TAG_SRC_RE.sub(repl, html)


def post_preview_image_src(post: PostView) -> str | None:
    """Pentru OG: hero_image_url dacă există, altfel image_url sau primul <img src> din conținut."""
    if post.hero_image_url and str(post.hero_image_url).strip():
        return str(post.hero_image_url).strip()
    if post.image_url and str(post.image_url).strip():
        return str(post.image_url).strip()
    for u in extract_images_from_html(post.content_html):
        c = _clean_optional_image_url(u)
        if c:
            return c
    return None


@dataclass(frozen=True)
class CategoryView:
    name: str
    slug: str
    depth: int = 0
    # Rând în ``categories``; None pentru etichete deduse doar din postări (fără rând în DB).
    db_id: int | None = None
    description: str | None = ""
    translations_json: str | None = "{}"


def _resolve_author_info(db: Session, author_id: int | None) -> tuple[int | None, str | None, str | None, str | None]:
    if not author_id:
        return (None, None, None, None)
    from app.models.db_models import User
    u = db.get(User, author_id)
    if not u:
        return (author_id, None, None, None)
    name_parts = [u.first_name, u.last_name]
    full_name = " ".join([p for p in name_parts if p]).strip()
    display_name = full_name if full_name else (u.username or f"User #{u.id}")
    return (u.id, display_name, u.username, u.image_url)


@dataclass(frozen=True)
class PostView:
    slug: str
    title: str
    excerpt: str
    content_html: str
    published_at: datetime | None
    id: int | None = None
    category: str | None = None
    draft: bool = False
    hero_image_url: str | None = None
    image_url: str | None = None
    images_url: list[str] | None = None
    author_id: int | None = None
    author_name: str | None = None
    author_username: str | None = None
    author_avatar: str | None = None
    meta_keywords: str | None = None

    @property
    def published_at_utc(self) -> datetime:
        if not self.published_at:
            return datetime.now(timezone.utc)
        dt = self.published_at
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)


def _category_filter_name(db: Session, category: str | None) -> str | None:
    if not category:
        return None
    category_value = category.strip()
    if not category_value:
        return None

    norm_slug = slugify(category_value)

    stmt = select(CategoryModel).where(
        (CategoryModel.slug == norm_slug)
        | (func.lower(CategoryModel.name) == category_value.lower())
    )
    category_row = db.execute(stmt).scalars().first()
    if category_row:
        return category_row.name

    distinct_cats = db.execute(
        select(func.distinct(PostModel.category)).where(PostModel.category != None)
    ).scalars().all()

    for cat_name in distinct_cats:
        if cat_name and (cat_name.lower() == category_value.lower() or slugify(cat_name) == norm_slug):
            return cat_name

    return category_value


def list_posts(
    db: Session,
    *,
    q: str | None = None,
    include_drafts: bool = False,
    category: str | None = None,
    author: str | None = None,
    locale: str | None = None,
    exclude_static: bool = True,
) -> list[PostView]:
    stmt = select(PostModel)
    if not include_drafts:
        stmt = stmt.where(PostModel.draft == False)  # noqa: E712
    if category:
        category_name = _category_filter_name(db, category)
        if category_name:
            stmt = stmt.where((func.lower(PostModel.category) == func.lower(category_name)) | (PostModel.category == category_name))
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        trans_subq = (
            select(PostTranslationModel.post_id)
            .where(
                func.lower(PostTranslationModel.title).like(term)
                | func.lower(PostTranslationModel.excerpt).like(term)
                | func.lower(PostTranslationModel.content_html).like(term)
            )
        )
        stmt = stmt.where(
            func.lower(PostModel.title).like(term)
            | func.lower(PostModel.excerpt).like(term)
            | func.lower(PostModel.content_html).like(term)
            | func.lower(PostModel.slug).like(term)
            | PostModel.id.in_(trans_subq)
        )
    sort_ts = func.coalesce(PostModel.published_at, PostModel.created_at)
    stmt = stmt.order_by(sort_ts.desc(), PostModel.id.desc())

    rows = db.execute(stmt).scalars().all()
    results: list[PostView] = []
    from app.core.config import is_static_page_slug
    for p in rows:
        if not include_drafts and exclude_static and is_static_page_slug(p.slug):
            continue
        title = p.title
        excerpt = p.excerpt or ""
        content_html = p.content_html
        if locale:
            t_stmt = select(PostTranslationModel).where(
                (PostTranslationModel.post_id == p.id)
                & (PostTranslationModel.locale_code == locale)
            )
            trans = db.execute(t_stmt).scalars().first()
            if trans:
                if trans.title and trans.title.strip():
                    title = trans.title.strip()
                if trans.excerpt and trans.excerpt.strip():
                    excerpt = trans.excerpt.strip()
                if trans.content_html and trans.content_html.strip():
                    content_html = trans.content_html.strip()
        aid, aname, auser, aavatar = _resolve_author_info(db, p.author_id)
        results.append(
            PostView(
                id=p.id,
                slug=p.slug,
                title=title,
                excerpt=excerpt,
                category=p.category,
                content_html=_strip_missing_local_post_images(content_html),
                published_at=p.published_at,
                draft=bool(p.draft),
                hero_image_url=_clean_optional_image_url(p.hero_image_url),
                image_url=_clean_optional_image_url(p.image_url),
                images_url=json.loads(p.images_url_json) if p.images_url_json else None,
                author_id=aid,
                author_name=aname,
                author_username=auser,
                author_avatar=aavatar,
            )
        )
    return results


def get_post(db: Session, slug: str, locale: str | None = None) -> PostView | None:
    stmt = select(PostModel).where(PostModel.slug == slug)
    row = db.execute(stmt).scalars().first()
    if not row:
        return None

    title = row.title
    excerpt = row.excerpt or ""
    content_html = row.content_html
    meta_keywords = getattr(row, "meta_keywords", None) or ""

    if locale:
        t_stmt = select(PostTranslationModel).where(
            (PostTranslationModel.post_id == row.id)
            & (PostTranslationModel.locale_code == locale)
        )
        trans = db.execute(t_stmt).scalars().first()
        if trans:
            if trans.title and trans.title.strip():
                title = trans.title.strip()
            if trans.excerpt and trans.excerpt.strip():
                excerpt = trans.excerpt.strip()
            if trans.content_html and trans.content_html.strip():
                content_html = trans.content_html.strip()
            if hasattr(trans, "meta_keywords") and trans.meta_keywords and trans.meta_keywords.strip():
                meta_keywords = trans.meta_keywords.strip()

    aid, aname, auser, aavatar = _resolve_author_info(db, row.author_id)
    return PostView(
        id=row.id,
        slug=row.slug,
        title=title,
        excerpt=excerpt,
        category=row.category,
        content_html=_strip_missing_local_post_images(content_html),
        published_at=row.published_at,
        draft=bool(row.draft),
        hero_image_url=_clean_optional_image_url(row.hero_image_url),
        image_url=_clean_optional_image_url(row.image_url),
        images_url=json.loads(row.images_url_json) if row.images_url_json else None,
        author_id=aid,
        author_name=aname,
        author_username=auser,
        author_avatar=aavatar,
        meta_keywords=meta_keywords,
    )


def get_adjacent_posts(
    db: Session, current_post_id: int, locale: str | None = None
) -> tuple[PostView | None, PostView | None]:
    """
    Returnează perechea (prev_post, next_post) bazată pe ID:
    - prev_post: articolul publicat cu ID < current_post_id, ordonat descendent după ID.
    - next_post: articolul publicat cu ID > current_post_id, ordonat ascendent după ID.
    """
    if not current_post_id:
        return (None, None)

    prev_stmt = (
        select(PostModel)
        .where((PostModel.id < current_post_id) & (PostModel.draft == False))
        .order_by(PostModel.id.desc())
        .limit(1)
    )
    prev_row = db.execute(prev_stmt).scalars().first()

    next_stmt = (
        select(PostModel)
        .where((PostModel.id > current_post_id) & (PostModel.draft == False))
        .order_by(PostModel.id.asc())
        .limit(1)
    )
    next_row = db.execute(next_stmt).scalars().first()

    prev_post = get_post(db, prev_row.slug, locale=locale) if prev_row else None
    next_post = get_post(db, next_row.slug, locale=locale) if next_row else None

    return (prev_post, next_post)


def _category_full_path(category: CategoryModel) -> str:
    parts: list[str] = []
    current: CategoryModel | None = category
    while current is not None:
        parts.insert(0, current.name)
        current = current.parent
    return " / ".join(parts)


def list_categories(db: Session) -> list[CategoryView]:
    rows = (
        db.execute(
            select(CategoryModel).order_by(CategoryModel.parent_id, CategoryModel.name)
        )
        .scalars()
        .all()
    )
    grouped: dict[int | None, list[CategoryModel]] = {}
    for row in rows:
        grouped.setdefault(row.parent_id, []).append(row)
    for children in grouped.values():
        children.sort(key=lambda item: item.name)

    ordered: list[CategoryView] = []

    def walk(parent_id: int | None, depth: int = 0) -> None:
        for category_row in grouped.get(parent_id, []):
            ordered.append(
                CategoryView(
                    name=_category_full_path(category_row),
                    slug=category_row.slug,
                    depth=depth,
                    db_id=category_row.id,
                    description=getattr(category_row, "description", "") or "",
                    translations_json=getattr(category_row, "translations_json", "{}") or "{}",
                )
            )
            walk(category_row.id, depth + 1)

    walk(None, 0)

    post_categories = (
        db.execute(
            select(func.distinct(PostModel.category)).where(PostModel.category != None)
        )
        .scalars()
        .all()
    )
    for value in sorted({c for c in post_categories if c}):
        if not any(view.name == value for view in ordered):
            ordered.append(
                CategoryView(name=value, slug=slugify(value), depth=0, db_id=None, description="", translations_json="{}")
            )

    return ordered


def get_category_by_slug(db: Session, slug: str) -> CategoryModel | None:
    stmt = select(CategoryModel).where(CategoryModel.slug == slugify(slug))
    return db.execute(stmt).scalars().first()


def _resolve_parent_category(
    db: Session, parent_ref: str | None
) -> CategoryModel | None:
    """
    Părinte din admin: fie ID numeric (formularul trimite category.id), fie slug.
    """
    if not parent_ref:
        return None
    raw = str(parent_ref).strip()
    if not raw:
        return None
    if raw.isdigit():
        stmt = select(CategoryModel).where(CategoryModel.id == int(raw))
        return db.execute(stmt).scalars().first()
    return get_category_by_slug(db, raw)


def create_category(
    db: Session, name: str, parent_slug: str | None = None, description: str | None = "", translations_json: str | None = "{}"
) -> CategoryModel:
    """
    Creează sau actualizează o categorie.

    Dacă există deja o categorie cu același slug:
    - Dacă nu se specifică parent_slug, returnează categoria existentă (doar pentru protecție împotriva duplicatelor).
    - Dacă se specifică un părinte valid, actualizează relația parent_id.

    Acest comportament permite migrații sigure și reorganizarea ierarhică a categoriilor.

    ``parent_slug`` poate fi slug-ul părintelui sau ID-ul său (string), ca în formularul admin.
    """
    name_clean = (name or "").strip()
    if not name_clean:
        raise ValueError("Categoria trebuie să aibă un nume.")

    slug = slugify(name_clean)
    parent = _resolve_parent_category(db, parent_slug)
    if (parent_slug or "").strip() and parent is None:
        logger.warning(
            "create_category: părinte inexistent pentru ref=%r, nume=%r",
            parent_slug,
            name_clean,
        )

    # Verificăm dacă există deja o categorie cu acest slug
    existing = get_category_by_slug(db, slug)

    if existing:
        updated = False
        if parent and existing.parent_id != parent.id:
            existing.parent_id = parent.id
            updated = True
        if description is not None and description != "":
            existing.description = description.strip()
            updated = True
        if translations_json is not None and translations_json != "":
            existing.translations_json = translations_json.strip()
            updated = True
        if updated:
            db.commit()
            db.refresh(existing)

        return existing

    # Creație nouă de categorie
    category = CategoryModel(
        name=name_clean,
        slug=slug,
        parent_id=(parent.id if parent else None),
        description=(description or "").strip(),
        translations_json=(translations_json or "{}").strip()
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def _iter_category_subtree(db: Session, root: CategoryModel) -> list[CategoryModel]:
    """Rădăcină + toți descendenții, în ordine stabilă (copii sortați după nume)."""
    out: list[CategoryModel] = [root]
    stmt = (
        select(CategoryModel)
        .where(CategoryModel.parent_id == root.id)
        .order_by(CategoryModel.name)
    )
    for child in db.execute(stmt).scalars().all():
        out.extend(_iter_category_subtree(db, child))
    return out


def delete_category_by_id(db: Session, category_id: int) -> bool:
    """
    Șterge categoria (și subcategoriile — cascade ORM).

    Postările care foloseau calea afișată (ex. „Părinte / Copil”) pentru orice nod
    din subarbore rămân fără categorie (NULL).
    """
    row = db.get(CategoryModel, category_id)
    if row is None:
        return False

    nodes = _iter_category_subtree(db, row)
    paths = {_category_full_path(c) for c in nodes}
    paths.discard("")

    if paths:
        db.execute(
            update(PostModel)
            .where(PostModel.category.in_(paths))
            .values(category=None)
        )

    db.delete(row)
    db.commit()
    return True


def _resolve_local_post_image_path(url: str) -> Path | None:
    """Rezolvă calea imaginei locale din URL-ul postării."""
    if not url:
        return None
    raw = str(url).strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    path = parsed.path if parsed.scheme or parsed.netloc else raw
    if not path.startswith(_POST_IMAGE_PREFIX):
        return None
    filename = path[len(_POST_IMAGE_PREFIX) :].strip("/")
    if not filename or ".." in filename or filename.startswith("/"):
        return None
    return APP_DIR / "static" / "images" / "post_images" / filename


def _collect_post_image_paths(post: PostModel) -> list[Path]:
    """Strânge toate căile imaginilor asociate unei postări."""
    paths: list[Path] = []
    images: list[str] = []
    if post.images_url_json:
        try:
            images = json.loads(post.images_url_json)
        except Exception:
            images = []
    if not images:
        images = extract_images_from_html(post.content_html)
    if post.image_url:
        images.append(str(post.image_url))
    for image_url in images:
        path = _resolve_local_post_image_path(image_url)
        if path and path not in paths:
            paths.append(path)
    return paths


def _maybe_delete_local_post_image(
    db: Session, *, image_url: str, exclude_slug: str
) -> None:
    """
    Șterge fișierul pentru /static/images/post_images/* doar dacă:
    - e o cale locală validă
    - NU mai este referit de niciun alt post (hero/image/images_json/content_html)
    """
    path = _resolve_local_post_image_path(image_url)
    if not path:
        return
    if not path.exists():
        return

    url = str(image_url).strip()
    if not url:
        return

    refs_stmt = (
            select(func.count())
            .select_from(PostModel)
            .where(
                (PostModel.slug != exclude_slug)
                & (
                    (PostModel.hero_image_url == url)
                    | (PostModel.image_url == url)
                    | (PostModel.images_url_json.like(f"%{url}%"))
                    | (PostModel.content_html.like(f"%{url}%"))
                )
            )
        )
    refs = int(db.execute(refs_stmt).scalar() or 0)
    if refs > 0:
        return

    try:
        path.unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("delete_post: nu am putut șterge imaginea %s: %s", path, exc)


def delete_post(db: Session, slug: str) -> bool:
    """
    Șterge o postare din baza de date bazat pe slug.
    Returnează True dacă a fost ștearsă, False dacă nu a existat.
    """
    stmt = select(PostModel).where(PostModel.slug == slug)
    post = db.execute(stmt).scalars().first()

    if post:
        # Șterge imaginile asociate
        images_to_delete = []
        if post.hero_image_url:
            path = _resolve_local_post_image_path(post.hero_image_url)
            if path:
                images_to_delete.append(path)
        for path in _collect_post_image_paths(post):
            if path not in images_to_delete:
                images_to_delete.append(path)
        for path in images_to_delete:
            try:
                path.unlink(missing_ok=True)
            except Exception as exc:
                logger.warning(
                    "delete_post: nu am putut șterge imaginea %s: %s", path, exc
                )
        db.delete(post)
        db.commit()
        return True

    return False


def save_post(
    db: Session,
    *,
    author_id: int,
    slug: str,
    title: str,
    excerpt: str,
    category: str | None,
    hero_image_url: str | None,
    content_html: str,
    draft: bool,
    meta_keywords: str | None = None,
    published_at: datetime | None = None,
    original_slug: str | None = None,
) -> PostView:
    now = datetime.now(timezone.utc)
    slug_final = slugify(slug or title)

    raw_images = extract_images_from_html(content_html)
    images = [u for u in raw_images if _clean_optional_image_url(u)]
    image_url = images[0] if images else None
    hero_norm = _clean_optional_image_url(hero_image_url)
    if not image_url and hero_norm:
        image_url = hero_norm
    images_url_json = json.dumps(images, ensure_ascii=False) if images else None
    keywords_norm = (meta_keywords or "").strip() or None

    def _normalize_published_at(dt: datetime) -> datetime:
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    lookup_slug = original_slug.strip() if original_slug and original_slug.strip() else slug_final
    stmt = select(PostModel).where(PostModel.slug == lookup_slug)
    existing = db.execute(stmt).scalars().first()

    was_draft_before: bool | None = None
    if existing is not None:
        was_draft_before = bool(existing.draft)

    cat_clean = category.strip() if category and category.strip() else None
    if cat_clean and cat_clean.lower() in ("none", "null", "uncategorized", ""):
        cat_clean = None

    if existing is None:
        if published_at is None:
            published_at_final = now
        else:
            published_at_final = _normalize_published_at(published_at)
        post = PostModel(
            slug=slug_final,
            author_id=author_id,
            title=(title or slug_final).strip(),
            excerpt=(excerpt or "").strip(),
            category=cat_clean,
            content_html=(content_html or "").strip(),
            hero_image_url=hero_norm,
            image_url=image_url,
            images_url_json=images_url_json,
            meta_keywords=keywords_norm,
            draft=bool(draft),
            published_at=published_at_final,
            created_at=now,
            updated_at=now,
        )
        db.add(post)
    else:
        old_hero = (existing.hero_image_url or "").strip() or None
        if published_at is not None:
            published_at_final = _normalize_published_at(published_at)
        else:
            published_at_final = existing.published_at
        if not existing.author_id:
            existing.author_id = author_id
        existing.title = (title or slug_final).strip()
        existing.excerpt = (excerpt or "").strip()
        existing.category = cat_clean
        existing.content_html = (content_html or "").strip()
        existing.hero_image_url = hero_norm
        existing.image_url = image_url
        existing.images_url_json = images_url_json
        existing.meta_keywords = keywords_norm
        existing.draft = bool(draft)
        existing.published_at = published_at_final
        existing.updated_at = now
        post = existing

    db.commit()
    db.refresh(post)

    if not post.draft:
        from app.core import events
        from app.core.config import get_public_site_url, post_public_path
        rel = post_public_path(post.slug)
        base = (get_public_site_url() or "").strip().rstrip("/")
        post_url = f"{base}{rel}" if base else rel
        hero_abs: str | None = None
        hero_raw = _clean_optional_image_url(post.hero_image_url)
        if hero_raw:
            if hero_raw.startswith(("http://", "https://")):
                hero_abs = hero_raw
            elif base:
                pth = hero_raw if hero_raw.startswith("/") else f"/{hero_raw}"
                hero_abs = f"{base}{pth}"
        post_translations = get_post_translations(db, post.id)
        events.publish(
            "blog.post_published",
            slug=post.slug,
            title=post.title or post.slug,
            excerpt=(post.excerpt or "")[:800],
            post_url=post_url,
            hero_image_abs=hero_abs,
            translations=post_translations,
        )

    # Dacă hero s-a schimbat / a fost scos, încercăm să ștergem fișierul vechi.
    if existing is not None:
        new_hero = (post.hero_image_url or "").strip() or None
        if old_hero and old_hero != new_hero:
            _maybe_delete_local_post_image(
                db, image_url=old_hero, exclude_slug=post.slug
            )

    return PostView(
        slug=post.slug,
        title=post.title,
        excerpt=post.excerpt or "",
        category=post.category,
        content_html=post.content_html,
        published_at=post.published_at,
        draft=bool(post.draft),
        hero_image_url=_clean_optional_image_url(post.hero_image_url),
        image_url=_clean_optional_image_url(post.image_url),
        images_url=json.loads(post.images_url_json) if post.images_url_json else None,
    )


def get_post_translations(db: Session, post_id: int) -> dict[str, dict[str, str]]:
    stmt = select(PostTranslationModel).where(PostTranslationModel.post_id == post_id)
    rows = db.execute(stmt).scalars().all()
    res: dict[str, dict[str, str]] = {}
    for r in rows:
        res[r.locale_code] = {
            "title": r.title or "",
            "excerpt": r.excerpt or "",
            "content_html": r.content_html or "",
        }
    return res

def save_post_translations(
    db: Session,
    post_id: int,
    translations: dict[str, dict[str, str]],
) -> None:
    from app.models.db_models import TranslationLocale as TranslationLocaleModel
    for locale_code, data in translations.items():
        title = (data.get("title") or "").strip()
        excerpt = (data.get("excerpt") or "").strip()
        content_html = (data.get("content_html") or "").strip()
        if not title and not content_html:
            continue
        loc_row = db.get(TranslationLocaleModel, locale_code)
        if loc_row is None:
            db.add(TranslationLocaleModel(code=locale_code, name=locale_code.upper(), enabled=True, is_default=(locale_code == "en")))
            db.flush()
        stmt = select(PostTranslationModel).where(
            (PostTranslationModel.post_id == post_id)
            & (PostTranslationModel.locale_code == locale_code)
        )
        row = db.execute(stmt).scalars().first()
        if row is None:
            row = PostTranslationModel(
                post_id=post_id,
                locale_code=locale_code,
                title=title,
                excerpt=excerpt,
                content_html=content_html,
            )
            db.add(row)
        else:
            row.title = title
            row.excerpt = excerpt
            row.content_html = content_html
    db.commit()

def list_authors_with_posts(db: Session) -> list[dict]:
    author_ids = db.execute(
        select(func.distinct(PostModel.author_id)).where(PostModel.draft == False)
    ).scalars().all()

    authors: list[dict] = []
    for aid in author_ids:
        if not aid:
            continue
        u = db.get(UserModel, aid)
        if not u:
            continue
        name_parts = [u.first_name, u.last_name]
        full_name = " ".join([p for p in name_parts if p]).strip()
        display_name = full_name if full_name else (u.username or f"User #{u.id}")
        slug = u.username or display_name
        authors.append({
            "id": u.id,
            "name": display_name,
            "username": u.username,
            "slug": slug,
            "avatar": u.image_url,
        })
    return authors
