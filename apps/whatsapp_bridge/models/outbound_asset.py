import uuid

from django.conf import settings
from django.db import models


def outbound_asset_path(instance, filename):
    extension = (filename.rsplit('.', 1)[-1] if '.' in filename else 'bin').lower()
    return f'outbound/{instance.company_id}/{instance.storage_key}.{extension}'


class OutboundAsset(models.Model):
    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='outbound_assets',
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='outbound_assets_uploaded',
    )
    storage_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    file = models.FileField(upload_to=outbound_asset_path)
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'whatsapp_outbound_asset'
        ordering = ['-created_at']
