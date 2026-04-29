# template_starter

A drop-in Django app providing a clean, reusable look-and-feel for new projects.
It contains three styled pages — **Login**, **Dashboard**, and **Detail** — along
with all CSS, JS, and template filters needed to render them.

## What's inside

```
template_starter/
├── apps.py
├── urls.py                      # /login, /logout, /, /items/<id>/
├── views.py                     # Example views with placeholder data
├── templatetags/
│   └── template_filters.py      # currency, capacity_pct, format_number, ...
├── templates/template_starter/
│   ├── base.html                # Sidebar + topbar shell (extends to all pages)
│   ├── login.html               # Standalone login page
│   ├── dashboard.html           # Hero + stats + charts + tables + timeline
│   └── detail.html              # Hero + stat cards + 4 charts + history table
└── static/template_starter/
    ├── css/app.css              # All visual styles (sidebar, topbar, cards, ...)
    ├── js/app.js                # Sidebar/topbar/dropdown interactions
    └── img/                     # logo.png, logo.svg, avatar.png placeholders
```

External dependencies (loaded via CDN in `base.html` / `login.html`):
- Tailwind CSS (Play CDN)
- Inter font (Google Fonts)
- Feather icons
- Chart.js (loaded only on the dashboard and detail pages)

## How to use it in a new Django project

1. **Copy the app**: drop the `template_starter/` folder into your project root
   (next to `manage.py`).

2. **Register it** in `settings.py`:

   ```python
   INSTALLED_APPS = [
       # ...
       "template_starter",
   ]

   LOGIN_URL = "login"
   LOGIN_REDIRECT_URL = "dashboard"
   ```

   Make sure `STATICFILES_DIRS` / `STATIC_URL` are configured normally.

3. **Wire up the URLs** in your project `urls.py`:

   ```python
   from django.urls import include, path

   urlpatterns = [
       # ...
       path("", include("template_starter.urls")),
   ]
   ```

4. **Run it**:

   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py runserver
   ```

   Visit `http://localhost:8000/login/`, sign in, and you'll land on the
   dashboard. `/items/anything/` renders the detail page.

## Customizing for your app

- **Brand strings** (app name, brand initials, login footer) are passed via
  `BRAND_CONTEXT` in `views.py`. Edit them there or move them into a context
  processor / settings module.

- **Brand color** is `#EC1C24` (red). Search `app.css` and `base.html` for
  `EC1C24` / `d01920` / `brand` to swap it out. The Tailwind `brand` palette
  is defined inline at the top of `base.html`.

- **Sidebar nav** — edit the `<nav class="sidebar-nav">` block in
  `base.html`. Use `{% if page == 'foo' %}sidebar-link-active{% endif %}` to
  highlight the active link, and pass `page` from each view's context.

- **Logo / avatar** — replace the files in `static/template_starter/img/`.
  The logo gracefully falls back to a styled square with `brand_initials` if
  the image is missing.

- **Notifications** — populated from `BRAND_CONTEXT["notifications"]`. Each
  entry takes `icon`, `color`, `title`, `body`, `time`.

- **Dashboard / detail data** — replace the dummy data in `views.py` with
  your real querysets or service calls. The template variables expected by
  each page are documented below.

### Dashboard view context shape

```python
{
    "workspace": {"name", "id", "plan", "tagline", "last_login",
                  "contact_name", "contact_email", "contact_phone",
                  "period_start", "period_end"},
    "summary_stats": [{"label", "value", "icon", "color", "badge",
                       "badge_color", "progress", "caption"}, ...],
    "trend": {"labels": json, "actual": json, "target": json},
    "breakdown": {"labels": json, "amounts": json, "colors": json},
    "status_chart": {"labels": json, "counts": json, "colors": json},
    "allocation": {"labels": [...], "values": [...], "colors": [...]},
    "recent_items": [{"id", "name", "type", "type_color",
                      "date", "amount", "status", "status_color"}, ...],
    "activity_timeline": [{"icon", "color", "title", "description", "time"}, ...],
    "milestones": [{"date", "title", "status"}, ...],
    "quick_actions": [{"icon", "color", "title", "description", "href"}, ...],
}
```

### Detail view context shape

```python
{
    "summary": {
        "id", "name", "subtitle", "category", "icon", "icon_color",
        "stats": [{"label", "value", "unit", "icon", "color", "value_color"}, ...],
        "fields": [{"label", "value", "value_color"}, ...],
    },
    "history": [{"year", "month", "volume", "target_volume",
                 "actual", "target", "variance"}, ...],
    "annual": [{"year", "avg_actual", "avg_target", "avg_variance",
                "total_volume", "total_target"}, ...],
    "chart_data": {"labels", "actual_values", "target_values",
                   "volume_values", "target_volume_values", "variance_values"},
    "annual_chart": {"labels", "avg_actual", "avg_target"},
}
```

## Template filters

Available via `{% load template_filters %}`:

| Filter | Description |
|---|---|
| `currency` | `1234.5` → `$1,234.50` |
| `percentage` | `45.2` → `45.20%` |
| `capacity_pct` | `0.452` → `45.2%` |
| `format_number` | `1234567.89` → `1,234,567.89` |
| `month_name` | `4` → `Apr` |
| `floatsub` | `{{ a|floatsub:b }}` → `a - b` |
| `listget` | `{{ mylist|listget:idx }}` |

## Notes

- The starter ships with Tailwind via the Play CDN for ease of use. For
  production, swap to a built Tailwind pipeline.
- All page-specific JS (Chart.js init code) lives inside the page template's
  `{% block extra_js %}` so each page is self-contained.
- The base template provides `{% block extra_head %}` and `{% block topbar_left %}`
  hooks for per-page customization.
