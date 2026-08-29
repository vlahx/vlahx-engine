# ⚡ VlahX Engine (v2.0 Core) Developer API Guide
## Architecture, Core APIs, Database Models & Plugin System

This technical guide provides the complete developer documentation for the **VlahX Core 2.0** engine. Developers can use this document to understand the codebase structure and build **custom plugins**, **themes**, and **extensions**.

---

## 1. Core Concepts & Architecture

* **Core Stack**: Python 3.11+ (FastAPI), Jinja2 Templates, SQLite (`db/app.db`), Vanilla CSS / Bootstrap 5, Vanilla JS.
* **Single Source of Truth**: Application settings are stored directly inside the SQLite database (`plugin_settings` table), eliminating messy configuration files.
* **Decoupled Plugin Architecture**: Core functionality (SEO, OAuth SSO, Telegram Notifications, Analytics, Sitemap, Shop) is encapsulated into decoupled plugins.

---

## 2. Core Helper Functions (`app/core/config.py`)

Helper functions available across plugins and routers:

| Helper Function | Returns | Description |
| :--- | :--- | :--- |
| `get_site_display_name(locale=None)` | `str` | Official site name (with multi-language support). |
| `get_site_tagline(locale=None)` | `str` | Site slogan / tagline. |
| `get_public_site_url()` | `str` | Configured public site URL. |
| `public_site_origin(request)` | `str` | Absolute origin (e.g. `https://vlahx.org`), auto-detecting HTTPS reverse-proxy headers (`X-Forwarded-Proto`). |
| `get_homepage_mode()` | `str` | Homepage mode (`blog` = article feed, `page:<slug>` = static page, `shop` = online store). |
| `get_active_theme()` | `str` | Active theme slug (e.g. `"minimal"`). |
| `get_flat_post_urls()` | `bool` | `True` if post URLs are flat `/{slug}`, or `False` if `/blog/{slug}`. |
| `get_site_favicon_path()` | `str` | Path to site favicon. |
| `get_site_brand_image_path()` | `str` | Path to brand image / main logo. |
| `get_site_nav_icon_path()` | `str` | Path to navbar brand icon. |
| `get_og_card_image_path()` | `str` | Path to default OpenGraph card image. |
| `get_telegram_bot_token()` | `str` | Telegram Bot token stored in SQLite/plugin settings. |
| `get_telegram_notify_chat_id()` | `str` | Telegram Chat ID for admin notifications. |
| `get_telegram_bot_username()` | `str` | Telegram Bot username (without `@`). |

---

## 3. Database Schema (`app/models/db_models.py`)

- **User**: ID, email, password_hash, first_name, last_name, bio, is_admin, is_developer, oauth_provider, oauth_id.
- **Post**: ID, slug, title, content, excerpt, category_id, is_published, views_count, created_at, updated_at.
- **Category**: ID, slug, name, description.
- **PluginSetting**: key, value, created_at, updated_at.

---

## 4. Multi-Language Internationalization (i18n)

- Language parameter `?lang=` is preserved across all routes and links.
- `resolve_locale(request)` resolves language from `?lang=`, session, or headers.
- Template helper `{{ t('key') }}` translates string keys using `/app/locales/ro.json` and `/app/locales/en.json`.
