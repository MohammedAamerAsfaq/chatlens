# Django + Vue Wiring In This Repo

This project does not serve a standalone `frontend/dist/index.html` directly from Django. Instead, Django renders a template shell and injects either:

- Vite dev-server assets during local frontend development
- built Vite assets from `backend/static/frontend/` in non-dev mode

The Vue SPA is mounted under `/ui/`, while `/api/` and `/admin/` remain normal Django routes.

## 1. Django URL Patterns That Serve The Vue App Or Catch-All Frontend Routes

Top-level URL configuration is in [backend/config/urls.py](/C:/Users/Administrator/OneDrive%20-%20Perfect%20Link%20Technologies/Documents/Visual%20Studio%20Code/Python/kiwitalk/backend/config/urls.py:4):

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("apps.core.web_urls")),
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.api_urls")),
    path("api/billing/", include("apps.billing.api_urls")),
    path("api/companies/", include("apps.tenants.company_api_urls")),
    path("api/whatsapp/", include("apps.whatsapp.api_urls")),
    path("api/inbox/", include("apps.inbox.api_urls")),
    path("api/templates/", include("apps.templates.api_urls")),
    path("api/broadcasts/", include("apps.broadcasts.api_urls")),
    path("api/broadcast-inbox/", include("apps.broadcasts.api_urls_inbox")),
    path("api/workflows/", include("apps.workflows.api_urls")),
    path("api/apiconsumer/", include("apps.apiconsumer.api_urls")),
    path("api/integrations/", include("apps.integrations.api_urls")),
    path("api/audit/", include("apps.auditlog.api_urls")),
    path("api/", include("apps.core.api_urls")),
]
```

Frontend-specific web routing is in [backend/apps/core/web_urls.py](/C:/Users/Administrator/OneDrive%20-%20Perfect%20Link%20Technologies/Documents/Visual%20Studio%20Code/Python/kiwitalk/backend/apps/core/web_urls.py:7):

```python
from django.urls import path
from django.urls import re_path

from apps.core import web_views


urlpatterns = [
    path("", web_views.root_view, name="frontend-root"),
    path("login/", web_views.login_view, name="frontend-login"),
    path("ui/", web_views.vue_spa_view, name="frontend-vue-spa"),
    re_path(r"^ui/(?P<path>.*)$", web_views.vue_spa_view, name="frontend-vue-spa-path"),
    path("app/", web_views.app_view, name="frontend-app"),
    path("app/overview/", web_views.app_page_view, {"page": "overview"}, name="frontend-app-overview"),
    path("app/whatsapp/", web_views.app_page_view, {"page": "whatsapp"}, name="frontend-app-whatsapp"),
    path("app/team/", web_views.app_page_view, {"page": "team"}, name="frontend-app-team"),
    path("app/inbox/", web_views.app_page_view, {"page": "inbox"}, name="frontend-app-inbox"),
    path("app/billing/", web_views.app_page_view, {"page": "billing"}, name="frontend-app-billing"),
    path("app/templates/", web_views.app_page_view, {"page": "templates"}, name="frontend-app-templates"),
    path("app/broadcasts/", web_views.app_page_view, {"page": "broadcasts"}, name="frontend-app-broadcasts"),
    path("app/workflows/", web_views.app_page_view, {"page": "workflows"}, name="frontend-app-workflows"),
    path("app/integrations/", web_views.app_page_view, {"page": "integrations"}, name="frontend-app-integrations"),
    path("app/audit/", web_views.app_page_view, {"page": "audit"}, name="frontend-app-audit"),
    path("app/admin/", web_views.app_page_view, {"page": "admin"}, name="frontend-app-admin"),
]
```

Key point:

- the SPA catch-all is only `^ui/(?P<path>.*)$`
- there is no global catch-all route that would accidentally swallow `/api/` or `/admin/`

## 2. The Django View Used To Return Vue's `index.html`

The SPA entry view is in [backend/apps/core/web_views.py](/C:/Users/Administrator/OneDrive%20-%20Perfect%20Link%20Technologies/Documents/Visual%20Studio%20Code/Python/kiwitalk/backend/apps/core/web_views.py:53):

```python
import json
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import redirect, render
from django.templatetags.static import static


