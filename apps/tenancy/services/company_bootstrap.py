import json

from apps.chatlens_core.models import SystemSettings
from apps.trading.services.trading_settings_service import (
    INQUIRY_PRODUCT_SAVE_DEFAULTS,
    INQUIRY_PRODUCT_SAVE_KEY,
    V2_MATCHING_SETTINGS_DEFAULTS,
    V2_MATCHING_SETTINGS_KEY,
)


REQUIRED_COMPANY_SETTINGS = {
    INQUIRY_PRODUCT_SAVE_KEY: INQUIRY_PRODUCT_SAVE_DEFAULTS,
    V2_MATCHING_SETTINGS_KEY: V2_MATCHING_SETTINGS_DEFAULTS,
}


def seed_required_company_settings(company):
    """Create settings that must exist before a new tenant can operate safely."""
    for key, value in REQUIRED_COMPANY_SETTINGS.items():
        SystemSettings.objects.get_or_create(
            company=company,
            key=key,
            defaults={
                'value': json.dumps(value),
                'description': 'Required defaults created during company enrollment.',
            },
        )
