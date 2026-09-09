# 🔌 Guide: How to Create a Custom Plugin for VlahX Core 3.0

This guide explains step-by-step how to design, develop, package, and install a custom plugin for **VlahX Core 3.0**.

---

## 📁 1. Plugin Directory Architecture

Every plugin in **VlahX Core 3.0** must be **100% self-contained** inside its own directory in `app/plugins/<plugin_id>/`. Nothing should spill over into core `templates/` or `app/` folders.

```text
app/plugins/<plugin_id>/
├── plugin.json               # Required plugin manifest & metadata (v3.0)
├── plugin.py                 # Main entry point (MUST export register(app) function)
├── db.py                     # Database models, JSON/SQLite settings & CRUD logic (optional)
├── locales/                  # Multi-language translations (optional)
│   ├── ro.json               # Romanian translations
│   └── en.json               # English translations
├── templates/                # Embedded Jinja2 HTML templates (optional)
│   └── admin/                # Admin Panel pages (e.g. templates/admin/<plugin_id>.html)
└── assets/                   # Static CSS/JS files (optional)
    └── script.js
```

---

## 📜 2. Plugin Manifest (`plugin.json`)

Create a `plugin.json` file inside `app/plugins/<plugin_id>/`:

```json
{
  "id": "my_custom_plugin",
  "name": "My Custom Plugin",
  "version": "1.0.0",
  "vlahx_version": "3.0.0",
  "min_engine_version": "3.0.0",
  "description": "Adds awesome custom features to VlahX Core 3.0.",
  "author": "Your Name"
}
```

### Manifest Fields (v3.0):
- **`id`**: Unique lowercase identifier matching folder name (e.g. `ai_vlahx`, `newsletter`, `minishop`).
- **`name`**: Human-readable name shown in Admin Plugin Manager (`/admin/plugins`).
- **`version`**: Semantic version string (e.g. `1.0.0`).
- **`vlahx_version`**: Platform target version (`"3.0.0"`).
- **`min_engine_version`**: Minimum VlahX engine version requirement (`"3.0.0"`).
- **`description`**: Brief summary of what the plugin does.
- **`author`**: Developer or team name.

---

## 🚀 3. Plugin Entry Point (`plugin.py`)

The `plugin.py` file is loaded dynamically by `plugin_manager.py` when VlahX starts. It **MUST** export a `register(app: FastAPI)` function.

```python
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.template_hooks import register_admin_nav
from app.core.templates import render_template, build_templates
from app.core.plugin_manager import get_plugin_admin_context
from app.utils.db import SessionLocal

logger = logging.getLogger("my_custom_plugin")
PLUGIN_ID = "my_custom_plugin"


def render_my_admin_nav(request: Request) -> str:
    """Renders the sidebar navigation link in VlahX Core 3.0 Admin Panel."""
    current_path = request.url.path
    active_cls = "active" if f"/admin/plugins/{PLUGIN_ID}" in current_path else ""
    return f"""
    <a href="/admin/plugins/{PLUGIN_ID}" class="sidebar-link {active_cls}">
      <span class="icon">⚡</span>
      <span class="text">My Custom Plugin</span>
    </a>
    """


def register(app: FastAPI) -> None:
    """
    CRITICAL: VlahX Core 3.0 Plugin Manager requires this exact function name!
    """
    logger.info("Initializing plugin: %s", PLUGIN_ID)

    # 1. Register Link in Admin Sidebar under 'Plugin-uri Active'
    register_admin_nav(render_my_admin_nav, order=10)

    # 2. Admin Dashboard Route
    @app.get(f"/admin/plugins/{PLUGIN_ID}", response_class=HTMLResponse)
    async def admin_dashboard(request: Request, message: Optional[str] = None):
        user_id = request.session.get("user_id")
        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=303)

        with SessionLocal() as db:
            extra_ctx = {
                "message": message,
                "custom_data": "VlahX 3.0 Data"
            }
            # Crucial for VlahX 3.0 context & i18n rendering
            ctx = get_plugin_admin_context(PLUGIN_ID, db, extra_ctx)
            return render_template(
                build_templates(),
                request=request,
                name="admin/my_custom_plugin.html",
                context=ctx
            )
```

---

## 🎨 4. Template Encapsulation & Rendering (VlahX 3.0)

In VlahX Core 3.0, template rendering is unified via `render_template(build_templates(), request=request, name=..., context=ctx)`.

