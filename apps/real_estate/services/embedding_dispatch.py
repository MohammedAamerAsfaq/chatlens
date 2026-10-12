"""Durably dispatch Real Estate embedding work to its isolated queue."""

import logging

from django.db.models import Q
from django.utils import timezone

from apps.queue_management.services import enqueue_task
from apps.real_estate.models import EmbeddingStatus
from .embedding_service import embedding_spec, load_target, mark_pending

logger = logging.getLogger(__name__)

TASK_KEYS = {
    'property': 'real_estate.embed_property',
    'listing': 'real_estate.embed_listing',
    'requirement': 'real_estate.embed_requirement',
    'candidate': 'real_estate.embed_candidate',
}


def enqueue_embedding(kind, object_id, *, company=None, revision=''):
    target = load_target(kind, object_id)
    company = company or target.company
    if target.company_id != company.pk:
        raise ValueError('Real Estate embedding target belongs to another company.')
    revision = revision or target.updated_at.isoformat()
    task = enqueue_task(
        task_key=TASK_KEYS[kind],
        payload={'version': 1, 'company_id': company.pk, 'object_id': object_id},
        idempotency_key=f'real-estate-embedding:{kind}:{object_id}:{revision}',
        correlation_id=f'real-estate-embedding:{kind}:{object_id}',
        company=company,
    )
    mark_pending(kind, target)
    logger.info('Real Estate embedding enqueued | kind=%s object_id=%s', kind, object_id)
    return task


def enqueue_property_dependencies(property_id, *, revision=''):
    from apps.real_estate.models import Listing, Property

    property_record = Property.objects.select_related('company').get(pk=property_id)
    enqueue_embedding('property', property_id, company=property_record.company, revision=revision)
    for listing_id in Listing.objects.filter(property_id=property_id).values_list('id', flat=True):
        enqueue_embedding(
            'listing', listing_id, company=property_record.company,
            revision=f'{revision}:listing:{listing_id}',
        )


def embedding_status(company):
    result = {'total': 0, 'embedded': 0, 'pending': 0, 'error': 0, 'skipped': 0, 'missing': 0, 'entities': {}}
    for kind in TASK_KEYS:
        target_model, embedding_model, target_field, _ = embedding_spec(kind)
        total = target_model.objects.filter(company=company).count()
        counts = {
            status: embedding_model.objects.filter(company=company, status=status).count()
            for status in EmbeddingStatus.values
        }
        counts['total'] = total
        counts['missing'] = max(0, total - sum(counts[status] for status in EmbeddingStatus.values))
        result['entities'][kind] = counts
        result['total'] += total
        for key in ('embedded', 'pending', 'error', 'skipped', 'missing'):
            result[key] += counts[key]
    return result


def enqueue_backfill(company):
    counts = {kind: 0 for kind in TASK_KEYS}
    revision = f'backfill:{timezone.now().isoformat()}'
    for kind in TASK_KEYS:
        target_model, _, _, _ = embedding_spec(kind)
        targets = target_model.objects.filter(company=company).filter(
            Q(embedding_record__isnull=True) |
            ~Q(embedding_record__status=EmbeddingStatus.EMBEDDED)
        ).select_related('company')
        for target in targets.iterator():
            enqueue_embedding(kind, target.pk, company=company, revision=revision)
            counts[kind] += 1
    return {'enqueued': sum(counts.values()), 'entities': counts}
