# Code Review Remediation Plan

> **Current status:** In progress - Phases 1, 2, 3, and 4 have been implemented.
> **Last updated:** 2026-07-25

> **Prepared:** 2026-07-22
> **Source:** Full-project code review requested on 2026-07-21 and follow-up planning request on 2026-07-22.
> **Scope:** Address the five concrete findings from the review: tenant isolation, worker metadata durability, unbounded background threading, session-start settings drift, and restore-count accuracy.

---

## 0. Current Implementation Status

### Completed

- **Phase 1 - Tenant isolation and access control:** Implemented through company tenancy, company memberships, active company selection, tenant-scoped API helpers, control-company admin endpoints, and tenant-owned products/inquiries/configuration records.
- **Phase 2 - Durable worker metadata fallback and replay:** Implemented for `sendContactsUpdate`, `sendGroupUpdate`, and `sendGroupParticipantsUpdate`. Failed metadata updates are written to `failed-reports.ndjson`, replay-safe metadata records can be replayed, and successful replay removes completed records from the fallback file.
- **Phase 3 - Session-start settings consistency:** Implemented for manual worker session start. Django includes persisted `sync_history`, `history_days`, `idle_disconnect_minutes`, and `auto_download_media` in the worker bootstrap payload, and the worker session route forwards all of those options to `createSession`.
- **Phase 4 - Accurate restore reporting:** Implemented for message restore. The restore endpoint pre-checks existing provider message IDs, inserts only new rows, and reports `restored_messages`, `skipped_existing`, and `invalid_rows`.
- **Contact update rejection visibility:** `internal_contacts_update` now reports `updated`, `skipped`, and `rejected` counts so malformed LID-primary contacts are visible to the worker instead of being hidden behind a generic success response.

### Verified

- `python manage.py check`
- `python manage.py test apps.api`
- `python manage.py test apps.whatsapp_bridge`
- `npm.cmd test` in `whatsapp-worker`
- `npm.cmd run build`

### Remaining

- **Phase 5 - Bounded background execution:** Replace unbounded daemon-thread spawning with a bounded executor or queued task system. This phase should be implemented slowly and carefully, one change at a time, because it changes background execution behavior in the live ingestion path.

---

## 1. Goal

Turn the review findings into a staged implementation plan that:

- closes the only direct data-exposure issue first,
- hardens the WhatsApp worker's metadata/reporting reliability,
- removes the highest operational scaling risk in the ingestion pipeline,
- fixes configuration drift between Django and the worker, and
- corrects inaccurate operator-visible restore reporting.

This document is intentionally implementation-oriented: what to change, in what order, what tradeoffs are being chosen, and what tests must exist before the work is considered complete.

---

## 2. Findings Being Addressed

### 2.1 Cross-user data exposure

`WhatsAppAccount` has an `owner` field, but user-facing API viewsets and custom actions are only gated by `IsAuthenticated`. Querysets are global, so any authenticated user can access any other user's accounts and derived data unless the deployment only ever has one user.

**Impact:** highest severity — confidentiality/integrity issue.

### 2.2 Non-durable worker metadata updates

The worker persists dropped messages, worker alerts, and stuck receipts to `failed-reports.ndjson` when Django is unavailable, but `sendContactsUpdate`, `sendGroupUpdate`, and `sendGroupParticipantsUpdate` do not. A transient Django outage can permanently lose contact alias/group metadata with only a warning log line.

**Impact:** high reliability risk — especially load-bearing for LID/username resolution.

### 2.3 Unbounded background thread creation

Django still uses daemon threads for live embed/classify work, but unresolved-message recovery from `contacts_update` no longer spawns one thread per LID contact. As of 2026-08-17, `internal_contacts_update` batches all LID mappings from one worker contact update into a single recovery thread with explicit DB connection cleanup (`close_old_connections()` at start, `connection.close()` in `finally`). Remaining risk: live embed/classify threads are still unbounded until the planned queue/task module is implemented.

**Impact:** medium/high operational risk under sustained traffic.

### 2.4 Session-start configuration drift

