"""Generate Real Estate vectors without modifying authoritative source rows."""

import hashlib
import logging

from apps.ai_providers.manager import ai_manager
from apps.real_estate.models import EmbeddingStatus
from .embedding_documents import (
    DOCUMENT_VERSION, candidate_document, listing_document,
    property_document, requirement_document,
)

logger = logging.getLogger(__name__)


def embedding_spec(kind):
    from apps.real_estate.models import (
        CandidateEmbedding, Listing, ListingEmbedding, Property,
        PropertyCandidate, PropertyEmbedding, PropertyRequirement,
        RequirementEmbedding,
    )

    specs = {
        'property': (Property, PropertyEmbedding, 'property', property_document),
        'listing': (Listing, ListingEmbedding, 'listing', listing_document),
        'requirement': (PropertyRequirement, RequirementEmbedding, 'requirement', requirement_document),
        'candidate': (PropertyCandidate, CandidateEmbedding, 'candidate', candidate_document),
    }
    try:
        return specs[kind]
    except KeyError as exc:
        raise ValueError(f'Unsupported Real Estate embedding kind: {kind}') from exc


def target_queryset(kind, target_model):
    if kind == 'property':
        return target_model.objects.select_related('address').prefetch_related('media')
    if kind == 'listing':
        return target_model.objects.select_related('property__address').prefetch_related('property__media')
    return target_model.objects.select_related('opportunity')


def load_target(kind, object_id):
    target_model, _, _, _ = embedding_spec(kind)
    return target_queryset(kind, target_model).get(pk=object_id)


def mark_pending(kind, target):
    _, embedding_model, target_field, _ = embedding_spec(kind)
    embedding_model.objects.update_or_create(
        **{target_field: target},
        defaults={'company': target.company, 'status': EmbeddingStatus.PENDING, 'error': ''},
    )


def embed_real_estate(kind, object_id, company_id):
    _, embedding_model, target_field, builder = embedding_spec(kind)
    target = load_target(kind, object_id)
    if target.company_id != company_id:
        raise ValueError('Real Estate embedding target belongs to another company.')
    lookup = {target_field: target}
    document = builder(target).strip()
    if not document:
        embedding_model.objects.update_or_create(
            **lookup,
            defaults={
                'company': target.company, 'embedding': None, 'embedding_model': '',
                'metadata': {'document_version': DOCUMENT_VERSION},
                'status': EmbeddingStatus.SKIPPED, 'error': 'No embeddable content.',
            },
        )
        return False

    config = ai_manager.active_config('embedding', company=target.company)
    if config is None:
        embedding_model.objects.update_or_create(
            **lookup,
            defaults={
                'company': target.company, 'status': EmbeddingStatus.ERROR,
                'error': 'No active embedding provider configured for this company.',
            },
        )
        return False
    try:
        vector = ai_manager.embed(document, company=target.company)
    except Exception as exc:
        embedding_model.objects.update_or_create(
            **lookup,
            defaults={'company': target.company, 'status': EmbeddingStatus.ERROR, 'error': str(exc)},
        )
        logger.exception('Real Estate embedding failed | kind=%s object_id=%s', kind, object_id)
        raise

    embedding_model.objects.update_or_create(
        **lookup,
        defaults={
            'company': target.company,
            'embedding': vector,
            'embedding_model': config.model,
            'metadata': {
                'provider': config.provider,
                'dimensions': len(vector),
                'document_version': DOCUMENT_VERSION,
                'document_sha256': hashlib.sha256(document.encode('utf-8')).hexdigest(),
            },
            'status': EmbeddingStatus.EMBEDDED,
            'error': '',
        },
    )
    logger.info('Real Estate embedding stored | kind=%s object_id=%s dims=%s', kind, object_id, len(vector))
    return True
