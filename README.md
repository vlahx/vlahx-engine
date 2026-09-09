# ⚡ VlahX Engine (v3.0 Core) — Modular Web Platform

[![VlahX Engine](https://img.shields.io/badge/VlahX_Engine-v3.0_Core-6f42c1?style=for-the-badge&logo=python&logoColor=white)](https://vlahx.org/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

**VlahX Engine** is an ultra-fast, highly flexible, modular web application platform built with **Python 3.11+ (FastAPI)**, **SQLAlchemy**, **Jinja2**, and **Bootstrap 5**. It is designed to effortlessly build and extend modern websites, blogs, e-commerce stores, and community portals through a decoupled architecture of **plugins** and **themes**.

🌐 **Official Site & Community**: [https://vlahx.org/](https://vlahx.org/)  
📖 **Documentation & About**: [https://vlahx.org/about](https://vlahx.org/about)

---

## 🌟 Key Features

- ⚡ **Blazing Fast Core**: Powered by Python 3.11+, FastAPI, Uvicorn, and SQLite / SQLAlchemy in WAL mode.
- 🗄️ **Single Source of Truth**: Application settings and plugin configurations are saved directly to the SQLite database (`db/app.db`), enabling dynamic configuration without manual config file edits.
- 🔀 **Dynamic Homepage Router**: Effortlessly switch your homepage (`/`) between a Blog Feed, a Custom Static Page, an Online Shop (`minishop`), or the default Core Welcome Hero.
- 🔐 **Multi-Provider SSO & Authentication**:
  - Built-in Single Sign-On (SSO) supporting **Google**, **GitHub**, **Facebook**, **LinkedIn**, **Microsoft**, **Discord**, and **Telegram 1-Click Login**.
  - Automatic account linking via verified email or active user session.
- 🧩 **Decoupled Plugin Architecture**:
  - Official plugins for **OAuth 2.0 Social Login**, **Google SEO & Instant Indexing**, **Traffic Analytics & Referrers**, **Telegram Notifications**, **XML Sitemap**, **Robots.txt**, **Comments Widget**, **Newsletter**, **Social Share**, **AI Author (RAG)**, and **MiniShop**.
- 🎨 **Multi-Theme Engine**:
  - Fully decoupled themes with native Dark Mode & Light Mode support.
  - Template Hooks system allowing plugins to inject UI components seamlessly into themes.
- 🌐 **Seamless Path-Based Internationalization (i18n)**:
  - Clean `/{lang}/...` path-based routing with automatic `<link rel="canonical">`, `hreflang` tags, and fallback localization.
- ⚡ **Navigation & Admin Manager**:
  - Full control over navbar and footer links, external URLs with security attributes (`rel="noopener noreferrer"`), and dynamic target settings.

---

## 🚀 Quick Start Guide

### 🐧 Linux & 🍎 macOS (1-Step Launcher)

```bash
git clone git@github.com:vlahx/vlahx-engine.git
cd vlahx-engine
./run.sh
```

### 🪟 Windows (1-Step Launcher)

```cmd
git clone git@github.com:vlahx/vlahx-engine.git
cd vlahx-engine
win-run.bat
```

### 🛠️ Manual Development Setup (Cross-Platform)

```bash
git clone git@github.com:vlahx/vlahx-engine.git
cd vlahx-engine

# Create & activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies and start development server
pip install -r requirements.txt
python run.py
```

Open `http://localhost:8000` in your browser.

---

## 🐳 Docker Deployment

The `docker-compose.yml` file is excluded from Git (`.gitignore`) by default to prevent container name and port collisions between **Development (DEV)** and **Production (PROD)** environments.

### 🛠️ Development Configuration (`dev-vlahx` — Port 8002)

Create `docker-compose.yml` in your development directory (`/opt/devapp`):

```yaml
services:
  dev-blog:
    build: .
    image: dev-vlahx-engine:latest
    container_name: dev-vlahx
    restart: unless-stopped
    ports:
      - "8002:8000"
    environment:
      APP_PORT: "8000"
      APP_RELOAD: "true"
    volumes:
      - ./app:/app/app
      - ./db:/app/db
      - ./main.py:/app/main.py
      - ./run.py:/app/run.py
```

### 🚀 Production Configuration (`vlahx` — Port 8001)

Create `docker-compose.yml` in your production directory (`/opt/vlahx`):

```yaml
services:
  vlahx-blog:
    build: .
    image: vlahx-engine:latest
    container_name: vlahx
    restart: unless-stopped
    ports:
      - "8001:8000"
    environment:
      APP_PORT: "8000"
      APP_RELOAD: "false"
    volumes:
      - ./app:/app/app
      - ./db:/app/db
      - ./main.py:/app/main.py
      - ./run.py:/app/run.py
```

### Start Container

```bash
docker compose up -d
```

---

## 📘 Developer Guide & Documentation

We welcome developers to build custom plugins, themes, and extensions for the VlahX ecosystem!

* 📖 **Plugin Development**: Check [`docs/PLUGIN_DEVELOPMENT_GUIDE.md`](docs/PLUGIN_DEVELOPMENT_GUIDE.md) for plugin structure, lifecycle hooks, and database guidelines.
* 🎨 **Theme Development**: Check [`docs/THEME_DEVELOPMENT_GUIDE.md`](docs/THEME_DEVELOPMENT_GUIDE.md) for Jinja2 template standards and hook injection points.
* 🏬 **VlahX Extension Store**: Discover official packages and publish your own plugins at [https://repo.vlahx.org/](https://repo.vlahx.org/).

---

## 📜 License

Distributed under the **Apache License 2.0**. See `LICENSE` for details.

© 2026 **[VlahX Engine Community](https://vlahx.org/)** — Build and extend modern web applications with plugins and themes.