The account setting `auto_download_media` is persisted in Django and used on reconnect/restore paths, but `POST /api/accounts/{id}/start-session/` does not include it in the worker bootstrap payload. A fresh session can therefore start with media download enabled even when the account setting is disabled.

**Impact:** medium correctness/configuration bug.

### 2.5 Restore reporting overcounts inserted messages

`restore_messages` uses `bulk_create(..., ignore_conflicts=True)` and then reports `len(created_objs)` as restored count. That does not reliably mean "newly inserted rows", so repeat or overlapping restores can over-report success.

**Impact:** low severity, but operator-visible correctness bug.

---

## 3. Delivery Order

Implementation should follow this order:

1. **Access control**
2. **Worker metadata durability**
3. **Session-start config fix**
4. **Restore-count accuracy**
5. **Background execution redesign**

Why this order:

- Access control is the only issue with direct security exposure.
- Metadata durability is the next most important because it affects message identity correctness and observability.
- The session-start and restore-count fixes are narrow, low-risk correctness patches that can land quickly.
- Background execution redesign is the broadest change and should happen after the smaller reliability/security fixes are safely in place.

---

## 4. Proposed Solution

## 4.1 Phase 1 — Tenant Isolation and Access Control

### Objective

Restrict every user-facing API to objects owned by the authenticated user, unless the caller is explicitly allowed broader visibility by policy.

### Policy decision required

Before implementation, choose one of these models:

**Option A — strict ownership by default**
- Ordinary users only see their own data.
- Superusers also only see their own data in normal endpoints.
- Cross-tenant visibility exists only in dedicated admin endpoints.

**Option B — superuser global access**
- Ordinary users only see their own data.
- Superusers can see everything through the same endpoints.

**Recommended:** Option A. It keeps the default behavior safer and makes cross-tenant access an explicit administrative operation rather than a silent property of every endpoint.

### Backend changes

Apply owner scoping to:

- `WhatsAppAccountViewSet`
- `ChatViewSet`
- `ContactViewSet`
- `GroupViewSet`
- `SyncLogViewSet`
- `DroppedMessageViewSet`
- `WorkerAlertViewSet`
- `StuckReceiptViewSet`
- `UnresolvedMessageViewSet`
- any trading viewsets already keyed off account/contact/chat relationships
- every custom action that currently starts from `self.get_object()` or a global queryset

### Implementation approach

Use a shared helper/mixin instead of duplicating owner filters in every viewset:

```python
class OwnerScopedQuerysetMixin:
    owner_field = 'owner'

    def scope_queryset_to_user(self, qs):
        user = self.request.user
        if user.is_superuser and settings.API_SUPERUSER_SEES_ALL:
            return qs
        return qs.filter(**{self.owner_field: user})
```

For related models whose ownership is indirect:

- chats/logs/dropped messages/alerts: filter via `account__owner`
- messages: filter via `account__owner` or `chat__account__owner`
- contacts/groups: filter via `account__owner`
- trading models: filter via `account__owner` and any linked relations as needed

### Additional safeguards

- Reject `account=<foreign id>` query params if that account is not visible to the requester.
- Ensure destructive endpoints (`delete-all-*`, restore endpoints, acknowledge-all, clear-all, etc.) only affect rows visible to the requester.
- Verify `perform_create()` never lets a caller set someone else's owner.

### Tests required

Add API tests proving:

- user A cannot list user B's accounts
- user A gets 404/403 on user B's detail endpoints
- user A cannot mutate user B's contacts/groups/logs
- bulk actions only affect the caller's own rows
- superuser behavior matches the chosen policy exactly

### Rollout risk

Low-to-medium. The risk is mostly missed endpoints, not behavioral complexity. The mitigation is broad API coverage tests.

---

## 4.2 Phase 2 — Durable Worker Metadata Fallback and Replay

### Objective

Make contact/group metadata updates survive transient Django failures the same way dropped messages and worker alerts already do.

### Backend/worker problem statement

Today these methods lose data on failure:

- `sendContactsUpdate`
- `sendGroupUpdate`
- `sendGroupParticipantsUpdate`

