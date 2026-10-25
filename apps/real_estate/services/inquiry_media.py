from django.utils.text import slugify

from apps.real_estate.models import InquiryMedium


DEFAULT_MEDIA = (
    ('phone', 'Phone'),
    ('email', 'Email'),
    ('whatsapp', 'WhatsApp'),
    ('telegram', 'Telegram'),
    ('signal', 'Signal'),
    ('website', 'Website'),
    ('meeting', 'Meeting'),
)


def seed_default_inquiry_media(company):
    existing = set(InquiryMedium.objects.filter(company=company).values_list('code', flat=True))
    missing = [
        InquiryMedium(company=company, code=code, name=name, sort_order=index * 10)
        for index, (code, name) in enumerate(DEFAULT_MEDIA, 1)
        if code not in existing
    ]
    if missing:
        InquiryMedium.objects.bulk_create(missing, ignore_conflicts=True)
    return InquiryMedium.objects.filter(company=company)


def unique_medium_code(company, name):
    root = slugify(name)[:70] or 'medium'
    code = root
    suffix = 2
    while InquiryMedium.objects.filter(company=company, code=code).exists():
        code = f'{root[:70 - len(str(suffix))]}-{suffix}'
        suffix += 1
    return code
