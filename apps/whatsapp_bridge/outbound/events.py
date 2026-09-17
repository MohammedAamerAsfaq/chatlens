def record_event(message, event_type, *, actor='', detail='', metadata=None):
    from apps.whatsapp_bridge.models import OutboundMessageEvent

    return OutboundMessageEvent.objects.create(
        message=message,
        event_type=event_type,
        actor=actor,
        attempt_number=message.attempt_count,
        detail=detail,
        metadata=metadata or {},
    )
