"""
Database-backed request/token throttle for AI provider calls — the direct fix for a
real Voyage AI free-tier account (3 requests/minute, 10K tokens/minute) getting 429'd
whenever several product/alias embeds landed within the same minute. Every embedding
call (live messages, products, aliases) shares one active provider config, so they all
draw from the same real-world quota; this coordinates them through one shared window
instead of each firing independently and racing for the same limit.

State lives in the AIProviderRequestLog table, not process memory — a plain in-memory
counter only sees requests made by its own process, which silently under-counts real
usage the moment more than one process shares the same API key (a `manage.py shell`
invocation running alongside `runserver`, multiple production worker processes, etc.).
Confirmed this mattered in practice: an in-memory version passed a same-process burst
test cleanly, then still got 429'd on the very next request from a separate process,
because that process's own counter started fresh at zero.

No-ops entirely (skips the DB round-trip too) when a config has no configured limit —
the existing/default behavior for any provider that hasn't had a rate_limit_rpm/
rate_limit_tpm set in its extra_config (AI Providers screen).
"""
import time
from datetime import timedelta

WINDOW_SECONDS = 60


def estimate_tokens(text: str) -> int:
    """Rough token estimate (chars/4) — same heuristic already used elsewhere in this
    codebase for cost estimates. A rate-limit guard needs a reasonable approximation,
    not a billing-accurate tokenizer."""
    return max(1, len(text or '') // 4)


def acquire(config_id: int, rpm, tpm, tokens_needed: int, poll_interval: float = 1.0) -> None:
    """Blocks until a request for `tokens_needed` tokens fits within the given per-minute
    request/token budget for this provider config, then reserves the slot (an
    AIProviderRequestLog row) and returns. `rpm`/`tpm` of None or 0 disables that half of
    the check; both falsy means no throttling at all.

    Not perfectly race-free under simultaneous check-then-insert from two processes at
    the exact same instant — an accepted tradeoff for a rate limiter whose job is
    avoiding sustained 429s from a strict-but-not-adversarial limit, not guaranteeing
    exactly N requests/minute never exceeded by one under a hostile race.
    """
    if not rpm and not tpm:
        return

    from django.db.models import Sum
    from django.utils import timezone
    from .models import AIProviderRequestLog

    while True:
        cutoff = timezone.now() - timedelta(seconds=WINDOW_SECONDS)
        # Opportunistic prune — keeps this table tiny without needing a separate cron.
        AIProviderRequestLog.objects.filter(config_id=config_id, created_at__lt=cutoff).delete()

        recent = AIProviderRequestLog.objects.filter(config_id=config_id, created_at__gte=cutoff)
        current_requests = recent.count()
        current_tokens = recent.aggregate(total=Sum('tokens'))['total'] or 0

        requests_ok = (not rpm) or (current_requests < rpm)
        tokens_ok = (not tpm) or (current_tokens + tokens_needed <= tpm)

        if requests_ok and tokens_ok:
            AIProviderRequestLog.objects.create(config_id=config_id, tokens=tokens_needed)
            return

        time.sleep(poll_interval)
