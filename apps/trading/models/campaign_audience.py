from django.db import models


class CampaignAudience(models.TextChoices):
    CONTACTS = 'contacts', 'Contacts'
    GROUPS = 'groups', 'Groups'


class CampaignMessageMode(models.TextChoices):
    FORMATTED = 'formatted', 'Preformatted Products'
    DIRECT = 'direct', 'Direct Message'