Those failures are especially significant because:

- contact alias persistence seeds LID/username caches on reconnect,
- missed group metadata weakens group/member observability,
- warning-only logging is not durable enough for later diagnosis.

### Worker changes

Extend each method to write a durable fallback record to `failed-reports.ndjson`:

```js
this._writeFallback('contacts_update', payload)
this._writeFallback('group_update', payload)
this._writeFallback('group_participants_update', payload)
```

Keep the payloads replayable as-is:

- `worker_session_id`
- endpoint-specific body
- timestamp
- kind

### Replay design

Recording the failure is not enough; the worker needs a way to replay it.

**Recommended implementation:**

- add a worker-side replay function that reads `failed-reports.ndjson`,
- retries only replay-safe kinds:
  - `contacts_update`
  - `group_update`
  - `group_participants_update`
  - existing safe kinds may also be replayed later if desired
- mark successful replays in-memory during the run and rewrite the file without completed entries, or move completed entries to a companion archive file.

### Replay trigger

Initial version:

- trigger replay after the worker confirms Django connectivity is healthy,
- also allow a manual/admin-triggered replay endpoint if needed later.

### Idempotency assumptions to verify

- `internal_contacts_update` is already an upsert: safe to replay.
- `internal_group_update` is already an upsert: safe to replay.
- `internal_group_participants_update` must be treated carefully but is also replay-safe because the current actions are state-setting updates, not append-only audit writes.

### Django-side visibility improvement

The earlier LID investigation already identified one related gap: `internal_contacts_update` currently rejects invalid LID-primary contacts silently from the worker's perspective and still returns a generic success body.

That should be folded into this phase:

- return a differentiated response with `updated`, `skipped`, and `rejected`
- log warnings on the worker when `rejected > 0`
- optionally emit a `WorkerAlert` for malformed contact batches if rejection is unexpected

### Tests required

Worker tests:

- contacts/group updates write fallback entries on HTTP failure
- replay resubmits saved entries
- replay removes or archives successfully replayed items

Django tests:

- replayed contacts/group updates remain idempotent
- malformed contacts are reported explicitly, not silently hidden

### Rollout risk

Low. This is additive reliability work with existing patterns already in the codebase.

---

## 4.3 Phase 3 — Session-Start Settings Consistency

### Objective

Ensure a fresh worker session starts with the exact account settings already stored in Django.

### Required change

`start_session` must include:

- `auto_download_media`

in addition to the existing:

- `sync_history`
- `history_days`
- `idle_disconnect_minutes`

### Files affected

- `apps/api/views.py`
- worker session bootstrap handling in `whatsapp-worker/src/session-manager.js` (already supports the setting; this phase verifies the bootstrap path only)

### Tests required

- API test asserting the worker start payload includes `auto_download_media`
- worker/session test confirming a new session created with `auto_download_media: false` does not default back to `true`

### Rollout risk

Very low.

---

## 4.4 Phase 4 — Accurate Restore Reporting

### Objective

Make the restore endpoint report what actually happened, not just how many rows were attempted.

### Current issue

`bulk_create(ignore_conflicts=True)` is useful for idempotent restore behavior, but not for precise inserted-row counts.

### Proposed implementation

Per chat restore batch:

1. collect candidate `provider_message_id`s from the uploaded payload
2. query existing IDs for `(account, provider_message_id)` before insert
3. insert only rows whose IDs are not already present
4. report:
   - `restored_messages`
   - `skipped_existing`
   - optionally `invalid_rows`

This is clearer than trying to infer inserts from `bulk_create` return semantics.

### Preferred response shape

```json
{
  "restored_chats": 3,
  "restored_messages": 412,
  "skipped_existing": 87
}
```

### Tests required

- first import of a clean backup inserts all rows
- second import of the same backup inserts zero and reports all as skipped
- partial-overlap import reports a split between inserted and skipped

### Rollout risk

Low.

---

## 4.5 Phase 5 — Replace Unbounded Per-Event Threads

### Objective

