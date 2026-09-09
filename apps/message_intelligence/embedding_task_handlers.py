"""Durable task handlers for the embedding domain."""
from apps.task_management.registry import task_handler, validate_embedding_payload


def _run(payload, function_name):
    """Import execution code lazily so worker startup has no provider side effects."""
    from apps.message_intelligence.services import embedding_service

    stored = getattr(embedding_service, function_name)(payload['object_id'])
    return {'object_id': payload['object_id'], 'embedded': bool(stored)}


@task_handler(
    key='whatsapp.embed_message', default_queue='embeddings',
    payload_validator=validate_embedding_payload,
)
def embed_message(payload, context):
    return _run(payload, 'embed_message')


@task_handler(
    key='embedding.product', default_queue='embeddings',
    payload_validator=validate_embedding_payload,
)
def embed_product(payload, context):
    return _run(payload, 'embed_product')


@task_handler(
    key='embedding.product_alias', default_queue='embeddings',
    payload_validator=validate_embedding_payload,
)
def embed_product_alias(payload, context):
    return _run(payload, 'embed_product_alias')


@task_handler(
    key='embedding.inquiry_product', default_queue='embeddings',
    payload_validator=validate_embedding_payload,
)
def embed_inquiry_product(payload, context):
    return _run(payload, 'embed_inquiry_product')


@task_handler(
    key='embedding.non_inventory_product', default_queue='embeddings',
    payload_validator=validate_embedding_payload,
)
def embed_non_inventory_product(payload, context):
    return _run(payload, 'embed_non_inventory_product')
