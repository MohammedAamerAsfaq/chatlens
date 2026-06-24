from django.db import models


class WhatsAppContact(models.Model):
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='contacts',
    )
    wa_contact_id = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    display_name = models.CharField(max_length=255, blank=True)
    push_name = models.CharField(max_length=255, blank=True)
    is_business = models.BooleanField(default=False)
    raw_payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'whatsapp_contact'
        unique_together = [('account', 'wa_contact_id')]
        ordering = ['display_name']

    def __str__(self):
        return self.display_name or self.phone_number or self.wa_contact_id
