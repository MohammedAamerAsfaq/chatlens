# Exception Handling and Failure Visibility Principle

> **Status:** Active engineering principle.
> **Prepared:** 2026-07-22
> **Scope:** All backend, worker, frontend-adjacent API, background-job, and integration code in ChatLens.
> **Priority:** Strict rule — intended to guide every future implementation, refactor, and review.

---

## 1. Purpose

ChatLens handles message ingestion, identity resolution, AI processing, sync, operational alerts, and tenant/business data. In this kind of system, the cost of a failure is often not the exception itself, but the system continuing in a misleading state where:

- the failure is hidden,
- the original cause is lost,
- an alternate path partially succeeds,
- operators think the system is healthy when it is not,
- later debugging becomes extremely slow or impossible.

This document establishes a strict development principle:

**Failures must be explicit, observable, and traceable.**

ChatLens should prefer:

- clear failure,
- structured logging,
- durable reporting where appropriate,
- direct root-cause visibility,

over:

- silent suppression,
- hidden fallback logic,
- shadow persistence paths,
- alternate execution branches that mask the original problem.

---

## 2. Core Rule

### 2.1 Primary principle

Whenever a code path can fail in a way that matters to correctness, persistence, delivery, identity resolution, synchronization, or business processing:

- the exception must be handled deliberately,
- the failure must be logged with useful context,
- the failure must be reported through the proper system channel if operator action may be needed,
- the system must not silently pretend success,
- and the code must not introduce a hidden fallback route that makes the failure harder to diagnose.

### 2.2 Non-negotiable rule

**Never implement a fallback mechanism that silently handles failure by switching to an alternate route or alternate implementation when that would obscure the real failure.**

That includes:

- suppressing the exception and returning success anyway,
- swallowing errors and continuing as if nothing happened,
- silently switching to a different data source,
- silently writing to a second storage path and treating the operation as “done”,
- silently downgrading a hard requirement into a best-effort path without explicit reporting,
- creating shadow behavior that future debugging cannot easily reconstruct.

If a fallback exists at all, it must be:

- explicit,
- documented,
- observable,
- auditable,
- and clearly reported as fallback behavior rather than normal success.

---

## 3. Strict Development Standard

## 3.1 Every meaningful `try/except` or `try/catch` must answer five questions

Any exception-handling block in ChatLens must make the answers to these questions obvious:

1. **What failed?**
2. **Why can it fail here?**
3. **What exact context is logged?**
4. **Does the caller/operator/system know this failed?**
5. **Why is the chosen post-failure behavior safer than re-raising or hard-failing?**

If those answers are unclear, the exception handling is not acceptable.

## 3.2 “Catch and continue” is not acceptable by default

A `try/except` or `try/catch` that only prevents a crash is insufficient unless the failure is also:

- visible in logs,
- visible in structured records where needed,
- and justified in comments or surrounding design.

Examples of unacceptable patterns:

```python
try:
    do_important_work()
except Exception:
    pass
```

```js
try {
  doImportantWork()
} catch (_) {
}
```

```python
try:
    save_data()
except Exception:
    return {"status": "ok"}
```

These patterns are banned for meaningful code paths.

---

## 4. Where Exception Handling Is Required

The following classes of code require deliberate exception handling and explicit failure visibility.

## 4.1 External integrations

Examples:

- WhatsApp worker <-> Django HTTP calls
- Baileys event handling
- future Telegram/Signal/Discord connectors
- future Gmail/Exchange/IMAP connectors
- AI provider requests
- Redis / Celery / database-adjacent integration boundaries

Rules:

- never assume remote success,
- catch integration failures at the boundary,
- log request/operation context,
- report operator-relevant failures through structured records,
- never silently route around a failed provider call unless that fallback is explicitly designed and visible.

## 4.2 Persistence and state transitions

Examples:

- message ingest
- unresolved-message preservation
- dropped-message recording
- contact/group sync updates
- inquiry creation/update
- product changes
- tenant/account setup

Rules:

- if data is expected to be persisted, failure to persist must never be treated as normal success,
- failures must not be hidden behind secondary writes that create ambiguous sources of truth,
- if the system records a fallback artifact, it must still clearly report that the primary operation failed.

## 4.3 Background processing

Examples:

- embedding
- classification
- automation rules
- unresolved-message recovery
- async sync/replay tasks

Rules:

- background tasks must never fail invisibly,
- exceptions must always be captured with task context,
- operator-facing reporting is required when failures affect correctness or recovery,
- “daemon thread died” or “async task disappeared” without reporting is unacceptable.

## 4.4 Permission, tenant, and account resolution

Examples:

- company resolution
- provider selection
- company membership checks
- communication account ownership checks

Rules:

- authorization or tenant-resolution failures must be explicit,
- never silently substitute a broader scope,
- never “default” to a permissive path because strict resolution failed.

---

## 5. Logging Standard

## 5.1 Log with structured context

Every meaningful exception log should contain the contextual identifiers required to investigate the failure.

Examples of useful context:

- company id
- communication account id
- WhatsApp account id / session id
- provider key
- message id
- chat id
- contact id / lid / endpoint identity
- task name
- operation name
- payload type

Do not log vague messages such as:

- “Something failed”
- “Unexpected error”
- “Could not process”

without identifiers.

## 5.2 Log the actual exception

Use proper exception logging so the traceback/stack is preserved.

Examples:

```python
logger.exception("internal_message_ingest failed | account=%s msg_id=%s", account_id, msg_id)
```

```js
this.logger.error({ sessionId, msgId, err: err.message, stack: err.stack }, "Failed to forward message")
```

