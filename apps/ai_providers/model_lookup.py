"""Look up one model by name for an AI provider.

Two questions, answered separately:

1. Is the name right? Checked against the provider's own model list. Providers without
   a models endpoint get a one-word test call with that model instead.
2. What does it cost and how much can it take? Read from OpenRouter's public model
   catalog (the provider's own catalog when the provider *is* OpenRouter): input/output
   price per 1M tokens, context window, longest reply, and the request parameters the
   model accepts. Providers' own APIs do not publish prices, so for other providers this
   is OpenRouter's listing of the same model, and the result says so.
"""

import difflib
import re

import requests
from django.utils import timezone

from .manager import build_provider
from .models import AIProviderConfig
from .providers.base import friendly_error

CATALOG_URL = 'https://openrouter.ai/api/v1/models'
MAX_SUGGESTIONS = 8

# The vendor OpenRouter lists each provider's own models under. Providers missing here
# host other vendors' models (Groq, Together, LM Studio, ...), so any vendor may match.
CATALOG_VENDOR = {
    AIProviderConfig.PROVIDER_OPENAI: 'openai',
    AIProviderConfig.PROVIDER_ANTHROPIC: 'anthropic',
    AIProviderConfig.PROVIDER_GOOGLE: 'google',
    AIProviderConfig.PROVIDER_DEEPSEEK: 'deepseek',
    AIProviderConfig.PROVIDER_QWEN: 'qwen',
    AIProviderConfig.PROVIDER_KIMI: 'moonshotai',
    AIProviderConfig.PROVIDER_GLM: 'z-ai',
    AIProviderConfig.PROVIDER_MISTRAL: 'mistralai',
    AIProviderConfig.PROVIDER_GROK: 'x-ai',
    AIProviderConfig.PROVIDER_PERPLEXITY: 'perplexity',
    AIProviderConfig.PROVIDER_COHERE: 'cohere',
}


def lookup_model(config: AIProviderConfig) -> dict:
    """config: an (unsaved is fine) AIProviderConfig whose .model is the name to check."""
    name = (config.model or '').strip()
    if not name:
        raise ValueError('Enter a model name to look up.')
    provider = build_provider(config)
    is_openrouter = config.provider == AIProviderConfig.PROVIDER_OPENROUTER

    catalog, catalog_error = _catalog(provider if is_openrouter else None)
    if is_openrouter and catalog:
        known_ids = [row['id'] for row in catalog]
    else:
        known_ids = _provider_model_ids(provider)

    result = {'requested': name, 'suggestions': [], 'checked_at': timezone.now().isoformat()}
    if known_ids:
        model_id, how = _match_name(name, known_ids)
        result['method'] = 'model_list'
        if model_id:
            result.update(verified=True, model=model_id, detail=(
                f'{config.get_provider_display()} lists "{model_id}".' if how == 'exact' else
                f'{config.get_provider_display()} lists it as "{model_id}" - the name will be saved that way.'
            ))
        else:
            result.update(verified=False, model=name, suggestions=_suggestions(name, known_ids), detail=(
                f'{config.get_provider_display()} has no model named "{name}" '
                f'among the {len(known_ids)} it lists.'
            ))
    else:
        provider.model = name
        test = provider.test_connection()
        result['method'] = 'test_call'
        result['model'] = name
        if test.get('ok'):
            result.update(verified=True, detail=(
                f'{config.get_provider_display()} does not publish a model list, so a one-word test '
                f'call was made with "{name}" and it answered.'
            ))
        else:
            result.update(verified=False, detail=(
                f'{config.get_provider_display()} does not publish a model list, and a test call with '
                f'"{name}" failed: {test.get("error") or "no reason given"}'
            ))

    row = _catalog_row(catalog, config.provider, result['model']) if catalog else None
    if row:
        result['info'] = _info(row)
        result['info_source'] = 'provider' if is_openrouter else 'openrouter_catalog'
        result['info_detail'] = (
            'Rates and limits published by OpenRouter for this model.' if is_openrouter else
            f'Rates and limits from OpenRouter\'s public catalog listing "{row["id"]}". '
            f'{config.get_provider_display()} usually charges the same list price; check its '
            'pricing page if your account has a different rate.'
        )
    else:
        result['info'] = None
        result['info_source'] = ''
        result['info_detail'] = (
            f'Could not read the model catalog: {catalog_error}' if catalog_error else
            f'OpenRouter\'s public catalog has no listing for "{result["model"]}", so rates and '
            'limits are not available. Enter them by hand if you need them.'
        )
    return result


