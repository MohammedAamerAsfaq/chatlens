"""Select the embedding execution transport without owning embedding logic."""
import logging

from apps.queue_management.runtime_settings import get_task_runtime_settings

logger = logging.getLogger(__name__)


TASK_KEYS = {
    'message': 'whatsapp.embed_message',
    'product': 'embedding.product',
    'product_alias': 'embedding.product_alias',
    'inquiry_product': 'embedding.inquiry_product',
    'non_inventory_product': 'embedding.non_inventory_product',
}


def uses_embedding_queue() -> bool:
    """Return whether new embedding work must be delegated to a durable worker."""
    return get_task_runtime_settings().embedding_mode == 'db_queue'


def _company_for_embedding(kind: str, object_id: int):
    """Resolve task ownership from the durable object being embedded."""
    if kind == 'message':
        from apps.tenancy.services.access import company_for_message
        from apps.whatsapp_bridge.models import WhatsAppMessage

        message = WhatsAppMessage.objects.select_related(
            'account__communication_account__company', 'account__owner',
        ).filter(pk=object_id).first()
        return company_for_message(message)

    from apps.trading.models import InquiryProduct, NonInventoryProduct, Product, ProductAlias

    lookups = {
        'product': lambda: Product.objects.filter(pk=object_id).values_list('company_id', flat=True).first(),
        'product_alias': lambda: ProductAlias.objects.filter(pk=object_id).values_list('product__company_id', flat=True).first(),
        'inquiry_product': lambda: InquiryProduct.objects.filter(pk=object_id).values_list('company_id', flat=True).first(),
        'non_inventory_product': lambda: NonInventoryProduct.objects.filter(pk=object_id).values_list('company_id', flat=True).first(),
    }
    try:
        company_id = lookups[kind]()
    except KeyError as exc:
        raise ValueError(f'Unsupported embedding kind: {kind}') from exc
    if not company_id:
        return None

    from apps.tenancy.models import Company
    return Company.objects.filter(pk=company_id).first()


def enqueue_embedding(kind: str, object_id: int, *, company=None, correlation_id=None) -> bool:
    """Create one idempotent embedding task when database queue mode is enabled.

    Returns False in thread mode so callers can retain their legacy in-process path.
    Queue errors deliberately propagate: silently falling back would defeat durability.
    """
    if not uses_embedding_queue():
        return False
    try:
        task_key = TASK_KEYS[kind]
    except KeyError as exc:
        raise ValueError(f'Unsupported embedding kind: {kind}') from exc

    company = company or _company_for_embedding(kind, object_id)
    if company is None:
        raise ValueError(f'Embedding task has no company owner: kind={kind} object_id={object_id}')

    from apps.queue_management.services import enqueue_task

    enqueue_task(
        task_key=task_key,
        payload={'version': 1, 'object_id': object_id},
        idempotency_key=f'embedding:{kind}:{object_id}',
        correlation_id=correlation_id or f'embedding:{kind}:{object_id}',
        company=company,
    )
    logger.info('embedding task enqueued | kind=%s object_id=%s', kind, object_id)
    return True


def enqueue_embeddings(kind: str, object_ids, *, company=None, correlation_id=None) -> bool:
    """Queue each record independently, allowing retries without replaying a batch."""
    if not uses_embedding_queue():
        return False
    for object_id in set(object_ids):
        enqueue_embedding(kind, object_id, company=company, correlation_id=correlation_id)
    return True
