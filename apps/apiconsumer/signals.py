from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='whatsapp_bridge.OutboundMessageEvent')
def outbound_message_event_saved(sender, instance, created, **kwargs):
    if not created:
        return
    from .services import enqueue_outbound_status_webhooks

    enqueue_outbound_status_webhooks(instance)
