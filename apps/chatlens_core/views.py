import json
from pathlib import Path

from django.conf import settings
from django.shortcuts import render
from django.templatetags.static import static


def _load_frontend_bundle():
    dev_server_url = getattr(settings, 'FRONTEND_DEV_SERVER_URL', '').rstrip('/')
    if dev_server_url:
        return {
            'dev_server_url': dev_server_url,
            'entry_js_url': None,
            'css_urls': [],
            'favicon_url': f'{dev_server_url}/favicon.ico',
            'manifest_found': False,
        }

    manifest_path = Path(settings.BASE_DIR) / 'static' / 'frontend' / 'manifest.json'
    if not manifest_path.exists():
        return {
            'dev_server_url': '',
            'entry_js_url': None,
            'css_urls': [],
            'favicon_url': static('frontend/favicon.ico'),
            'manifest_found': False,
        }

    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    entry = manifest.get('index.html')
    if not entry:
        return {
            'dev_server_url': '',
            'entry_js_url': None,
            'css_urls': [],
            'favicon_url': static('frontend/favicon.ico'),
            'manifest_found': True,
        }

    return {
        'dev_server_url': '',
        'entry_js_url': static('frontend/' + entry['file']),
        'css_urls': [static('frontend/' + css_path) for css_path in entry.get('css', [])],
        'favicon_url': static('frontend/favicon.ico'),
        'manifest_found': True,
    }


def frontend_spa(request, path=''):
    return render(request, 'frontend/spa.html', {
        'frontend_bundle': _load_frontend_bundle(),
    })
