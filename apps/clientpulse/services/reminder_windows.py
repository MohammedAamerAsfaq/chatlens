from datetime import datetime, time, timedelta

from django.utils import timezone


def local_day_window(now=None):
    """Return timezone-aware bounds for the current local calendar day."""
    current = timezone.localtime(now or timezone.now())
    start = timezone.make_aware(
        datetime.combine(current.date(), time.min),
        timezone.get_current_timezone(),
    )
    return start, start + timedelta(days=1)
