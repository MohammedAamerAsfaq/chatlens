import json


INQUIRY_PRODUCT_SAVE_KEY = 'trading_inquiry_product_save_settings'
INQUIRY_PRODUCT_SAVE_MANUAL = 'manual'
INQUIRY_PRODUCT_SAVE_AUTO = 'auto'

INQUIRY_PRODUCT_SAVE_DEFAULTS = {
    'mode': INQUIRY_PRODUCT_SAVE_MANUAL,
}


def get_inquiry_product_save_settings(company):
    from apps.chatlens_core.models import SystemSettings

    saved = {}
    obj = SystemSettings.objects.filter(
        company=company,
        key=INQUIRY_PRODUCT_SAVE_KEY,
    ).first()
    if obj and obj.value:
        try:
            saved = json.loads(obj.value)
        except (json.JSONDecodeError, TypeError):
            saved = {}
    mode = saved.get('mode')
    if mode not in {INQUIRY_PRODUCT_SAVE_MANUAL, INQUIRY_PRODUCT_SAVE_AUTO}:
        mode = INQUIRY_PRODUCT_SAVE_DEFAULTS['mode']
    return {**INQUIRY_PRODUCT_SAVE_DEFAULTS, 'mode': mode}


def save_inquiry_product_save_settings(company, mode: str):
    from apps.chatlens_core.models import SystemSettings

    if mode not in {INQUIRY_PRODUCT_SAVE_MANUAL, INQUIRY_PRODUCT_SAVE_AUTO}:
        raise ValueError('mode must be manual or auto')

    payload = {'mode': mode}
    SystemSettings.objects.update_or_create(
        company=company,
        key=INQUIRY_PRODUCT_SAVE_KEY,
        defaults={
            'value': json.dumps(payload),
            'description': 'Controls whether exact inventory matches are automatically saved as inquiry product trace rows.',
        },
    )
    return payload


def should_auto_save_inquiry_products(company) -> bool:
    return get_inquiry_product_save_settings(company)['mode'] == INQUIRY_PRODUCT_SAVE_AUTO
