"""Atomic ordered-capacity routing for configured KiwiRouter instances."""
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .router_models import KiwiRouter, KiwiRouterReservation, KiwiRoutingDecision
from .provider_deadline import call_provider_with_deadline


@dataclass
class RouterSelection:
    member: object | None
    reservation: object | None
    available_at: object | None
    reason: str = ''


class KiwiRouterCapacityError(RuntimeError):
    def __init__(self, available_at):
        super().__init__('No KiwiRouter member has available capacity.')
        self.available_at = available_at


def estimate_tokens(messages):
    return sum(len(str(message.get('content', ''))) for message in messages) // 4


def reserve_agent(router_id, *, workflow_key, correlation_id, task_id=None,
                  estimated_input_tokens=0, estimated_output_tokens=0):
    """Reserve the first preferred member with current capacity.

    Member rows are locked in priority order so concurrent workers cannot reserve
    the same final RPM/TPM/concurrency slot. Capacity shortage returns a durable
    deferral time; callers must retry the task rather than wait in-process.
    """
    now = timezone.now()
    with transaction.atomic():
        router = KiwiRouter.objects.select_for_update().get(pk=router_id, is_active=True)
        members = list(router.members.select_for_update().select_related('provider_config').filter(
            is_enabled=True,
            provider_config__capability=router.capability,
        ))
        for member in members:
            timeout_seconds = (
                member.request_timeout_seconds
                or member.router.default_request_timeout_seconds
            )
            member.reservations.filter(
                status__in=[
                    KiwiRouterReservation.STATUS_RESERVED,
                    KiwiRouterReservation.STATUS_DISPATCHED,
                ],
                expires_at__lte=now,
            ).update(status=KiwiRouterReservation.STATUS_EXPIRED, released_at=now)
            window = now - timedelta(minutes=1)
            recent = member.reservations.filter(reserved_at__gte=window).exclude(
                status=KiwiRouterReservation.STATUS_EXPIRED,
            )
            request_count = recent.count()
            token_count = recent.aggregate(value=Sum('estimated_input_tokens'))['value'] or 0
            active_count = member.reservations.filter(status__in=[
                KiwiRouterReservation.STATUS_RESERVED,
                KiwiRouterReservation.STATUS_DISPATCHED,
            ], expires_at__gt=now).count()
            needed_tokens = estimated_input_tokens + estimated_output_tokens
            if member.rpm_limit is not None and request_count >= member.rpm_limit:
                continue
            if member.tpm_limit is not None and token_count + needed_tokens > member.tpm_limit:
                continue
            if member.max_concurrency is not None and active_count >= member.max_concurrency:
                continue
            reservation = KiwiRouterReservation.objects.create(
                member=member,
                correlation_id=correlation_id,
                task_id=task_id,
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
                expires_at=now + timedelta(seconds=timeout_seconds),
            )
            KiwiRoutingDecision.objects.create(
                router=router, member=member, provider_config=member.provider_config,
                task_id=task_id, correlation_id=correlation_id, workflow_key=workflow_key,
                strategy=router.strategy, decision=KiwiRoutingDecision.DECISION_SELECTED,
                reason='Reserved preferred member capacity.',
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
            )
            return RouterSelection(member, reservation, None)

        available_at = now + timedelta(minutes=1)
        KiwiRoutingDecision.objects.create(
            router=router, task_id=task_id, correlation_id=correlation_id,
            workflow_key=workflow_key, strategy=router.strategy,
            decision=KiwiRoutingDecision.DECISION_DEFERRED,
            reason='All enabled router members are at configured capacity.',
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
        )
        return RouterSelection(None, None, available_at, 'No router member has capacity.')


def complete_reservation(reservation, *, succeeded):
    reservation.status = (
        KiwiRouterReservation.STATUS_SUCCEEDED if succeeded
        else KiwiRouterReservation.STATUS_FAILED
    )
    reservation.released_at = timezone.now()
    reservation.save(update_fields=['status', 'released_at'])


def mark_reservation_dispatched(reservation):
    """Record that the provider call is about to leave this process."""
    reservation.status = KiwiRouterReservation.STATUS_DISPATCHED
    reservation.save(update_fields=['status'])


def execute_agent(router_id, *, messages, workflow_key, correlation_id, task_id=None, **kwargs):
    """Route one agent request without the legacy blocking provider limiter."""
    input_tokens = estimate_tokens(messages)
    selection = reserve_agent(
        router_id, workflow_key=workflow_key, correlation_id=correlation_id,
        task_id=task_id, estimated_input_tokens=input_tokens,
    )
    if selection.member is None:
        raise KiwiRouterCapacityError(selection.available_at)
    reservation = selection.reservation
    configured_timeout = (
        selection.member.request_timeout_seconds
        or selection.member.router.default_request_timeout_seconds
    )
    caller_timeout = kwargs.pop('request_timeout', None)
    timeout = min(configured_timeout, caller_timeout) if caller_timeout else configured_timeout
    try:
        mark_reservation_dispatched(reservation)
        response = call_provider_with_deadline(
            selection.member.provider_config_id,
            messages,
            timeout_seconds=timeout,
            request_timeout=timeout,
            **kwargs,
        )
    except Exception:
        complete_reservation(reservation, succeeded=False)
        raise
    complete_reservation(reservation, succeeded=True)
    return response, selection.member
