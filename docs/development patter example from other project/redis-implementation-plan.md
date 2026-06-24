# Redis Implementation Plan

## Purpose

Introduce Redis into the app in a controlled way, with a clear rollback path and an explicit cache on/off switch.

## Scope

Phase the rollout instead of using Redis everywhere at once.

Recommended initial scope:
- Django cache backend
- cache-aware feature toggles

Deferred scope:
- session storage in Redis
- Celery / background jobs
- pub/sub
- distributed locks
- custom event systems

## Primary Goals

- reduce repeated read load for safe read-heavy areas
- prepare shared infrastructure for later async/background features
- preserve tenant isolation
- keep accounting and transactional correctness independent of Redis
- allow cache to be disabled quickly if behavior becomes unstable

## Non-Negotiable Rule

Redis must not become a correctness dependency for:
- voucher posting
- ledger validation
- company provisioning correctness
- inventory/accounting write transactions

Redis may improve performance, but core business correctness must still work without it.

## Rollout Strategy

### Phase 1

Implement Redis as the Django cache backend only.

Do not move sessions yet.

### Phase 2

After cache stability is verified:
- optionally move Django sessions to Redis

### Phase 3

After cache/session stability is verified:
- background jobs
- long-running provisioning queue
- long-running reporting jobs

## Configuration Requirements

Add environment-driven settings in `core/settings.py`.

Required settings:
- `REDIS_URL`
- `CACHE_ENABLED`
- `CACHE_KEY_PREFIX`
- optional `SESSIONS_IN_REDIS`

Recommended behavior:
- if `CACHE_ENABLED=False`, the app should fall back to a safe non-Redis cache backend
- if Redis is unavailable and cache is enabled, failures should degrade gracefully for cacheable paths

## Cache Enable / Disable Requirement

This is mandatory.

The app must support enabling or disabling cache without removing the Redis configuration itself.

Recommended setting:

```python
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "False").lower() == "true"
```

Expected behavior:
- `CACHE_ENABLED=True`
  - use Redis cache backend
- `CACHE_ENABLED=False`
  - use a safe fallback backend such as Django local-memory cache

Reason:
- if a cache-related issue appears in production, cache must be disabled quickly without reworking all Redis settings
- this gives a clean operational rollback path

## Recommended Backend Fallback

When cache is disabled:
- use Django local-memory cache for app continuity

Example intent:
- Redis configured but cache disabled -> app continues without distributed caching

This toggle should control cache use centrally in settings, not through scattered per-module conditions.

## Key Design Rules

### Environment Namespacing

Cache keys must include environment context.

Example:
- `cellusense:prod:...`
- `cellusense:uat:...`
- `cellusense:dev:...`

### Tenant Isolation

Any tenant-specific cached data must include tenant identity in the key.

Use one of:
- company code
- primary host
- tenant DB alias

Never share tenant-specific cached data across tenants.

### Explicit TTL

All non-session cache entries should have intentional TTL values.

Avoid indefinite cache entries unless there is a clear invalidation rule.

## Good First Cache Targets

Use Redis first for low-risk, read-heavy data:
- menu JSON
- widget definitions
- dashboard layout metadata
- report metadata/configuration lookups
- static-like settings lookups

## Avoid in Phase 1

Do not cache these first:
- voucher save/update/delete flows
- live balance correctness during write flows
- provisioning state transitions
- inventory/accounting mutation pipelines

## Invalidation Rules

For every cacheable object, define:
- who creates it
- who invalidates it
- fallback TTL

Examples:
- menu changes -> invalidate menu cache
- widget layout changes -> invalidate widget/layout cache
- report config changes -> invalidate report config cache

## Health and Diagnostics

Add a small operational check for Redis health.

Recommended:
- management command or diagnostics endpoint that verifies Redis connectivity
- clear logging when Redis is unavailable

## Failure Handling

Cache failures should not crash normal request handling for cacheable features.

Preferred pattern:
- try cache read
- on failure, log and continue with normal DB/service path
- try cache write opportunistically

## Suggested Implementation Order

1. Add env-driven Redis settings.
2. Add `CACHE_ENABLED` toggle.
3. Configure Django cache backend selection in settings.
4. Keep sessions on DB initially.
5. Cache one or two low-risk read paths.
6. Add invalidation hooks for those paths.
7. Test tenant isolation.
8. Add Redis health diagnostics.
9. Only after stability, consider Redis sessions.

## Testing Checklist

### Functional

- app runs with:
  - Redis configured and cache enabled
  - Redis configured and cache disabled
  - Redis unavailable and cache disabled

### Tenant Safety

- tenant A cached data never appears in tenant B
- host-specific/menu-specific navigation data remains isolated

### Operational

- cache toggle can be changed without code edits
- app startup and login remain stable when cache is disabled
- cacheable features still function when Redis is unreachable

## Implementation Decision

Recommended first implementation:
- Redis for cache only
- `CACHE_ENABLED` toggle mandatory
- sessions remain on DB for now

This gives the safest first step and the cleanest rollback behavior.