If the logging system does not automatically preserve stack traces, include them explicitly.

## 5.3 Distinguish severity properly

- `debug`: low-impact diagnostic detail
- `info`: expected operational events
- `warning`: recoverable but important abnormal condition
- `error`: a real failure affecting the expected operation
- `critical` / highest severity equivalent: severe system integrity or availability issue

Do not log real failures as `debug` just because the process survives.

## 5.4 One failure, one truthful message

Logging should describe what actually happened, not the optimistic end state.

Bad:

- “message preserved successfully” when primary persistence failed but a hidden fallback file write occurred

Good:

- “primary unresolved-message persistence failed; fallback record written; operator action required”

If a fallback path exists, the log must say so explicitly.

---

## 6. Reporting Standard

## 6.1 Log vs structured report

Not every failure needs an operator-facing record, but every important failure needs at least a clear log.

Use structured reporting such as `WorkerAlert`, `DroppedMessage`, `SyncLog`, or future equivalents when:

- the failure affects correctness,
- the failure can cause message/data loss,
- human follow-up may be needed,
- the failure indicates degraded system health,
- the failure recurs in a way that should be queryable in the UI.

## 6.2 Never convert failure into silent success

If an operator-facing record is supposed to exist and that record itself fails to persist:

- log the failure explicitly,
- preserve whatever context can still be captured,
- do not pretend the reporting succeeded.

## 6.3 Reporting channels must not become ambiguous shadow truth

The system may use structured failure-reporting channels, but should avoid inventing secondary hidden truth paths that make operators unsure which source is authoritative.

If a secondary record exists at all, it must be clearly documented as:

- a last-resort audit trace,
- not a success path,
- not equivalent to the primary persistence path.

---

## 7. Fallback Principle

## 7.1 Default stance

Fallbacks are **disallowed by default** in correctness-critical flows unless they improve resilience **without obscuring the failure**.

## 7.2 Allowed fallback characteristics

A fallback is only acceptable if all of the following are true:

1. the primary failure is still explicit,
2. the fallback path is logged clearly,
3. the fallback does not masquerade as normal success,
4. the fallback does not create a confusing second source of truth,
5. the fallback makes later investigation easier, not harder.

## 7.3 Disallowed fallback patterns

The following are explicitly discouraged or banned:

- silent alternate persistence path
- silent alternate provider path
- silent retry loop with no visibility
- silent defaulting to empty state when state is expected
- silent downgrade from strict validation to permissive behavior
- silent data-loss prevention path that does not report the original failure

## 7.4 Preferred alternative to hidden fallback

Prefer:

- explicit failure record,
- durable structured alert,
- explicit retry mechanism,
- explicit replay queue,
- explicit admin action,

instead of:

- hidden alternate behavior.

---

## 8. Practical Rules for `try/except` and `try/catch`

## 8.1 When to re-raise

Re-raise when:

- the caller must know the operation failed,
- continuing would corrupt state,
- the failure invalidates the current operation contract,
- there is no safe local recovery,
- suppressing the exception would create misleading behavior.

## 8.2 When local handling is acceptable

Local handling is acceptable when:

- the failed work is truly non-critical to the primary contract,
- the failure is still logged clearly,
- continuation does not falsify success,
- comments/documentation explain why failure is acceptable there.

Example:

- a best-effort UI-only enrichment field failing after the primary record is already safely saved

Non-example:

- message persistence failing while the API still returns success

## 8.3 Required comment for intentionally non-fatal handling

When handling a failure locally and continuing intentionally, add a short code comment explaining:

- why the failure is non-fatal,
- what remains true,
- why continuation is safer than hard failure.

This is especially important in ingestion and background-processing code.

---

## 9. Application to ChatLens

## 9.1 Message ingestion

If message ingest, identity resolution, or content preservation fails:

- log with message/account/company context,
- report through the appropriate structured mechanism,
- never silently drop the message,
- never hide a failed primary save behind a quiet alternate path.

## 9.2 Provider and connector logic

If a communication provider fails:

- the provider failure must be explicit,
- the chosen provider must remain visible in logs,
- the system must not silently swap to another provider or route unless that behavior is deliberately designed and reported.

## 9.3 Tenant/account setup

If company/account/provider binding fails:

- do not create partial “success” states silently,
- log the incomplete state explicitly,
- prefer transaction boundaries where appropriate.

## 9.4 AI and background tasks

If embedding/classification/automation fails:

- the task failure must be visible,
- logs must include identifiers,
- async execution must not swallow exceptions into process silence,
- any retry behavior must be explicit and observable.

---

## 10. Code Review Rule

From this point onward, code review in ChatLens should reject:

- empty `except` / empty `catch` blocks,
- exception suppression without structured reasoning,
- fallback code that makes real failures harder to trace,
- logs without enough identifiers,
- success responses after failed primary operations,
- alternate hidden persistence routes that obscure root cause.

Review should ask:

- Does this code make failure easier or harder to debug?
- If this fails in production, will we know exactly what happened?
- Is there any hidden path here that makes operators think success occurred when it did not?

If the answer is unsatisfactory, the implementation should not be accepted.

---

## 11. Summary Principle

The strict development principle for ChatLens is:

**Catch exceptions deliberately. Log them with full context. Report important failures through visible system channels. Never hide a failure behind a silent fallback, alternate route, or disguised success path.**

The system must be easier to debug after a failure, not harder.

---

*Prepared for ChatLens on 2026-07-22 as a standing engineering rule for exception handling and failure visibility.*
