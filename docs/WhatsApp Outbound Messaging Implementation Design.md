# WhatsApp Outbound Messaging Implementation Design

> **Status:** Phases 1-3 implemented; later phases remain proposed.
> **Updated:** 2026-09-15
> **Purpose:** Define safe, account-configured WhatsApp message sending with durable execution, destination permission checks, throttling, and new-chat limit visibility.

Implemented so far:

- Phase 1 persists safe account settings and exposes their UI/API controls.
- Phase 2 persists group permission metadata, classifies destination types in
  Django and Node, and provides an authenticated dry-run preflight endpoint.
- Phase 3 pins Baileys `7.0.0-rc14`, persists new-chat cap and reach-out lock
  telemetry, consumes live updates, and exposes current/stale/unavailable state
  plus an authenticated manual refresh in the account UI.
- No outbound message record, send task, or Baileys `sendMessage` transport is
  implemented yet.

## 1. Objective

Add outbound WhatsApp messaging without allowing a new or existing account to
send unexpectedly. Sending is controlled per WhatsApp account, executed through
the durable task queue, and audited from request through delivery feedback.

The implementation must:

- keep all outbound sending disabled by default,
- control direct-contact and group sending independently,
- identify groups, communities, community announcement groups, channels, and
  unsupported destinations before attempting delivery,
- enforce both account-wide and same-recipient intervals,
- disable concurrent sends for an account by default,
- expose the account's available new-chat limit when WhatsApp provides it,
- estimate whether a direct message is likely to count as a new chat,
- avoid blind retries after an ambiguous provider response, and
- retain an operator-visible audit trail for every attempt.

## 2. Non-Goals for the First Release

- Sending to channels/newsletters, community umbrella records, broadcasts, or
  status destinations.
- Bulk campaign management.
- Circumventing WhatsApp account restrictions or rate limits.
- Claiming that a recipient is certainly a new or existing chat when WhatsApp
  does not provide an authoritative recipient-level answer.
- Enabling message sending automatically for any existing account.

## 3. Safety Principles

1. **Default deny.** Missing settings, stale metadata, unknown destination
   types, or uncertain permissions block dispatch.
2. **Validate twice.** Validate when the request is created and immediately
   before the worker sends it.
3. **Do not sleep in a task worker.** A throttled task is deferred by updating
   `available_at`; it does not occupy an execution slot while waiting.
4. **Do not confuse submission with delivery.** Sent, server-acknowledged,
   delivered, and read are separate states.
5. **Do not blindly retry ambiguous sends.** If WhatsApp may have accepted the
   message, retain an `unknown` outcome until it can be reconciled.
6. **Account isolation.** Limits and locks for one WhatsApp account must not
   block another account.

## 4. Account Settings

The Phase 1 implementation stores these database-backed settings on
`WhatsAppAccount`.

| Setting | Type | Default | Meaning |
|---|---|---:|---|
| `outbound_sending_enabled` | boolean | `false` | Master kill switch for all outbound messages. |
| `direct_sending_enabled` | boolean | `false` | Permit sends to direct contacts. |
| `group_sending_enabled` | boolean | `false` | Permit sends to eligible groups. |
| `recipient_interval_ms` | positive integer | `5000` | Minimum dispatch-start interval between messages from this account to the same recipient. |
| `account_interval_ms` | positive integer | `5000` | Minimum dispatch-start interval between any two messages from this account. |
| `allow_concurrent_sends` | boolean | `false` | Permit more than one in-flight send for this account. |
| `max_concurrent_sends` | positive integer | `1` | Concurrency ceiling when concurrent sending is enabled. |
| `unknown_new_chat_policy` | choice | `block` | Behavior when a likely-new direct chat has unavailable or stale cap data. |

Suggested validation limits:

```text
recipient_interval_ms: 1000..300000
account_interval_ms:   1000..300000
max_concurrent_sends:  1..20
```

`max_concurrent_sends` remains stored while concurrency is disabled, but the
effective value is always one. The initial UI may hide or disable this field
until `allow_concurrent_sends` is selected.

Existing-account migrations must explicitly populate the safe defaults. There
must be no environment-variable fallback for these business settings.

