"""How campaign messages show prices: a primary currency plus optional converted ones.

A company keeps one set of campaign currency settings (SystemSettings key below); a
campaign may carry its own copy in currency_settings, which then replaces the company's
for that campaign. Rates are entered by hand: each other currency's rate says how much
of it one unit of the primary currency buys (1 AED = 0.2723 USD). The message itself is
composed in the browser (features/campaigns/currency.js) from these settings.
"""
import json
import re

from django.utils.timezone import now
from rest_framework.exceptions import ValidationError

SETTINGS_KEY = 'trading_campaign_currency_settings'
LABELS = ('code', 'symbol', 'none')
POSITIONS = ('prefix', 'suffix')
MAX_DECIMALS = 4
MAX_OTHER_CURRENCIES = 10
CODE_RE = re.compile(r'^[A-Z]{3}$')

DEFAULTS = {
    'primary': {'code': 'AED', 'symbol': 'AED'},
    'label': 'code',
    'label_position': 'prefix',
    'decimals': 2,
    'trim_zeros': True,
    'separator': ' / ',
    'others': [],
}


def _code(value, field):
    code = str(value or '').strip().upper()
    if not CODE_RE.match(code):
        raise ValidationError({field: 'Use a 3-letter currency code, e.g. AED or USD.'})
    return code


def _symbol(value, code, field):
    symbol = str(value or '').strip()
    if len(symbol) > 8:
        raise ValidationError({field: 'Keep the symbol to 8 characters or fewer.'})
    return symbol or code


def clean_currency_settings(data, previous=None):
    """Validated settings, or ValidationError naming the field. `previous` (the stored
    settings) keeps each other currency's rate_updated_at unless its rate changed."""
    if not isinstance(data, dict):
        raise ValidationError({'currency_settings': 'Currency settings must be an object.'})
    primary = data.get('primary') or {}
    primary_code = _code(primary.get('code'), 'primary.code')
    label = data.get('label', DEFAULTS['label'])
    if label not in LABELS:
        raise ValidationError({'label': 'Show the currency as its code, its symbol, or not at all.'})
    position = data.get('label_position', DEFAULTS['label_position'])
    if position not in POSITIONS:
        raise ValidationError({'label_position': 'Put the currency before or after the amount.'})
    try:
        decimals = int(data.get('decimals', DEFAULTS['decimals']))
    except (TypeError, ValueError):
        raise ValidationError({'decimals': 'Decimal places must be a whole number.'})
    if not 0 <= decimals <= MAX_DECIMALS:
        raise ValidationError({'decimals': f'Decimal places must be between 0 and {MAX_DECIMALS}.'})
    separator = data.get('separator', DEFAULTS['separator'])
    if not isinstance(separator, str) or not separator or len(separator) > 10:
        raise ValidationError({'separator': 'Use a short separator between currencies, e.g. " / ".'})

    previous_rates = {
        row.get('code'): row for row in ((previous or {}).get('others') or []) if isinstance(row, dict)
    }
    others, seen = [], {primary_code}
    raw_others = data.get('others') or []
    if not isinstance(raw_others, list) or len(raw_others) > MAX_OTHER_CURRENCIES:
        raise ValidationError({'others': f'Add at most {MAX_OTHER_CURRENCIES} other currencies.'})
    for index, row in enumerate(raw_others):
        if not isinstance(row, dict):
            raise ValidationError({f'others.{index}': 'Each currency needs a code and a rate.'})
        code = _code(row.get('code'), f'others.{index}.code')
        if code in seen:
            raise ValidationError({f'others.{index}.code': f'{code} is already listed.'})
        seen.add(code)
        try:
            rate = float(row.get('rate'))
        except (TypeError, ValueError):
            rate = 0
        if not rate > 0:
            raise ValidationError({f'others.{index}.rate': f'Enter how much {code} one {primary_code} buys (more than 0).'})
        before = previous_rates.get(code) or {}
        changed = before.get('rate') != rate
        others.append({
            'code': code,
            'symbol': _symbol(row.get('symbol'), code, f'others.{index}.symbol'),
            'rate': rate,
            'enabled': bool(row.get('enabled', True)),
            'rate_updated_at': now().isoformat() if changed or not before.get('rate_updated_at') else before['rate_updated_at'],
        })
    return {
        'primary': {'code': primary_code, 'symbol': _symbol(primary.get('symbol'), primary_code, 'primary.symbol')},
        'label': label,
        'label_position': position,
        'decimals': decimals,
        'trim_zeros': bool(data.get('trim_zeros', DEFAULTS['trim_zeros'])),
        'separator': separator,
        'others': others,
    }


def company_currency_settings(company):
    from apps.chatlens_core.models import SystemSettings

    row = SystemSettings.objects.filter(company=company, key=SETTINGS_KEY).first()
    if not row or not row.value:
        return json.loads(json.dumps(DEFAULTS))
    return json.loads(row.value)


def save_company_currency_settings(company, data):
    from apps.chatlens_core.models import SystemSettings

    cleaned = clean_currency_settings(data, previous=company_currency_settings(company))
    SystemSettings.objects.update_or_create(
        company=company,
        key=SETTINGS_KEY,
        defaults={
            'value': json.dumps(cleaned),
            'description': 'How campaign messages show prices: primary currency, label style, and converted currencies with manual rates.',
        },
    )
    return cleaned
