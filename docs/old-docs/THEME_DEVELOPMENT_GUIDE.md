# 🎨 VlahX Core 2.0 Theme Development Guide
## (Zero-Hardcoding & Decoupled Architecture Specifications)

This technical guide provides the complete specifications, development rules, and reference code examples for creating **100% dynamic, responsive, and compatible themes** for the **VlahX Core 2.0** engine.

---

## 🌟 1. The Zero Hardcoding Philosophy (Golden Rule)

In VlahX Core 2.0, **NO THEME SHOULD CONTAIN HARDCODED TEXT, NAMES, OR HARDCODED FOOTER LINKS**.

* **Site Name & Tagline**: Always use `{{ site_display_name() }}` and `{{ site_tagline() }}` (which automatically support multi-language translations and Admin settings).
* **Logo / Brand Icon**: Use `{{ site_nav_icon_abs }}`. If set, render an `<img>` tag; otherwise, render a default SVG or Bootstrap Icon fallback.
* **Language Switcher**: In `navbar.html`, always render the language selector using `available_locales` (preserving the current `?lang=` query parameter).
* **Translations & UI Labels**: Use official keys from the i18n dictionary (`ro.json`/`en.json`):
  - `footer.navigation`, `footer.information`, `footer.quickNav`, `footer.adminPanel`, `footer.craftedBy`, `footer.myAccount`
  - `nav.home`, `ui.admin`, `ui.login`, `ui.logout`, `ui.profile`, `blog.author`, `blog.readMore`
  - Use `{{ t('key') }}` or `{{ t_safe(translations, 'key', 'Fallback') }}`.
* **Theme Author Credits**: In `footer.html`, use:
  `© {{ year }} {{ site_display_name() }}. {{ t('footer.craftedBy') }} {{ theme_author }}.`
  (where `theme_author` is automatically extracted from the `author` field defined in `theme.json`).

---

## 📁 2. Theme File & Directory Structure

Every VlahX Core theme resides in the `/app/themes/<theme_slug>/` directory:

```text
/app/themes/<theme_slug>/
├── theme.json               # Theme metadata manifest (Required)
└── templates/               # Jinja2 template overrides (Optional but recommended)
    ├── base.html            # Main HTML layout wrapper
    ├── blog/
    │   ├── index.html       # Homepage / Article listing grid
    │   └── post.html        # Individual post detail page & static pages
    └── partials/
        ├── navbar.html      # Top navigation header
        └── footer.html      # Responsive 4-column footer
```

---

## ⚙️ 3. The `theme.json` Manifest File

The `theme.json` manifest defines the theme name, version, author, description, and configurable theme options:

```json
{
  name: Minimal Dark,
  slug: minimal,
  version: 1.0.0,
  author: VlahX Engine Team,
  website: https://vlahx.org,
  description: A sleek, responsive dark-mode minimal theme for blogs and news sites.,
  features: [
    dark_mode,
    template_hooks,
    custom_css
  ],
  options: {
    default_dark: true
  }
}
```

---

## 🔌 4. Template Hooks System

Themes in VlahX Core must support Template Hooks so plugins can inject UI components without modifying theme files:

- `{{ plugin_area_head | safe }}` — Injected inside `<head>` (for analytics, custom CSS, SEO meta tags).
- `{{ plugin_area_navbar | safe }}` — Injected inside `navbar.html` (for search widgets, profile links).
- `{{ plugin_area_login_options | safe }}` — Injected on login screens (for OAuth SSO buttons).
- `{{ plugin_area_post_after | safe }}` — Injected after article body (for comments, author box, social share buttons).
- `{{ plugin_area_footer | safe }}` — Injected inside `footer.html` (for copyright widgets, badges).

---

## 🚀 5. Publishing & Testing Themes

To test a new theme:
1. Place your theme folder in `app/themes/<theme_slug>/`.
2. Go to VlahX Admin Panel ➔ **Themes** (`/admin/themes`).
3. Click **Activate** on your new theme.