## 5. Throttling and Concurrency Contract

### 5.1 Definitions

- **Account interval:** delay between dispatch starts for any two messages sent
  by the same WhatsApp account.
- **Recipient interval:** delay between dispatch starts for messages sent by the
  same account to the same canonical recipient JID.
- **In-flight send:** a send that has entered provider dispatch but has not yet
  reached a terminal submission outcome.
- **Dispatch start:** the instant immediately before calling Baileys
  `sendMessage`; queue waiting and preflight time do not count.

### 5.2 Earliest Dispatch Time

For message `M`, calculate:

```text
account_eligible_at = account.last_dispatch_started_at + account_interval_ms
recipient_eligible_at = recipient.last_dispatch_started_at + recipient_interval_ms
eligible_at = max(now, account_eligible_at, recipient_eligible_at)
```

If `eligible_at` is in the future, release the lease and defer the durable task
to that time. The calculation must run inside the same database transaction
that reserves the account and recipient slots.

Example with defaults:

```text
12:00:00  send to Contact A
12:00:05  earliest send to Contact A or Contact B (account interval)
12:00:10  earliest next send to Contact A if Contact B sent at 12:00:05
```

If the operator later sets `account_interval_ms=1000` while leaving
`recipient_interval_ms=5000`, messages to different contacts may start one
second apart, but repeated messages to one contact remain five seconds apart.

### 5.3 Concurrent Sending Disabled

When `allow_concurrent_sends=false`:

- only one message may be in flight for the account,
- other tasks for that account are deferred without sleeping,
- completion or a lease timeout releases the in-flight slot, and
- different WhatsApp accounts may still dispatch concurrently.

This is the default and safest operating mode.

### 5.4 Concurrent Sending Enabled

When enabled:

- no more than `max_concurrent_sends` may be in flight,
- account and recipient intervals still apply,
- two messages to the same recipient cannot reserve the same recipient slot,
- the reservation transaction must use row locking or an equivalent atomic
  compare-and-update, and
- decreasing the limit does not terminate current sends, but prevents new
  reservations until the in-flight count falls below the new limit.

Concurrency does not mean simultaneous dispatch without spacing. The account
interval remains authoritative unless the operator explicitly lowers it.

## 6. Destination Classification

Create one shared classifier used by the API, task handler, and Node worker.
It must distinguish:

```text
direct_contact
standard_group
community
community_announcement
community_subgroup
channel
broadcast
status
unknown
```

JID suffixes provide an initial classification, but live group metadata is the
authority for group/community distinctions. The persisted result is a cache for
display and preliminary validation, not permission to send.

### 6.1 Persisted Group Metadata

Extend group metadata with:

```text
is_community
is_community_announcement
linked_parent_jid
announce
restrict
account_participant_role
account_is_participant
can_send
send_block_reason
metadata_refreshed_at
```

`restrict` concerns who may change group settings; it must not be interpreted
as a direct send prohibition. `announce` means only administrators may send,
so the connected account's current participant role must also be checked.

### 6.2 Initial Permission Policy

| Destination | Initial behavior |
|---|---|
| Direct contact | Requires master and direct toggles, registration check, and new-chat preflight. |
| Standard group | Requires master and group toggles, current membership, and send permission. |
| Community subgroup | Treat as a group after live permission checks. |
| Community announcement | Allow only when the connected account is admin/superadmin. |
| Community umbrella | Always block. |
| Channel/newsletter | Always block in the first release. |
| Broadcast/status | Always block. |
| Unknown/stale metadata | Block and record the reason. |

Immediately before a group send, request fresh `groupMetadata`. If it cannot be
retrieved, do not attempt delivery.

## 7. Outbound Data Model

### 7.1 OutboundMessage

```text
id
company_id
whatsapp_account_id
destination_jid
canonical_recipient_key
destination_type
content_type
content_payload
status
status_reason
idempotency_key
provider_message_id
correlation_id
new_chat_state
new_chat_confidence
new_chat_reason
permission_snapshot
settings_snapshot
attempt_count
requested_by_id
requested_at
eligible_at
dispatch_started_at
provider_accepted_at
delivered_at
read_at
finished_at
last_error_code
last_error
created_at
updated_at
```

