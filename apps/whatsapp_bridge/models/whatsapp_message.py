from django.db import models


class MessageDirection(models.TextChoices):
    INBOUND = 'inbound', 'Inbound'
    OUTBOUND = 'outbound', 'Outbound'


class MessageType(models.TextChoices):
    TEXT = 'text', 'Text'
    IMAGE = 'image', 'Image'
    AUDIO = 'audio', 'Audio'
    VIDEO = 'video', 'Video'
    DOCUMENT = 'document', 'Document'
    STICKER = 'sticker', 'Sticker'
    LOCATION = 'location', 'Location'
    CONTACT = 'contact', 'Contact'
    UNKNOWN = 'unknown', 'Unknown'


class WhatsAppMessage(models.Model):
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='messages',
    )
    chat = models.ForeignKey(
        'whatsapp_bridge.WhatsAppChat',
        on_delete=models.CASCADE,
        related_name='messages',
    )
    contact = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
    )
    provider_message_id = models.CharField(max_length=255)
    sender_number = models.CharField(max_length=50, blank=True)
    direction = models.CharField(max_length=20, choices=MessageDirection.choices)
    message_type = models.CharField(max_length=50, choices=MessageType.choices)
    message_text = models.TextField(blank=True)
    message_time = models.DateTimeField()
    has_media = models.BooleanField(default=False)
    media_mime_type = models.CharField(max_length=255, blank=True)
    media_file_name = models.CharField(max_length=255, blank=True)
    media_url = models.CharField(max_length=500, blank=True, default='')
    raw_payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'whatsapp_message'
        unique_together = [('account', 'provider_message_id')]
        ordering = ['-message_time']
        indexes = [
            models.Index(fields=['account', 'message_time']),
            models.Index(fields=['chat', 'message_time']),
            models.Index(fields=['direction']),
            models.Index(fields=['message_type']),
        ]

    def __str__(self):
        return f"{self.direction} | {self.message_type} | {self.message_time}"
