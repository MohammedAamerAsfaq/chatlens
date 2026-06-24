from django.db import models


class ChatType(models.TextChoices):
    INDIVIDUAL = 'individual', 'Individual'
    GROUP = 'group', 'Group'


class WhatsAppChat(models.Model):
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='chats',
    )
    wa_chat_id = models.CharField(max_length=255)
    chat_type = models.CharField(max_length=50, choices=ChatType.choices)
    name = models.CharField(max_length=255, blank=True)
    contact = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chats',
    )
    last_message_at = models.DateTimeField(null=True, blank=True)
    unread_count = models.IntegerField(default=0)
    is_archived = models.BooleanField(default=False)
    raw_payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'whatsapp_chat'
        unique_together = [('account', 'wa_chat_id')]
        ordering = ['-last_message_at']

    def __str__(self):
        return self.name or self.wa_chat_id
