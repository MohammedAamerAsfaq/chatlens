import json


INQUIRY_PRODUCT_SAVE_KEY = 'trading_inquiry_product_save_settings'
V2_MATCHING_THRESHOLDS_KEY = 'trading_v2_matching_thresholds'
INQUIRY_PRODUCT_SAVE_MANUAL = 'manual'
INQUIRY_PRODUCT_SAVE_AUTO = 'auto'

INQUIRY_PRODUCT_SAVE_DEFAULTS = {
    'mode': INQUIRY_PRODUCT_SAVE_MANUAL,
}

V2_MATCHING_THRESHOLD_DEFAULTS = {
    'pass2_candidate_max_distance': 0.55,
    'exact_auto_match_max_distance': 0.45,
}


def _float_setting(value, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed < 0:
        return default
    return parsed


def _required_threshold(value, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{field_name} must be a number') from exc
    if parsed < 0:
        raise ValueError(f'{field_name} must be zero or greater')
    return parsed


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


def get_v2_matching_thresholds(company):
    from apps.chatlens_core.models import SystemSettings

    saved = {}
    obj = SystemSettings.objects.filter(
        company=company,
        key=V2_MATCHING_THRESHOLDS_KEY,
    ).first()
    if obj and obj.value:
        try:
            saved = json.loads(obj.value)
        except (json.JSONDecodeError, TypeError):
            saved = {}

    return {
        key: _float_setting(saved.get(key), default)
        for key, default in V2_MATCHING_THRESHOLD_DEFAULTS.items()
    }


def save_v2_matching_thresholds(company, pass2_candidate_max_distance, exact_auto_match_max_distance):
    from apps.chatlens_core.models import SystemSettings

    payload = {
        'pass2_candidate_max_distance': _required_threshold(
            pass2_candidate_max_distance,
            'pass2_candidate_max_distance',
        ),
        'exact_auto_match_max_distance': _required_threshold(
            exact_auto_match_max_distance,
            'exact_auto_match_max_distance',
        ),
    }
    SystemSettings.objects.update_or_create(
        company=company,
        key=V2_MATCHING_THRESHOLDS_KEY,
        defaults={
            'value': json.dumps(payload),
            'description': 'Distance thresholds for V2 inquiry product candidate selection and exact auto-match acceptance.',
        },
    )
    return payload
