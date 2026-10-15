import uuid

from django.conf import settings
from django.db import models


class RealEstateMockInquiryRun(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETE = 'complete'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'), (STATUS_RUNNING, 'Running'),
        (STATUS_COMPLETE, 'Complete'), (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE,
        related_name='real_estate_mock_inquiry_runs',
    )
    source_file_name = models.CharField(max_length=500)
    activity_type = models.CharField(max_length=30)
    requested_count = models.PositiveIntegerField()
    generated_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    task = models.ForeignKey(
        'task_management.BackgroundTask', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='real_estate_mock_runs',
    )
    mock_account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount', null=True, blank=True,
        on_delete=models.PROTECT, related_name='real_estate_mock_runs',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='real_estate_mock_runs_created',
    )
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_mock_inquiry_run'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', 'status', 'created_at'])]


class RealEstateMockInquiry(models.Model):
    STATUS_QUEUED = 'queued'
    STATUS_INGESTED = 'ingested'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'), (STATUS_INGESTED, 'Ingested'),
        (STATUS_FAILED, 'Failed'),
    ]

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE,
        related_name='real_estate_mock_inquiries',
    )
    run = models.ForeignKey(
        RealEstateMockInquiryRun, on_delete=models.CASCADE, related_name='inquiries',
    )
    source_record = models.ForeignKey(
        'real_estate.RealEstateMockSourceRecord', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='mock_inquiries',
    )
    activity_type = models.CharField(max_length=30)
    contact_name = models.CharField(max_length=255)
    contact_number = models.CharField(max_length=50)
    generated_message = models.TextField()
    provider_message_id = models.CharField(max_length=255, unique=True)
    live_task = models.ForeignKey(
        'task_management.BackgroundTask', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='real_estate_mock_inquiries',
    )
    message = models.OneToOneField(
        'whatsapp_bridge.WhatsAppMessage', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='real_estate_mock_inquiry',
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_QUEUED, db_index=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_mock_inquiry'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status', 'created_at']),
            models.Index(fields=['company', 'provider_message_id']),
        ]
