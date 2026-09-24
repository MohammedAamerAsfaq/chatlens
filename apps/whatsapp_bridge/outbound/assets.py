import hashlib
from pathlib import Path

from django.conf import settings

from apps.whatsapp_bridge.models import OutboundAsset


ALLOWED_IMAGE_SIGNATURES = (
    ('image/jpeg', '.jpg', lambda head: head.startswith(b'\xff\xd8\xff')),
    ('image/png', '.png', lambda head: head.startswith(b'\x89PNG\r\n\x1a\n')),
    ('image/webp', '.webp', lambda head: head[:4] == b'RIFF' and head[8:12] == b'WEBP'),
)


def _detect_image(upload):
    head = upload.read(16)
    upload.seek(0)
    for mime_type, extension, matches in ALLOWED_IMAGE_SIGNATURES:
        if matches(head):
            return mime_type, extension
    raise ValueError('unsupported_image_type')


def create_outbound_asset(*, company, uploaded_by, upload):
    max_bytes = getattr(settings, 'OUTBOUND_IMAGE_MAX_BYTES', 10 * 1024 * 1024)
    if not upload or upload.size <= 0:
        raise ValueError('empty_image')
    if upload.size > max_bytes:
        raise ValueError('image_too_large')

    mime_type, extension = _detect_image(upload)
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    original_name = Path(upload.name or f'image{extension}').name[:255]
    upload.name = f'image{extension}'
    return OutboundAsset.objects.create(
        company=company,
        uploaded_by=uploaded_by,
        file=upload,
        original_filename=original_name,
        mime_type=mime_type,
        size_bytes=upload.size,
        sha256=digest.hexdigest(),
    )