### Admin Panel Page (`app/plugins/<plugin_id>/templates/admin/<plugin_id>.html`)
**CRITICAL**: Every Admin template MUST extend `"admin/admin_base.html"`:

```html
{% extends "admin/admin_base.html" %}

{% block title %}My Custom Plugin - Admin{% endblock %}

{% block content %}
<div class="container-fluid px-4 py-4">
  <div class="d-flex align-items-center justify-content-between mb-4">
    <div>
      <h1 class="h3 fw-bold text-white mb-1">⚡ My Custom Plugin</h1>
      <p class="text-secondary mb-0">Manage options and view plugin status in VlahX Core 3.0.</p>
    </div>
  </div>

  {% if message %}
  <div class="alert alert-success alert-dismissible fade show" role="alert">
    {{ message }}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
  </div>
  {% endif %}

  <div class="card bg-dark border-secondary shadow-sm p-4 text-white">
    <h5 class="fw-bold">Welcome to My Plugin</h5>
    <p>{{ custom_data }}</p>
  </div>
</div>
{% endblock %}
```

---

## 🌐 5. Internationalization / Multi-language (`locales/`)

Place JSON translation files inside `app/plugins/<plugin_id>/locales/`:

### Romanian (`app/plugins/<plugin_id>/locales/ro.json`):
```json
{
  "plugin_name": "Plugin-ul Meu Personalizat",
  "title": "Panou de Control Plugin",
  "save_btn": "Salvează Configurația"
}
```

### English (`app/plugins/<plugin_id>/locales/en.json`):
```json
{
  "plugin_name": "My Custom Plugin",
  "title": "Plugin Control Panel",
  "save_btn": "Save Settings"
}
```

---

## 🤖 6. AI & Non-Blocking Async Execution Pattern

If your plugin connects to LLM services (LocalAI, OpenAI, Gemini), always execute HTTP requests using **`asyncio.to_thread`** to keep FastAPI completely non-blocking:

```python
import asyncio
import requests

def _call_localai_sync(endpoint: str, payload: dict, api_key: str) -> str:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    res = requests.post(endpoint, json=payload, headers=headers, timeout=300)
    res.raise_for_status()
    data = res.json()
    return data["choices"][0]["message"]["content"]

async def call_localai_async(endpoint: str, payload: dict, api_key: str) -> str:
    return await asyncio.to_thread(_call_localai_sync, endpoint, payload, api_key)
```

---

## 🔗 7. VlahX Core 3.0 Template Hooks Reference

| Registration Function | Hook Target / Location | Signature |
| :--- | :--- | :--- |
| `register_admin_nav(renderer, order=10)` | Admin Sidebar under 'Plugin-uri Active' | `renderer(request: Request) -> str` |
| `register_navbar_link(renderer)` | Public Navbar links | `renderer(request: Request) -> str` |
| `register_post_article_footer(renderer)` | Beneath blog posts/articles | `renderer(post: Any, request: Request) -> str` |
| `register_post_header_meta(renderer)` | Article metadata header bar | `renderer(post: Any, request: Request) -> str` |

---

## 📦 8. Packaging & Installation (ZIP Format)

To package a plugin for distribution:

### Archive Structure:
```text
my_custom_plugin.zip
 └── my_custom_plugin/
      ├── plugin.json
      ├── plugin.py
      ├── db.py (optional)
      ├── locales/ (optional)
      └── templates/ (optional)
```

### Installing in Admin:
1. Go to **Admin Panel** ➔ **Extensii & Plugin-uri** (`/admin/plugins`).
2. Click **Upload Plugin ZIP**.
3. Select your `<plugin_id>.zip` archive.
4. Click **Instalează Plugin**!

---

## 🎉 Checklist for VlahX Core 3.0 Plugin Developers

- [x] Folder name matches `id` in `plugin.json` (`app/plugins/<id>/`).
- [x] `plugin.json` includes `"vlahx_version": "3.0.0"` and `"min_engine_version": "3.0.0"`.
- [x] `plugin.py` exports **`def register(app: FastAPI)`**.
- [x] Admin views use `get_plugin_admin_context(PLUGIN_ID, db, extra_ctx)` and `render_template(build_templates(), ...)`.
- [x] Admin templates extend `"admin/admin_base.html"`.
- [x] Heavy AI/HTTP operations use `asyncio.to_thread` for non-blocking execution.
