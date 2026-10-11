from dataclasses import dataclass

from apps.real_estate.models import (
    ActivityType,
    ClassificationDecision,
    ClassificationStatus,
)


@dataclass(frozen=True)
class ClassificationOutcome:
    status: str
    activity_type: str | None


def outcome_for_decision(decision: str) -> ClassificationOutcome:
    normalized = str(decision or '').strip().lower()
    if normalized in ActivityType.values:
        return ClassificationOutcome(
            status=ClassificationStatus.CLASSIFIED,
            activity_type=normalized,
        )
    if normalized == ClassificationDecision.NOT_REAL_ESTATE:
        return ClassificationOutcome(
            status=ClassificationStatus.NOT_REAL_ESTATE,
            activity_type=None,
        )
    if normalized == ClassificationDecision.NEEDS_REVIEW:
        return ClassificationOutcome(
            status=ClassificationStatus.NEEDS_REVIEW,
            activity_type=None,
        )
    raise ValueError(f'Unsupported Real Estate classification decision: {decision!r}')