Initial statuses:

```text
queued
deferred
preflight_blocked
sending
sent
delivered
read
failed
cancelled
unknown
```

### 7.2 OutboundMessageEvent

Append-only events must record every significant transition:

```text
requested
preflight_passed
preflight_blocked
queued
rate_limited
concurrency_deferred
dispatch_started
provider_accepted
delivered
read
failed
outcome_unknown
cancelled
```

Each event stores its timestamp, actor/worker, attempt, message, and structured
metadata. Payloads shown in the UI must redact credentials and sensitive worker
headers.

### 7.3 Throttle State

Use dedicated state rather than scanning the full message ledger:

```text
OutboundAccountState
  whatsapp_account_id unique
  last_dispatch_started_at
  in_flight_count
  lease_version
  updated_at

OutboundRecipientState
  whatsapp_account_id
  canonical_recipient_key
  last_dispatch_started_at
  in_flight_count
  updated_at
  unique (whatsapp_account_id, canonical_recipient_key)
```

Reservations must lock the account state and recipient state in a consistent
order to avoid deadlocks.

## 8. Durable Task Execution

Add an `outbound` queue and task key:

```text
queue: outbound
task:  whatsapp.send_message
```

The request API creates `OutboundMessage` first and then enqueues a task whose
payload contains only stable identifiers:

```json
{
  "version": 1,
  "outbound_message_id": 12345
}
```

Use the outbound message UUID/ID as the task idempotency and correlation base.
The API must never call the Node worker directly.

The task handler performs:

1. Load and lock the outbound record.
2. Reject terminal or cancelled records.
3. Re-read current account settings.
4. Run destination and new-chat preflight.
5. Atomically reserve account, recipient, and concurrency capacity.
6. Defer using `available_at` when capacity is not yet available.
7. Mark `sending` and call the authenticated Node endpoint.
8. Persist the normalized response and release in-flight capacity in `finally`.
9. Reconcile later delivery/read events without reopening a terminal failure.

Turning off the master, direct, or group toggle must stop applicable queued
messages at step 3. It does not recall a message already accepted by WhatsApp.

## 9. Retry and Idempotency Rules

Use a deterministic provider message ID and worker-side duplicate suppression.
The same outbound message must reuse that ID on every safe retry.

Retry only when the system knows dispatch did not reach WhatsApp, for example:

- session unavailable before dispatch,
- permission metadata temporarily unavailable before dispatch,
- connection failure before the send call starts, or
- explicit provider rejection marked retryable.

Do not automatically retry when:

- the HTTP connection is lost after dispatch starts,
- the worker times out without proving rejection, or
- WhatsApp may already have accepted the message.

These cases become `unknown` and require receipt reconciliation or an operator
decision. The system provides duplicate suppression, not an unsupported claim
of exactly-once external delivery.

## 10. Node Worker API and Responsibilities

Add an authenticated internal endpoint such as:

```text
POST /sessions/{sessionId}/messages
```

The request includes the outbound ID, deterministic provider message ID,
destination JID, and validated content. The Node worker must still independently:

1. Confirm the session is connected and healthy.
2. Classify the JID using Baileys helpers.
3. Resolve/canonicalize direct JIDs and verify registration with `onWhatsApp`.
4. Fetch fresh group metadata for group destinations.
5. Reject communities, channels, broadcasts, unknown destinations, and groups
   where the account lacks permission.
6. Apply a per-session mutex and interval guard as defence in depth.
7. Call `sock.sendMessage`.
8. Return a normalized submission result.
9. Forward message acknowledgement, delivery, read, and failure updates to
   Django through authenticated internal callbacks.

The Django database remains the scheduling authority. Node guards prevent an
accidental bypass; they do not replace durable reservations.

## 11. New-Chat Capacity and State

Phase 3 replaces the legacy Baileys 6.x dependency with the pinned ESM release
`baileys@7.0.0-rc14`. The CommonJS worker loads it through an asynchronous
compatibility module. Production must still use a canary account after deployment
before relying on provider telemetry because the upstream cap query can be
unavailable for individual WhatsApp accounts.

Store the latest server-provided account state:

