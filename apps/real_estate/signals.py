"""Keep Real Estate embeddings synchronized through durable queue tasks."""

import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.real_estate.models import (
    Listing, Property, PropertyAddress, PropertyCandidate,
    PropertyMedia, PropertyRequirement, RealEstateOpportunity,
)

logger = logging.getLogger(__name__)


def _dispatch(callback, description):
    def run():
        try:
            callback()
        except Exception:
            logger.exception('Could not enqueue %s embedding refresh.', description)
    transaction.on_commit(run)


@receiver(post_save, sender=Property)
def property_saved(sender, instance, **kwargs):
    from apps.real_estate.services.embedding_dispatch import enqueue_property_dependencies

    revision = f'property:{instance.updated_at.isoformat()}'
    _dispatch(lambda: enqueue_property_dependencies(instance.pk, revision=revision), 'property')


@receiver([post_save, post_delete], sender=PropertyAddress)
@receiver([post_save, post_delete], sender=PropertyMedia)
def property_context_changed(sender, instance, **kwargs):
    from apps.real_estate.services.embedding_dispatch import enqueue_property_dependencies

    revision = f'{sender.__name__.lower()}:{instance.pk}:{timezone.now().isoformat()}'
    _dispatch(
        lambda: enqueue_property_dependencies(instance.property_id, revision=revision),
        'property context',
    )


@receiver(post_save, sender=Listing)
def listing_saved(sender, instance, **kwargs):
    from apps.real_estate.services.embedding_dispatch import enqueue_embedding

    revision = f'listing:{instance.updated_at.isoformat()}'
    _dispatch(lambda: enqueue_embedding('listing', instance.pk, revision=revision), 'listing')


@receiver(post_save, sender=PropertyRequirement)
def requirement_saved(sender, instance, **kwargs):
    from apps.real_estate.services.embedding_dispatch import enqueue_embedding

    revision = f'requirement:{instance.updated_at.isoformat()}'
    _dispatch(lambda: enqueue_embedding('requirement', instance.pk, revision=revision), 'requirement')


@receiver(post_save, sender=PropertyCandidate)
def candidate_saved(sender, instance, **kwargs):
    from apps.real_estate.services.embedding_dispatch import enqueue_embedding

    revision = f'candidate:{instance.updated_at.isoformat()}'
    _dispatch(lambda: enqueue_embedding('candidate', instance.pk, revision=revision), 'candidate')


@receiver(post_save, sender=RealEstateOpportunity)
def opportunity_saved(sender, instance, **kwargs):
    from apps.real_estate.services.embedding_dispatch import enqueue_embedding

    revision = f'opportunity:{instance.updated_at.isoformat()}'
    if hasattr(instance, 'requirement'):
        _dispatch(
            lambda: enqueue_embedding('requirement', instance.requirement.pk, revision=revision),
            'requirement',
        )
    if hasattr(instance, 'property_candidate'):
        _dispatch(
            lambda: enqueue_embedding('candidate', instance.property_candidate.pk, revision=revision),
            'candidate',
        )
