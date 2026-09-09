from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = value.replace("_", "-").replace(" ", "-")
    value = _SLUG_RE.sub("-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "post"


@dataclass(frozen=True)
class Post:
    slug: str
    title: str
    excerpt: str
    content_html: str
    published_at: datetime
    category: str | None = None
    draft: bool = False

    @property
    def published_at_utc(self) -> datetime:
        dt = self.published_at
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)


def _posts_dir(base_dir: str | Path = "content/posts") -> Path:
    p = Path(base_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _post_path(slug: str, base_dir: str | Path = "content/posts") -> Path:
    slug = slugify(slug)
    return _posts_dir(base_dir) / f"{slug}.json"


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _to_post(data: dict[str, Any]) -> Post | None:
    slug = slugify(str(data.get("slug", "")))
    title = str(data.get("title", "")).strip() or slug
    excerpt = str(data.get("excerpt", "")).strip()
    content_html = str(data.get("content_html", "") or data.get("content", "")).strip()
    published_at = _parse_dt(str(data.get("published_at", "") or data.get("date", "") or ""))
    draft = bool(data.get("draft", False))
    if not slug:
        return None
    return Post(
        slug=slug,
        title=title,
        excerpt=excerpt,
        category=str(data.get("category", "")).strip() or None,
        content_html=content_html,
        published_at=published_at,
        draft=draft,
    )


def list_posts(*, include_drafts: bool = False, base_dir: str | Path = "content/posts") -> list[Post]:
    posts: list[Post] = []
    for path in sorted(_posts_dir(base_dir).glob("*.json")):
        data = _load_json(path)
        if not data:
            continue
        post = _to_post(data)
        if not post:
            continue
        if post.draft and not include_drafts:
            continue
        posts.append(post)
    posts.sort(key=lambda p: p.published_at_utc, reverse=True)
    return posts


def get_post(slug: str, *, base_dir: str | Path = "content/posts") -> Post | None:
    path = _post_path(slug, base_dir)
    data = _load_json(path)
    if not data:
        return None
    return _to_post(data)


def save_post(
    *,
    slug: str,
    title: str,
    excerpt: str,
    content_html: str,
    draft: bool,
    published_at: datetime | None = None,
    base_dir: str | Path = "content/posts",
) -> Post:
    slug = slugify(slug or title)
    now = datetime.now(timezone.utc)
    published_at = published_at or now
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    post = Post(
        slug=slug,
        title=(title or slug).strip(),
        excerpt=(excerpt or "").strip(),
        content_html=(content_html or "").strip(),
        published_at=published_at.astimezone(timezone.utc),
        draft=bool(draft),
    )
    path = _post_path(slug, base_dir)
    payload = {
        "slug": post.slug,
        "title": post.title,
        "excerpt": post.excerpt,
        "category": post.category,
        "content_html": post.content_html,
        "published_at": post.published_at_utc.isoformat(),
        "draft": post.draft,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return post