def _load_frontend_bundle():
    dev_server_url = getattr(settings, "FRONTEND_DEV_SERVER_URL", "")
    if dev_server_url:
        return {
            "dev_server_url": dev_server_url,
            "entry_js_url": None,
            "css_urls": [],
            "favicon_url": f"{dev_server_url.rstrip('/')}/favicon.ico",
            "manifest_found": False,
        }

    manifest_path = Path(settings.BASE_DIR) / "static" / "frontend" / "manifest.json"
    if not manifest_path.exists():
        return {
            "dev_server_url": "",
            "entry_js_url": None,
            "css_urls": [],
            "favicon_url": static("frontend/favicon.ico"),
            "manifest_found": False,
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = manifest.get("index.html")
    if not entry:
        return {
            "dev_server_url": "",
            "entry_js_url": None,
            "css_urls": [],
            "favicon_url": static("frontend/favicon.ico"),
            "manifest_found": True,
        }

    css_urls = [static("frontend/" + css_path) for css_path in entry.get("css", [])]
    entry_js_url = static("frontend/" + entry["file"])
    return {
        "dev_server_url": "",
        "entry_js_url": entry_js_url,
        "css_urls": css_urls,
        "favicon_url": static("frontend/favicon.ico"),
        "manifest_found": True,
    }


def vue_spa_view(request, path=""):
    return render(
        request,
        "frontend/spa.html",
        {
            "frontend_bundle": _load_frontend_bundle(),
        },
    )
```

This does not return the built Vite HTML file directly. It renders Django template [backend/templates/frontend/spa.html](/C:/Users/Administrator/OneDrive%20-%20Perfect%20Link%20Technologies/Documents/Visual%20Studio%20Code/Python/kiwitalk/backend/templates/frontend/spa.html:1), which loads the Vue entry bundle:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>KiwiTalk</title>
    <link rel="icon" href="{{ frontend_bundle.favicon_url }}">
    {% if frontend_bundle.dev_server_url %}
        <script type="module" src="{{ frontend_bundle.dev_server_url }}/@vite/client"></script>
        <script type="module" src="{{ frontend_bundle.dev_server_url }}/src/app/main.ts"></script>
    {% elif frontend_bundle.entry_js_url %}
        {% for css_url in frontend_bundle.css_urls %}
            <link rel="stylesheet" href="{{ css_url }}">
        {% endfor %}
        <script type="module" src="{{ frontend_bundle.entry_js_url }}"></script>
    {% endif %}
</head>
<body>
    <div id="app"></div>
</body>
</html>
```

## 3. Relevant Django Settings For Templates And Static Assets

These settings are in [backend/config/settings/base.py](/C:/Users/Administrator/OneDrive%20-%20Perfect%20Link%20Technologies/Documents/Visual%20Studio%20Code/Python/kiwitalk/backend/config/settings/base.py:71):

```python
BASE_DIR = Path(__file__).resolve().parent.parent.parent

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

STATIC_URL = "/static/"
STATIC_ROOT = env("STATIC_ROOT", str(BASE_DIR / "staticfiles"))
STATICFILES_DIRS = [BASE_DIR / "static"]

FRONTEND_DEV_SERVER_URL = env("FRONTEND_DEV_SERVER_URL", "").rstrip("/")
```

What this means in this repo:

- `BASE_DIR` resolves to `backend/`
- Django templates are read from `backend/templates/`
- static source files are read from `backend/static/`
- collected static files go to `backend/staticfiles/` by default
- built frontend files are expected under `backend/static/frontend/`

The SPA loader specifically reads:

```python
manifest_path = Path(settings.BASE_DIR) / "static" / "frontend" / "manifest.json"
```

That resolves to:

```text
backend/static/frontend/manifest.json
```

## 4. Vue / Vite Build Config

The Vite config is in [frontend/vite.config.ts](/C:/Users/Administrator/OneDrive%20-%20Perfect%20Link%20Technologies/Documents/Visual%20Studio%20Code/Python/kiwitalk/frontend/vite.config.ts:1):

```ts
import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vueDevTools from "vite-plugin-vue-devtools";

export default defineConfig({
  plugins: [vue(), vueDevTools()],
  resolve: {
    alias: {
      "~": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/login": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/app": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/onboarding": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "../backend/static/frontend",
    assetsDir: "assets",
    manifest: "manifest.json",
    emptyOutDir: true,
  },
});
```

Important details:

- build output goes to `../backend/static/frontend`
- built asset files go under `backend/static/frontend/assets/`
- manifest is written as `backend/static/frontend/manifest.json`
- there is no explicit `base` setting
- because `base` is not set, Vite uses its default `"/"`
- this repo does not use Vue CLI `publicPath`; it uses Vite

The source HTML entry is [frontend/index.html](/C:/Users/Administrator/OneDrive%20-%20Perfect%20Link%20Technologies/Documents/Visual%20Studio%20Code/Python/kiwitalk/frontend/index.html:1):

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>KiwiTalk</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/app/main.ts"></script>
  </body>
</html>
```

## 5. Production Web Server Config And `/api/` / `/admin/` Exclusion

There is no checked-in production web server config in this repository. I did not find:

- `nginx.conf`
- Apache vhost config
- Caddyfile
- Docker or deployment config that defines the production routing layer

So there is no repo file to show for production web server routing.

What is implemented in Django code is clear:

- `/admin/` is explicitly handled by Django admin in `backend/config/urls.py`
- `/api/...` is explicitly handled by Django API routes in `backend/config/urls.py`
- the SPA catch-all only applies to `/ui/...` in `backend/apps/core/web_urls.py`

That means `/api/` and `/admin/` are excluded before the SPA route simply because the SPA catch-all is scoped to `/ui/*`, not because there is a global negative-regex catch-all.

## 6. Folder Layout Showing Where `frontend/dist`-Equivalent Output Goes

This repo does not use a literal `frontend/dist/` output directory in the current Vite build. Instead, Vite writes directly into Django's static tree.

Current effective layout:

```text
kiwitalk/
├── frontend/
│   ├── index.html
│   ├── vite.config.ts
│   ├── public/
│   └── src/
└── backend/
    ├── apps/
    │   └── core/
    │       ├── web_urls.py
    │       └── web_views.py
    ├── config/
    │   ├── urls.py
    │   └── settings/
    │       └── base.py
    ├── templates/
    │   └── frontend/
    │       └── spa.html
    ├── static/
    │   └── frontend/
    │       ├── manifest.json
    │       ├── favicon.ico
    │       └── assets/
    └── staticfiles/
```

The wiring path is:

1. frontend code lives in `frontend/src/`
2. `vite build` writes output into `backend/static/frontend/`
3. Django reads `backend/static/frontend/manifest.json`
4. `vue_spa_view()` renders `backend/templates/frontend/spa.html`
5. that template emits `<script>` and `<link>` tags pointing at Django static URLs such as `/static/frontend/assets/...`

## Summary

In this repo, the built Vue frontend is wired into Django like this:

- Django serves the SPA under `/ui/`
- Django renders `backend/templates/frontend/spa.html`
- the view reads either `FRONTEND_DEV_SERVER_URL` or `backend/static/frontend/manifest.json`
- Vite builds directly into `backend/static/frontend/`
- `/api/` and `/admin/` are not part of the SPA catch-all because the catch-all is limited to `/ui/*`
