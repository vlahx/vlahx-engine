from __future__ import annotations

from datetime import datetime, timezone


POSTS = [
    {
        "slug": "primul-post",
        "title": "Primul post",
        "excerpt": "Template-ul de blog e live: listă, pagină articol, UI simplu.",
        "content": """<p>Asta e o pagină de articol, randată cu Jinja2.</p>
<p>Următorii pași: markdown, DB, admin auth, editor.</p>""",
        "published_at": datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc),
    },
    {
        "slug": "despre",
        "title": "Despre",
        "excerpt": "Pagina „Despre” ca post (slug).",
        "content": "<p>Salut! Aici îți pui povestea proiectului.</p>",
        "published_at": datetime(2026, 4, 2, 12, 5, tzinfo=timezone.utc),
    },
]


def list_posts() -> list[dict]:
    return sorted(POSTS, key=lambda p: p["published_at"], reverse=True)


def get_post(slug: str) -> dict | None:
    for p in POSTS:
        if p["slug"] == slug:
            return p
    return None