def _catalog(openrouter_provider=None):
    """All catalog rows, or ([], reason) when it cannot be read."""
    try:
        if openrouter_provider is not None:
            response = openrouter_provider.session.get(f'{openrouter_provider.base_url}/models', timeout=15)
        else:
            response = requests.get(CATALOG_URL, timeout=15)
        response.raise_for_status()
        rows = [row for row in response.json().get('data', []) if row.get('id')]
        return rows, ''
    except Exception as exc:
        return [], friendly_error(exc)


def _provider_model_ids(provider) -> list:
    list_models = getattr(provider, 'list_models', None)
    if not callable(list_models):
        return []
    try:
        return list(list_models() or [])
    except Exception:
        return []


def _match_name(name, ids):
    """(id, how): exact, then ignoring case, then the part after a "vendor/" or "models/"
    prefix (OpenRouter and Gemini list ids that way)."""
    if name in ids:
        return name, 'exact'
    folded = name.casefold()
    for model_id in ids:
        if model_id.casefold() == folded:
            return model_id, 'case'
    tails = [model_id for model_id in ids if model_id.casefold().rsplit('/', 1)[-1] == folded]
    if len(tails) == 1:
        return tails[0], 'prefix'
    return None, ''


def _suggestions(name, ids):
    folded = name.casefold()
    by_folded = {model_id.casefold(): model_id for model_id in ids}
    close = difflib.get_close_matches(folded, list(by_folded), n=MAX_SUGGESTIONS, cutoff=0.6)
    contains = [key for key in by_folded if folded in key and key not in close]
    return [by_folded[key] for key in (close + sorted(contains, key=len))][:MAX_SUGGESTIONS]


def _key(name):
    """Compare names written slightly differently: case, dots vs dashes, a release date
    or a "-001" style version at the end."""
    key = re.sub(r'[\s._]+', '-', name.strip().casefold())
    return re.sub(r'-(\d{8}|\d{4}-\d{2}-\d{2}|\d{3})$', '', key)


def _catalog_row(rows, provider, model_id):
    if provider == AIProviderConfig.PROVIDER_OPENROUTER:
        return next((row for row in rows if row['id'] == model_id), None)
    wanted = _key(model_id.rsplit('/', 1)[-1])
    matches = [
        row for row in rows
        if ':' not in row['id'] and _key(row['id'].split('/', 1)[-1]) == wanted
    ]
    vendor = CATALOG_VENDOR.get(provider)
    if vendor:
        # A provider's own model is only that vendor's listing, never a namesake elsewhere.
        return next((row for row in matches if row['id'].split('/', 1)[0] == vendor), None)
    return matches[0] if len(matches) == 1 else None


def _per_million(value):
    try:
        price = float(value) * 1_000_000
    except (TypeError, ValueError):
        return None
    return round(price, 4) if price >= 0 else None


def _info(row):
    pricing = row.get('pricing') or {}
    top = row.get('top_provider') or {}
    architecture = row.get('architecture') or {}
    return {
        'catalog_id': row['id'],
        'name': row.get('name') or row['id'],
        'description': (row.get('description') or '').strip()[:600],
        'context_length': row.get('context_length') or top.get('context_length'),
        'max_output_tokens': top.get('max_completion_tokens'),
        'input_cost_per_million': _per_million(pricing.get('prompt')),
        'output_cost_per_million': _per_million(pricing.get('completion')),
        'supported_parameters': sorted(row.get('supported_parameters') or []),
        'input_modalities': architecture.get('input_modalities') or [],
    }
