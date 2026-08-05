import json


INQUIRY_PRODUCT_SAVE_KEY = 'trading_inquiry_product_save_settings'
V2_MATCHING_SETTINGS_KEY = 'trading_v2_matching_thresholds'
V2_MATCHING_THRESHOLDS_KEY = V2_MATCHING_SETTINGS_KEY
INQUIRY_PRODUCT_SAVE_MANUAL = 'manual'
INQUIRY_PRODUCT_SAVE_AUTO = 'auto'

INQUIRY_PRODUCT_SAVE_DEFAULTS = {
    'mode': INQUIRY_PRODUCT_SAVE_MANUAL,
}

V2_MATCHING_SETTINGS_DEFAULTS = {
    'pass2_candidate_max_distance': 0.55,
    'exact_auto_match_max_distance': 0.45,
    'pass2_candidates_per_line': 3,
    'pass2_batch_max_items': 15,
    'pass2_ai_timeout_seconds': 300,
}
V2_MATCHING_THRESHOLD_DEFAULTS = V2_MATCHING_SETTINGS_DEFAULTS


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


def _int_setting(value, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _required_positive_int(value, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{field_name} must be an integer') from exc
    if parsed <= 0:
        raise ValueError(f'{field_name} must be greater than zero')
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
        key=V2_MATCHING_SETTINGS_KEY,
    ).first()
    if obj and obj.value:
        try:
            saved = json.loads(obj.value)
        except (json.JSONDecodeError, TypeError):
            saved = {}

    return get_v2_matching_settings_from_payload(saved)


def get_v2_matching_settings(company):
    return get_v2_matching_thresholds(company)


def get_v2_matching_settings_from_payload(saved: dict) -> dict:
    return {
        'pass2_candidate_max_distance': _float_setting(
            saved.get('pass2_candidate_max_distance'),
            V2_MATCHING_SETTINGS_DEFAULTS['pass2_candidate_max_distance'],
        ),
        'exact_auto_match_max_distance': _float_setting(
            saved.get('exact_auto_match_max_distance'),
            V2_MATCHING_SETTINGS_DEFAULTS['exact_auto_match_max_distance'],
        ),
        'pass2_candidates_per_line': _int_setting(
            saved.get('pass2_candidates_per_line'),
            V2_MATCHING_SETTINGS_DEFAULTS['pass2_candidates_per_line'],
        ),
        'pass2_batch_max_items': _int_setting(
            saved.get('pass2_batch_max_items'),
            V2_MATCHING_SETTINGS_DEFAULTS['pass2_batch_max_items'],
        ),
        'pass2_ai_timeout_seconds': _int_setting(
            saved.get('pass2_ai_timeout_seconds'),
            V2_MATCHING_SETTINGS_DEFAULTS['pass2_ai_timeout_seconds'],
        ),
    }


def save_v2_matching_thresholds(
    company,
    pass2_candidate_max_distance,
    exact_auto_match_max_distance,
    pass2_candidates_per_line=None,
    pass2_batch_max_items=None,
    pass2_ai_timeout_seconds=None,
):
    from apps.chatlens_core.models import SystemSettings

    current = get_v2_matching_thresholds(company)
    payload = {
        'pass2_candidate_max_distance': _required_threshold(
            pass2_candidate_max_distance,
            'pass2_candidate_max_distance',
        ),
        'exact_auto_match_max_distance': _required_threshold(
            exact_auto_match_max_distance,
            'exact_auto_match_max_distance',
        ),
        'pass2_candidates_per_line': _required_positive_int(
            pass2_candidates_per_line if pass2_candidates_per_line is not None else current['pass2_candidates_per_line'],
            'pass2_candidates_per_line',
        ),
        'pass2_batch_max_items': _required_positive_int(
            pass2_batch_max_items if pass2_batch_max_items is not None else current['pass2_batch_max_items'],
            'pass2_batch_max_items',
        ),
        'pass2_ai_timeout_seconds': _required_positive_int(
            pass2_ai_timeout_seconds if pass2_ai_timeout_seconds is not None else current['pass2_ai_timeout_seconds'],
            'pass2_ai_timeout_seconds',
        ),
    }
    SystemSettings.objects.update_or_create(
        company=company,
        key=V2_MATCHING_SETTINGS_KEY,
        defaults={
            'value': json.dumps(payload),
            'description': 'V2 inquiry product matching settings: distance thresholds, candidate caps, batching, and AI timeout.',
        },
    )
    return payload


def save_v2_matching_settings(company, payload: dict):
    return save_v2_matching_thresholds(
        company,
        payload.get('pass2_candidate_max_distance'),
        payload.get('exact_auto_match_max_distance'),
        payload.get('pass2_candidates_per_line'),
        payload.get('pass2_batch_max_items'),
        payload.get('pass2_ai_timeout_seconds'),
    )
