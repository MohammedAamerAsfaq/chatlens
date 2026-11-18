from django.db import models


class ClientReminderPhrase(models.Model):
    """A company's preset reminder action ("Send price list") offered in the reminder form.

    Choosing one copies its text into the reminder title, so editing or deleting a phrase
    never changes reminders already created from it.
    """
    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='client_reminder_phrases',
    )
    text = models.CharField(max_length=255)
    normalized_text = models.CharField(max_length=255)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clientpulse_reminder_phrase'
        ordering = ['position', 'id']
        constraints = [models.UniqueConstraint(
            fields=['company', 'normalized_text'], name='unique_reminder_phrase_per_company',
        )]

    def save(self, *args, **kwargs):
        self.text = ' '.join(self.text.split())
        self.normalized_text = self.text.casefold()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.text
