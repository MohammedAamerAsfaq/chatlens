from django.db import models


class CampaignAudience(models.TextChoices):
    CONTACTS = 'contacts', 'Contacts'
    GROUPS = 'groups', 'Groups'
