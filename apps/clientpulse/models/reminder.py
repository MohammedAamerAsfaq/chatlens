import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ClientReminder(models.Model):
    STATUSES = [(value, value.title()) for value in (
        'pending', 'due', 'completed', 'snoozed', 'cancelled',
    )]
    PRIORITIES = [(value, value.title()) for value in ('low', 'normal', 'high', 'critical')]
    RECURRENCES = [(value, value.title()) for value in ('none', 'daily', 'weekly', 'monthly', 'custom')]

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='client_reminders')
    profile = models.ForeignKey('clientpulse.ClientProfile', on_delete=models.CASCADE, related_name='reminders')
    assigned_to = models.ForeignKey(
        'tenancy.CompanyMembership', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='assigned_client_reminders',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_at = models.DateTimeField()
    timezone = models.CharField(max_length=64, default='Asia/Dubai')
    priority = models.CharField(max_length=20, choices=PRIORITIES, default='normal')
    status = models.CharField(max_length=20, choices=STATUSES, default='pending')
    recurrence_type = models.CharField(max_length=20, choices=RECURRENCES, default='none')
    recurrence_rule = models.JSONField(default=dict, blank=True)
    snoozed_until = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='client_reminders_completed',
    )
    next_occurrence_at = models.DateTimeField(null=True, blank=True)
    series_key = models.UUIDField(default=uuid.uuid4, editable=False)
    occurrence_number = models.PositiveIntegerField(default=1)
    previous_occurrence = models.OneToOneField(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='generated_occurrence',
    )
    linked_from = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='linked_follow_ups',
    )
    thread_key = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='client_reminders_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clientpulse_reminder'
        ordering = ['due_at', '-priority']
        indexes = [
            models.Index(fields=['company', 'status', 'due_at'], name='cp_reminder_due_idx'),
            models.Index(fields=['assigned_to', 'status', 'due_at'], name='cp_reminder_assigned_idx'),
            models.Index(fields=['profile', 'due_at'], name='cp_reminder_profile_idx'),
        ]
        constraints = [models.UniqueConstraint(
            fields=['series_key', 'occurrence_number'], name='unique_reminder_series_occurrence',
        )]

    def clean(self):
        if self.profile_id and self.profile.company_id != self.company_id:
            raise ValidationError('Reminder profile must belong to the same company.')
        if self.assigned_to_id and self.assigned_to.company_id != self.company_id:
            raise ValidationError('Reminder assignee must belong to the same company.')
        if self.linked_from_id:
            if self.linked_from.company_id != self.company_id:
                raise ValidationError('Linked reminder must belong to the same company.')
            if self.linked_from.profile_id != self.profile_id:
                raise ValidationError('Linked reminders must belong to the same client.')
            if self.linked_from.status != 'completed':
                raise ValidationError('A follow-up can only be linked to a completed reminder.')
            if self.thread_key != self.linked_from.thread_key:
                raise ValidationError('Linked reminders must retain the same thread key.')
        if self.recurrence_type == 'custom':
            try:
                interval_days = int(self.recurrence_rule.get('interval_days', 0))
            except (TypeError, ValueError):
                interval_days = 0
            if interval_days <= 0:
                raise ValidationError('Custom recurrence requires a positive interval_days value.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ClientReminderNotification(models.Model):
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='client_reminder_notifications')
    reminder = models.OneToOneField(ClientReminder, on_delete=models.CASCADE, related_name='notification')
    recipient = models.ForeignKey(
        'tenancy.CompanyMembership', null=True, blank=True, on_delete=models.CASCADE,
        related_name='client_reminder_notifications',
    )
    delivered_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'clientpulse_reminder_notification'
        ordering = ['-delivered_at']

    def clean(self):
        if self.reminder_id and self.reminder.company_id != self.company_id:
            raise ValidationError('Reminder notification company mismatch.')
        if self.recipient_id and self.recipient.company_id != self.company_id:
            raise ValidationError('Reminder notification recipient company mismatch.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
