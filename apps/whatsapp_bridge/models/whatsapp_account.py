from django.db import models
from django.contrib.auth.models import User


class SessionStatus(models.TextChoices):
    PENDING_QR = 'pending_qr', 'Pending QR'
    QR_GENERATED = 'qr_generated', 'QR Generated'
    CONNECTED = 'connected', 'Connected'
    DISCONNECTED = 'disconnected', 'Disconnected'
    LOGGED_OUT = 'logged_out', 'Logged Out'
    ERROR = 'error', 'Error'


class WhatsAppAccount(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='whatsapp_accounts')
    display_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    session_status = models.CharField(
        max_length=50,
        choices=SessionStatus.choices,
        default=SessionStatus.PENDING_QR,
    )
    worker_session_id = models.CharField(max_length=255, blank=True)
    last_connected_at = models.DateTimeField(null=True, blank=True)
    last_disconnected_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    sync_history = models.BooleanField(default=True)
    history_days = models.IntegerField(null=True, blank=True)  # null = all time
    idle_disconnect_minutes = models.IntegerField(default=0)   # 0 = disabled
    auto_download_media = models.BooleanField(default=True)
    ai_parsing_enabled = models.BooleanField(default=False)
    # Set by the worker when it detects a degraded session it can't self-heal by
    # reconnecting — repeated Signal-protocol decrypt failures or post-connect
    # handshake timeouts. The connection can look "connected" the whole time (WhatsApp
    # mobile shows the linked device as active) while silently receiving nothing,
    # because reconnecting reuses the same corrupted local key state. The only real
    # fix is a fresh QR re-link, which establishes a brand-new session.
    connection_unhealthy = models.BooleanField(default=False)
    connection_unhealthy_reason = models.TextField(blank=True)
    connection_unhealthy_since = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'whatsapp_account'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.display_name or self.phone_number} ({self.session_status})"
