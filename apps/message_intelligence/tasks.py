import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_message_analysis(self, message_id: int):
    """Run intent detection and sentiment analysis on a message."""
    try:
        from apps.whatsapp_bridge.models import WhatsAppMessage
        from .models import MessageAnalysis, Intent
        message = WhatsAppMessage.objects.get(pk=message_id)
        MessageAnalysis.objects.get_or_create(
            message=message,
            defaults={'intent': Intent.UNKNOWN},
        )
        logger.info(f'process_message_analysis completed | message_id={message_id}')
    except Exception as exc:
        logger.exception(f'process_message_analysis failed | message_id={message_id}')
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def generate_message_embedding(self, message_id: int):
    """Generate and store pgvector embedding for a message."""
    try:
        from .services.embedding_service import embed_message
        stored = embed_message(message_id)
        if stored:
            logger.info('generate_message_embedding | done | message_id=%s', message_id)
    except Exception as exc:
        logger.exception('generate_message_embedding | failed | message_id=%s', message_id)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def extract_product_mentions(self, message_id: int):
    """Extract product mentions from message text."""
    try:
        logger.info(f'extract_product_mentions queued | message_id={message_id}')
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task
def refresh_daily_analytics(account_id: int, date: str):
    """Refresh daily analytics aggregates for an account."""
    logger.info(f'refresh_daily_analytics | account_id={account_id} | date={date}')
