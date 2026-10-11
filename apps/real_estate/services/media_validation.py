from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError


ALLOWED_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.webp', '.mp4', '.mov', '.pdf', '.doc', '.docx',
}


def validate_property_media_file(upload):
    if not upload:
        return
    max_bytes = getattr(settings, 'REAL_ESTATE_MEDIA_MAX_BYTES', 20 * 1024 * 1024)
    try:
        size = upload.size
    except (AttributeError, OSError):
        size = None
    if size is not None and size > max_bytes:
        raise ValidationError(f'Property media must not exceed {max_bytes // (1024 * 1024)} MB.')
    extension = Path(upload.name or '').suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError('Unsupported property media file type.')
