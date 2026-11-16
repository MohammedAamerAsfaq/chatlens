"""Which emoji stands for each catalog Color value in outgoing WhatsApp text.

The company sets one emoji per Color attribute value it actually uses (Settings →
AI Instructions → Color emoji). Lookup is by the exact stored value: nothing is
guessed from a colour's name, so a new catalog colour shows up here unmapped
until someone picks its emoji.
"""

import json

from django.db.models import Count

from apps.chatlens_core.models import SystemSettings
from apps.trading.models import ProductAttribute

COLOR_EMOJI_KEY = 'trading_color_emoji'
COLOR_ATTRIBUTE_KEY = 'Color'
MAX_EMOJI_LENGTH = 16


class ColorEmojiError(ValueError):
    """An invalid mapping; the message is user-facing."""


def saved_color_emoji(company):
    obj = SystemSettings.objects.filter(company=company, key=COLOR_EMOJI_KEY).first()
    if not obj or not obj.value:
        return {}
    return json.loads(obj.value)


def color_emoji_settings(company):
    """Every Color value in the catalog (plus any mapped value no longer used), with its emoji."""
    mapping = saved_color_emoji(company)
    counts = dict(
        ProductAttribute.objects.filter(product__company=company, key=COLOR_ATTRIBUTE_KEY)
        .values_list('value').annotate(n=Count('id')).order_by()
    )
    colors = sorted(set(counts) | set(mapping), key=str.casefold)
    return {
        'emoji': mapping,
        'colors': [
            {'color': color, 'emoji': mapping.get(color, ''), 'products': counts.get(color, 0)}
            for color in colors
        ],
    }


def save_color_emoji(company, emoji):
    if not isinstance(emoji, dict):
        raise ColorEmojiError('emoji must be an object of Color value → emoji.')
    mapping = {}
    for color, value in emoji.items():
        if not isinstance(color, str) or not color.strip():
            raise ColorEmojiError('Every Color value must be non-empty text.')
        if value is None:
            continue
        if not isinstance(value, str):
            raise ColorEmojiError(f'The emoji for {color} must be text.')
        value = value.strip()
        if len(value) > MAX_EMOJI_LENGTH:
            raise ColorEmojiError(f'The emoji for {color} is too long ({MAX_EMOJI_LENGTH} characters at most).')
        if value:
            mapping[color.strip()] = value
    SystemSettings.objects.update_or_create(
        company=company, key=COLOR_EMOJI_KEY,
        defaults={
            'value': json.dumps(mapping, ensure_ascii=False),
            'description': 'Emoji used for each catalog Color attribute value in WhatsApp replies and selling offers.',
        },
    )
    return color_emoji_settings(company)
