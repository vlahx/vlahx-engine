from __future__ import annotations

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import Response

from app.core.config import invalidate_nav_fixed_post_links_cache
from app.core.i18n import get_translation, get_translations, resolve_locale, set_locale_cookie
from app.core.templates import build_templates, render_template
from app.core.translation_db import DEFAULT_TRANSLATION_CATALOG, list_translation_catalog, set_translation_entry
from app.models.db_models import AppSetting, Post, PostTranslation, User
from app.utils.db import SessionLocal


def test_resolve_locale_from_query_param() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "query_string": b"lang=en"})

    assert resolve_locale(request) == "en"


def test_get_translation_falls_back_to_default_locale() -> None:
    assert get_translation("ro", "ui.admin") == "Admin"
    assert get_translation("en", "ui.admin") == "Admin"


def test_resolve_locale_from_cookie() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"cookie", b"blog_locale=en")]})

    assert resolve_locale(request) == "en"


def test_set_locale_cookie_writes_cookie() -> None:
    response = Response()
    set_locale_cookie(response, "en")

    assert "blog_locale=en" in response.headers["set-cookie"]


def test_falls_back_to_english_source_for_missing_locale_entries() -> None:
    set_translation_entry("en", "tests.fallback.label", "English source value")

    assert get_translation("fr", "tests.fallback.label") == "English source value"


def test_get_translations_includes_english_fallback_values() -> None:
    set_translation_entry("en", "tests.fallback.group.title", "English group title")

    translations = get_translations("fr")

    assert translations["tests"]["fallback"]["group"]["title"] == "English group title"


def test_translation_catalog_uses_english_as_source_for_admin_ui() -> None:
    set_translation_entry("en", "ui.admin", "Admin")

    catalog = list_translation_catalog("fr")

    assert any(item["key"] == "ui.admin" and item["source_value"] == "Admin" for item in catalog)


def test_default_translation_catalog_contains_english_source_values() -> None:
    assert DEFAULT_TRANSLATION_CATALOG["ui.admin"] == "Admin"
    assert DEFAULT_TRANSLATION_CATALOG["blog.empty.title"] == "No posts yet"


def test_get_translations_falls_back_to_default_locale_when_locale_is_empty() -> None:
    set_translation_entry("en", "blog.empty.title", "No posts yet")
    set_translation_entry("en", "blog.empty.description", "The first post will appear soon.")

    translations = get_translations("ro")

    assert translations["blog"]["empty"]["title"] == "No posts yet"
    assert translations["blog"]["empty"]["description"] == "The first post will appear soon."


def test_render_template_uses_request_locale_for_site_title_and_tagline() -> None:
    with SessionLocal() as db:
        for key in ("SITE_DISPLAY_NAME_ro", "SITE_TAGLINE_ro"):
            db.query(AppSetting).filter(AppSetting.key == key).delete(synchronize_session=False)
        db.add_all(
            [
                AppSetting(key="SITE_DISPLAY_NAME_ro", value="Titlu RO"),
                AppSetting(key="SITE_TAGLINE_ro", value="Tagline RO"),
            ]
        )
        db.commit()

    templates = build_templates("templates")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "client": ("127.0.0.1", 1234),
            "server": ("127.0.0.1", 8000),
        }
    )
    request.state.locale = "ro"
    request.state.translations = {}

    response = render_template(
        templates,
        request=request,
        name="blog/index.html",
        context={"posts": [], "categories": [], "title": "Test"},
    )

    html = response.body.decode("utf-8")
    assert "Titlu RO" in html
    assert "Tagline RO" in html


