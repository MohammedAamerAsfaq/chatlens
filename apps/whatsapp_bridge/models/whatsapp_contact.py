from django.db import models


class WhatsAppContact(models.Model):
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='contacts',
    )
    wa_contact_id = models.CharField(max_length=255, blank=True)
    # LID alias for this contact (nullable). Set when Baileys exposes the mapping.
    # wa_contact_id is ALWAYS the canonical phone JID; lid_jid is the alias only.
    lid_jid = models.CharField(max_length=255, blank=True, null=True)
    # WhatsApp username alias (e.g. "ahmed.mobile"). Populated from contacts.set when
    # the contact has set a username. Like lid_jid, this is an alias — wa_contact_id
    # remains the canonical phone JID.
    username = models.CharField(max_length=35, blank=True, null=True)
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
        constraints = [
            models.UniqueConstraint(
                fields=['account', 'lid_jid'],
                condition=models.Q(lid_jid__isnull=False) & ~models.Q(lid_jid=''),
                name='unique_account_lid_jid',
            ),
            models.UniqueConstraint(
                fields=['account', 'username'],
                condition=models.Q(username__isnull=False) & ~models.Q(username=''),
                name='unique_account_username',
            ),
        ]

    def __str__(self):
        return self.display_name or self.phone_number or self.wa_contact_id
