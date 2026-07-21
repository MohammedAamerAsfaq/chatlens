from django.conf import settings
from django.db import models


class WorkerAlert(models.Model):
    """
    Structured, queryable, UI-visible record of a worker-side failure that would
    otherwise only exist as an unstructured line in a raw log file — decrypt
    failures, handshake timeouts, silently-skipped history messages, batch
    persistence failures, uncaught exceptions, and any future failure of the same
    shape. Root-cause fix for the class of bug where something goes wrong deep in
    the pipeline (often inside Baileys itself, before our own drop-reporting can
    even see it) and the only trace is a raw text file nobody is watching.

    Every occurrence is logged here immediately — this is not a threshold/count
    mechanism like WhatsAppAccount.connection_unhealthy (which flags a session as
    needing re-linking only after repeated failures). This table is the audit
    trail; connection_unhealthy is a derived, session-level escalation built on
    top of the same underlying events.
    """
    ALERT_TYPE_CHOICES = [
        ('decrypt_failure',        'Message decrypt failure'),
        ('handshake_timeout',      'Connection handshake timeout'),
        ('history_build_failed',   'History message dropped while building payload'),
        ('batch_persist_failed',   'Message lost persisting a history/live batch'),
        ('batch_partial_failure',  'Batch ingest reported partial errors'),
        ('drop_report_failed',     'Worker could not report a dropped message to Django'),
        ('unresolved_message_failed', 'Worker could not preserve an unresolved (LID-blocked) message'),
        ('uncaught_exception',     'Uncaught exception in a worker event handler'),
        ('other',                  'Other'),
    ]
    SEVERITY_CHOICES = [
        ('warning', 'Warning'),
        ('error',   'Error'),
    ]

    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='worker_alerts',
        null=True, blank=True,
    )
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPE_CHOICES)
    severity   = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='warning')
    message    = models.TextField()
    context    = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )

    class Meta:
        db_table = 'whatsapp_worker_alert'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', 'created_at']),
            models.Index(fields=['alert_type', 'created_at']),
            models.Index(fields=['acknowledged_at']),
        ]

    def __str__(self):
        return f"{self.alert_type} | {self.severity} | {self.created_at}"