def test_render_template_includes_fixed_nav_link_when_configured() -> None:
    with SessionLocal() as db:
        db.query(AppSetting).filter(
            AppSetting.key.in_(["NAV_FIXED_POST_SLUG", "NAV_FIXED_POST_LABEL", "STATIC_NAV_LINKS"])
        ).delete(synchronize_session=False)
        db.query(Post).filter(Post.slug == "despre-noi").delete(synchronize_session=False)

        user = User(
            provider="dev",
            oauth_id="nav-test-user",
            username="navtest",
            first_name="Nav",
            last_name="Tester",
            email="navtest@example.com",
            role="admin",
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.flush()

        db.add(
            Post(
                author_id=user.id,
                slug="despre-noi",
                title="Despre noi",
                excerpt="",
                category="General",
                content_html="<p>Intro</p>",
                draft=False,
                published_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.add_all(
            [
                AppSetting(key="NAV_FIXED_POST_SLUG", value="despre-noi"),
                AppSetting(key="NAV_FIXED_POST_LABEL", value="Despre noi"),
            ]
        )
        db.commit()
        invalidate_nav_fixed_post_links_cache()

    templates = build_templates("templates")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "client": ("127.0.0.1", 1234),
            "server": ("127.0.0.1", 8000),
        }
    )
    request.state.locale = "ro"
    request.state.translations = {}

    response = render_template(
        templates,
        request=request,
        name="blog/index.html",
        context={"posts": [], "categories": [], "title": "Test"},
    )

    html = response.body.decode("utf-8")
    assert "Despre noi" in html
    assert 'href="/despre-noi"' in html


def test_render_template_uses_post_title_when_static_nav_label_is_missing() -> None:
    with SessionLocal() as db:
        db.query(AppSetting).filter(
            AppSetting.key.in_(["NAV_FIXED_POST_SLUG", "NAV_FIXED_POST_LABEL", "STATIC_NAV_LINKS"])
        ).delete(synchronize_session=False)
        db.query(Post).filter(Post.slug == "despre-noi").delete(synchronize_session=False)

        user = User(
            provider="dev",
            oauth_id="nav-title-user",
            username="navtitle",
            first_name="Nav",
            last_name="Title",
            email="navtitle@example.com",
            role="admin",
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.flush()

        db.add(
            Post(
                author_id=user.id,
                slug="despre-noi",
                title="Despre noi",
                excerpt="",
                category="General",
                content_html="<p>Intro</p>",
                draft=False,
                published_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.add(AppSetting(key="NAV_FIXED_POST_SLUG", value="despre-noi"))
        db.commit()
    invalidate_nav_fixed_post_links_cache()

    templates = build_templates("templates")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "client": ("127.0.0.1", 1234),
            "server": ("127.0.0.1", 8000),
        }
    )
    request.state.locale = "ro"
    request.state.translations = {}

    response = render_template(
        templates,
        request=request,
        name="blog/index.html",
        context={"posts": [], "categories": [], "title": "Test"},
    )

    html = response.body.decode("utf-8")
    assert "Despre noi" in html
    assert 'href="/despre-noi"' in html


def test_render_template_uses_current_locale_title_for_static_nav_link() -> None:
    with SessionLocal() as db:
        db.query(AppSetting).filter(
            AppSetting.key.in_(["NAV_FIXED_POST_SLUG", "NAV_FIXED_POST_LABEL", "STATIC_NAV_LINKS"])
        ).delete(synchronize_session=False)
        db.query(Post).filter(Post.slug == "despre-noi").delete(synchronize_session=False)

        user = User(
            provider="dev",
            oauth_id="nav-localized-user",
            username="navlocalized",
            first_name="Nav",
            last_name="Localized",
            email="navlocalized@example.com",
            role="admin",
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.flush()

        post = Post(
            author_id=user.id,
            slug="despre-noi",
            title="Despre noi",
            excerpt="",
            category="General",
            content_html="<p>Intro</p>",
            draft=False,
            published_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(post)
        db.flush()
        db.add_all(
            [
                PostTranslation(post_id=post.id, locale_code="ro", title="Despre noi", excerpt="", content_html="<p>Intro ro</p>"),
                PostTranslation(post_id=post.id, locale_code="en", title="About us", excerpt="", content_html="<p>Intro en</p>"),
                AppSetting(key="STATIC_NAV_LINKS", value='[{"slug": "despre-noi", "label": "Legacy label", "fixed_label": "Legacy label"}]'),
            ]
        )
        db.commit()

    templates = build_templates("templates")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"lang=en",
            "client": ("127.0.0.1", 1234),
            "server": ("127.0.0.1", 8000),
        }
    )
    request.state.locale = "en"
    request.state.translations = {}

    response = render_template(
        templates,
        request=request,
        name="blog/index.html",
        context={"posts": [], "categories": [], "title": "Test"},
    )

    html = response.body.decode("utf-8")
    assert "About us" in html
    assert "Legacy label" not in html
    assert "/despre-noi" in html