```text
total_quota
used_quota
remaining_quota (derived)
cycle_started_at
cycle_ends_at
capping_status
reachout_lock_status
reachout_lock_ends_at
source
fetched_at
fetch_status
fetch_error
```

Fetch it on connection and consume subsequent cap/reach-out updates. If the
provider endpoint is unsupported or fails, preserve the last valid sample and
mark it stale or unavailable. Never interpret missing data as unlimited.

## 12. Direct-Recipient New-Chat Preflight

WhatsApp does not provide a dependable per-recipient promise that a message will
or will not consume new-chat quota. `onWhatsApp` verifies registration only.

The local classifier returns:

| State | Evidence |
|---|---|
| `existing_warm` | At least one direct inbound message from this identity exists for this account. |
| `likely_new` | Recipient is registered, but no local conversation history exists. |
| `unknown` | Outbound-only history, incomplete sync, unresolved LID, or stale identity data. |

The result includes confidence, reasons, and the history/cap timestamps used.
It is recalculated immediately before dispatch.

Initial policy:

- likely new plus capped/reach-out locked: block,
- likely new plus unknown/stale cap state: block,
- existing warm: permit when other settings allow it,
- unknown recipient state: block by default, and
- any actual WhatsApp restriction response overrides the prediction and updates
  account state.

## 13. API Surface

Suggested endpoints:

```text
PATCH /api/whatsapp/accounts/{id}/message-settings/
GET   /api/whatsapp/accounts/{id}/message-capacity/
POST  /api/whatsapp/accounts/{id}/message-preflight/
POST  /api/whatsapp/accounts/{id}/messages/
GET   /api/whatsapp/outbound-messages/
GET   /api/whatsapp/outbound-messages/{id}/
POST  /api/whatsapp/outbound-messages/{id}/cancel/
POST  /api/whatsapp/outbound-messages/{id}/retry/
```

Authorization must require company/account access and a specific outbound-send
permission. The backend must not trust a destination classification submitted
by the browser.

## 14. User Interface

### Account Settings

Add a **Message Sending** section containing:

- master outbound toggle,
- direct-contact toggle,
- group toggle,
- same-recipient interval in milliseconds with a `5000 ms (5 seconds)` hint,
- account-wide interval in milliseconds,
- concurrent sending toggle,
- maximum concurrent sends when enabled,
- new-chat unknown-state policy,
- prominent warning when sending is enabled, and
- current cap/reach-out state with source and freshness.

Changing a child toggle does not bypass the master toggle. The UI must state the
effective state rather than only showing stored values.

### Message Composer

Before enabling Send, show:

- destination type,
- permission result,
- new-chat prediction for direct contacts,
- current/stale/unavailable cap state,
- earliest expected dispatch time, and
- an exact reason when sending is blocked.

Likely-new direct messages require explicit confirmation in the first release.

### Operations Page

Add a paginated outbound-message grid with account, destination, type, status,
queued time, dispatch time, current delay reason, and correlation ID. Expanding
a row shows the settings snapshot, preflight result, attempts, provider response,
and event timeline. Only queued messages can be cancelled. Retry is available
only for outcomes classified as safe to retry.

## 15. Failure Handling

Required explicit failure categories include:

```text
master_sending_disabled
direct_sending_disabled
group_sending_disabled
destination_unsupported
community_send_blocked
channel_send_blocked
not_a_group_participant
group_admin_required
group_metadata_unavailable
live_preflight_unavailable
recipient_not_registered
recipient_identity_unresolved
new_chat_cap_reached
new_chat_cap_unknown
reachout_locked
account_interval_wait
recipient_interval_wait
account_concurrency_wait
session_disconnected
provider_rejected
dispatch_outcome_unknown
```

Operator-visible feedback must use these stable categories rather than requiring
terminal-log inspection.

## 16. Metrics and Monitoring

Capture per account and destination type:

- requested, blocked, deferred, submitted, delivered, read, failed, and unknown
  counts,
- queue wait, throttle wait, provider submission latency, delivery latency, and
  read latency,
- account-interval, recipient-interval, and concurrency deferrals,
- new-chat predictions and actual restriction outcomes,
- duplicate-suppression events,
- stale group metadata and cap-data frequency, and
- current in-flight count and next eligible dispatch time.

