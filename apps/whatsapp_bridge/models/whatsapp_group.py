from django.db import models


class ParticipantRole(models.TextChoices):
    MEMBER = 'member', 'Member'
    ADMIN = 'admin', 'Admin'
    SUPERADMIN = 'superadmin', 'Superadmin'


class WhatsAppGroup(models.Model):
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='groups',
    )
    wa_group_id = models.CharField(max_length=255)
    # Link to the existing WhatsAppChat row for this group (nullable — chat may arrive before metadata)
    chat = models.OneToOneField(
        'whatsapp_bridge.WhatsAppChat',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='group',
    )
    name = models.CharField(max_length=512, blank=True)
    description = models.TextField(blank=True)
    owner_jid = models.CharField(max_length=255, blank=True)
    # Points to the parent community group when this is a sub-group
    community = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sub_groups',
    )
    # True when this group row represents a community umbrella (not a regular group)
    is_community = models.BooleanField(default=False)
    participant_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'whatsapp_group'
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['account', 'wa_group_id'], name='unique_account_wa_group_id'),
        ]

    def __str__(self):
        return self.name or self.wa_group_id


class WhatsAppGroupParticipant(models.Model):
    group = models.ForeignKey(
        WhatsAppGroup,
        on_delete=models.CASCADE,
        related_name='participants',
    )
    wa_jid = models.CharField(max_length=255)
    contact = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='group_memberships',
    )
    role = models.CharField(
        max_length=20,
        choices=ParticipantRole.choices,
        default=ParticipantRole.MEMBER,
    )
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'whatsapp_group_participant'
        ordering = ['-role', 'wa_jid']
        constraints = [
            models.UniqueConstraint(fields=['group', 'wa_jid'], name='unique_group_participant'),
        ]

    def __str__(self):
        return f'{self.wa_jid} in {self.group}'