Remove unbounded daemon-thread spawning from the ingestion path and replace it with bounded execution with observable capacity limits.

### Current behavior

Threads are spawned here:

- `_embed_in_background(...)`
- `_process_message_in_background(...)`
- `internal_contacts_update` unresolved-message recovery trigger

This is acceptable for a low-volume prototype, but not for a production message-ingestion pipeline that can spike.

### Target design

Move background work into a bounded execution model.

Two viable implementations:

**Option A — bounded in-process executor**
- use `ThreadPoolExecutor`
- define a max worker count
- submit embed/classify/recovery tasks into the pool
- reject or log when queue depth becomes unhealthy

**Option B — Celery-backed async tasks**
- move embedding, classification, and unresolved recovery into Celery tasks
- use Redis broker already referenced in settings
- gain retries, concurrency control, queue visibility, and process separation

**Recommended path:** staged.

#### Stage 1

Replace raw `threading.Thread(...).start()` with a shared bounded executor to stop the immediate "thread explosion" risk with minimal code churn.

#### Stage 2

Promote that work to Celery once the task boundaries are stable.

This avoids bundling a larger deployment/infrastructure shift into the same patch as the immediate operational fix.

### Task boundaries

Split work into explicit units:

- embed a message
- classify a message
- process automation rules for a message
- recover unresolved messages for a LID
- update sync-log post-processing metadata

### Behavioral requirements

- never block the ingest HTTP response on AI/embedding work
- preserve current "ingest first, classify later" contract
- keep failures visible in logs and, where appropriate, `WorkerAlert`
- avoid duplicate classification on retries

### Observability to add

- queue depth / pending task count
- task execution duration
- task failure count
- recovery batch size
- executor saturation warnings

### Tests required

At minimum:

- unit tests for task submission and idempotent execution
- regression tests proving ingestion still returns success even when async work fails
- tests for duplicate-safe recovery/classification behavior

Load/perf validation:

- a local script or test harness that simulates burst traffic and confirms bounded concurrency

### Rollout risk

Medium. This changes execution behavior, so it should land after the narrower fixes above.

---

## 5. Recommended Implementation Batches

### Batch A — Security patch

Includes:

- Phase 1 owner scoping
- tests for tenant isolation

This should be a self-contained patch and reviewed as such.

### Batch B — Reliability patch

Includes:

- Phase 2 metadata fallback + replay
- explicit contacts-update rejection reporting
- Phase 3 session-start `auto_download_media` fix

These changes are closely related to worker/Django operational correctness.

### Batch C — Correctness patch

Includes:

- Phase 4 restore-count fix

Small and low-risk; can land independently.

### Batch D — Scalability patch

Includes:

- Phase 5 bounded async execution

Should land only after the earlier patches are stable.

---

## 6. Acceptance Criteria

The remediation effort is complete when all of the following are true:

- a non-owner authenticated user cannot read or mutate another user's data through any normal API endpoint,
- worker contact/group metadata updates survive transient Django outages and can be replayed safely,
- fresh worker sessions honor `auto_download_media` immediately,
- restore reporting distinguishes inserted rows from already-existing rows,
- ingestion no longer creates an unbounded number of background threads,
- automated tests cover the new security and reliability guarantees.

---

## 7. Explicit Non-Goals

This document does **not** propose:

- changing the WhatsApp-side linked-device limitation documented in `Silent Message Drop Investigation.md`,
- redesigning the whole authentication system,
- merging tenant isolation with role-based fine-grained permissions in one pass,
- moving all worker-side persistence to a different transport,
- enabling message sending.

Those are separate decisions.

---

## 8. Recommended Next Step

Start with **Phase 1 (tenant isolation)** and make the superuser-policy decision first. That decision affects queryset design, test expectations, and whether any current UI workflows implicitly depend on global visibility.

Once that is fixed, proceed to **Phase 2 (durable worker metadata fallback)**, because it closes the most important reliability hole still left open by the 2026-07-21 LID-preservation work.

---

*Prepared for ChatLens as the implementation plan for the 2026-07-21/2026-07-22 code review findings.*
