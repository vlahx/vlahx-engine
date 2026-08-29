# ⚡ VlahX Core 2.0 Technical Documentation (`vlahx.md`)
## Architecture Specification, System Workflows & OpenAPI/Swagger Reference

This document serves as the official technical documentation for **VlahX Core 2.0**, designed for **Developers** (architecture, routes, parameters, integrations, plugins) and **Administrators** (workflows, roles, moderation, site settings).

---

## 1. General Architecture & Core Technologies

**VlahX Engine 2.0** is designed as a high-performance, modular Plugin-Driven Architecture built on top of:

* **Backend & Web Framework**: Python 3.11+ with **FastAPI** for high-speed async routing and automatic OpenAPI/Swagger documentation generation.
* **ORM & Database**: **SQLAlchemy** connected to **SQLite** (`db/app.db`).
* **Templating & UI Rendering**: **Jinja2 Templates** (Server-Side Rendering), supported by responsive UI (Bootstrap 5, Vanilla CSS3, modular JavaScript).
* **Authentication & Sessions**: `starlette.middleware.sessions.SessionMiddleware` supporting Classic Email/Password, Multi-Provider OAuth 2.0 SSO (Google, GitHub, Facebook, LinkedIn, Microsoft, Discord), and Telegram Widget Login.
* **Internationalization (i18n)**: Hybrid JSON file-based system (`app/locales/ro.json`, `app/locales/en.json`) with dynamic language preservation (`?lang=`).

### Project Directory Structure

```text
/app/
├── core/                  # Core utilities (config, i18n, plugin_manager, template_hooks)
├── models/                # SQLAlchemy ORM models (Post, User, Category, PluginSetting, etc.)
├── routers/               # Primary FastAPI routers (auth, admin, blog, plugin_settings)
├── plugins/               # Decoupled plugin modules (vlahx_oauth, minishop, newsletter, robots_sitemap, etc.)
├── static/                # Static assets (CSS, JS, upload media)
├── templates/             # Jinja2 template files (admin/, blog/, user/)
└── utils/                 # Utility helpers (auth, db, telegram, open_graph)
```

---

## 2. Role & Permission System

Access control is governed by decorators in `app/utils/auth.py`:
- **user**: Registered end-user.
- **developer**: Community plugin/theme developer.
- **admin**: Full administrative control over site settings, plugins, themes, and users.