The operations monitor should alert when an in-flight lease exceeds its timeout
or cap/group metadata remains stale beyond the configured freshness threshold.

## 17. Implementation Structure

Keep policy and transport concerns separate. Suggested modules:

```text
apps/whatsapp_bridge/outbound/
  models.py
  settings_service.py
  destination_policy.py
  new_chat_policy.py
  throttle_service.py
  message_service.py
  task_handler.py
  receipt_service.py
  api/

whatsapp-worker/src/outbound/
  destination-classifier.js
  permission-checker.js
  session-throttle.js
  message-sender.js
  receipt-forwarder.js
```

Follow the existing separation of concerns: Django owns durable intent, policy,
scheduling, and audit; the Node worker owns live WhatsApp session validation and
Baileys transport.

## 18. Rollout Sequence

### Phase 1: Safe Configuration

- Add models, migrations, serializers, settings API, and UI.
- Populate all accounts with disabled defaults.
- Add permission tests proving no message can leave the system.

### Phase 2: Destination Metadata and Dry Run

- Persist the additional group/community metadata.
- Implement Django and Node destination classifiers.
- Add preflight-only APIs and compare their decisions against live test data.

### Phase 3: Baileys Upgrade and Capacity Telemetry

- Implemented: pinned `baileys@7.0.0-rc14` with CommonJS compatibility loading.
- Implemented: automated session, history, group metadata, ingestion, and telemetry
  regression tests; a live canary remains a deployment requirement.
- Implemented: cap and reach-out collection without enabling sends.

### Phase 4: Durable Outbound Execution

- Add outbound records, event ledger, throttle state, queue, and task handler.
- Add the authenticated Node send endpoint and duplicate suppression.
- Keep the feature disabled except for a dedicated test account.

### Phase 5: Controlled Verification

- Test one existing direct conversation.
- Test account-wide and recipient-specific timing.
- Test concurrency disabled, then enabled with a small limit.
- Test standard, announcement-only, non-member, and community groups.
- Test disconnects, worker restarts, ambiguous timeouts, and receipt updates.
- Enable likely-new-chat sending only after cap telemetry is trustworthy.

## 19. Required Tests

### Django

- All new and migrated accounts default to sending disabled.
- Master and destination-specific switches are independently enforced.
- Account and recipient intervals calculate the correct later eligibility time.
- Concurrent dispatch cannot exceed the effective account limit.
- Reservations remain safe across multiple worker processes.
- Deferred tasks do not occupy worker execution slots.
- Stale metadata and unknown new-chat state block safely.
- Idempotent requests create one outbound intent.
- Ambiguous dispatch is not automatically retried.

### Node Worker

- Every supported JID type is classified correctly.
- Community, newsletter, broadcast, status, and unknown destinations are denied.
- Group membership and announcement-admin rules use fresh metadata.
- Session-level concurrency and interval guards reject bypass attempts.
- Deterministic message IDs suppress duplicate submissions.
- Acknowledgement and receipt events map to normalized states.

### End to End

- Direct warm-chat send and receipt progression.
- Same-recipient five-second minimum.
- Account-global interval across different recipients.
- Independent concurrent operation of two accounts.
- Account concurrency disabled and enabled behavior.
- Settings disabled while messages are queued.
- Worker termination/restart during preflight and during dispatch.
- Unknown-result reconciliation without duplicate delivery.

## 20. Acceptance Criteria

The first release is complete only when:

1. Every account starts with master, direct, and group sending disabled.
2. No message reaches the Node send endpoint when an applicable switch is off.
3. Messages to the same recipient respect at least the configured five-second
   default interval.
4. All messages from one account respect its configured global interval.
5. Concurrent sends are impossible by default and bounded when enabled.
6. One account's throttle does not block another account.
7. Community umbrellas, channels, broadcasts, status targets, unauthorized
   groups, and unknown destinations are never submitted.
8. New-chat capacity is displayed with source and freshness; unavailable data
   is never presented as unlimited.
9. Every requested message has a durable record and append-only event history.
10. Ambiguous sends are not blindly retried.
11. The operations UI explains every block, delay, failure, and unknown outcome.
