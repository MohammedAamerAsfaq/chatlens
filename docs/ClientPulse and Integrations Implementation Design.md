# ClientPulse and Integrations Implementation Design

> **Status:** Approved design; Phases 0-4 implemented through manual WhatsApp follow-up. ClientPulse directory, reminder, and profile screens use the shared Inspinia component system.
> **Prepared:** 2026-10-01
> **Purpose:** Define the concrete implementation of the ClientPulse CRM module and the Integrations module used to connect external contact providers such as Google Contacts.

---

## 1. Objective

ClientPulse is the company-owned CRM area of ChatLens. Its primary responsibilities are:

- maintain a reliable customer contact database,
- give users a complete history of customer interactions,
- support manual follow-up and customer-contact workflows,
- provide reminders and recurring follow-up processes,
- support carefully controlled automated follow-up,
- connect customer identities to WhatsApp and future channels,
- consume contacts synchronized by external providers,
- report which customers require attention and whether follow-up is effective.

External-provider connectivity is owned by a separate module named **Integrations**.

Integrations is responsible for:

- OAuth and provider authorization,
- encrypted provider credentials,
- provider-specific API clients,
- full and incremental synchronization,
- external identifiers and cursors,
- synchronization logs and conflicts,
- converting provider records into a provider-neutral contact import contract.

ClientPulse must not contain Google API logic. Integrations must not contain CRM lifecycle, reminder, or follow-up policy.

### 1.1 Implementation checkpoint

Phase 0 currently includes the additive RBAC schema, permission catalog, seven default company roles, legacy membership mapping, effective permission output in the auth context, company Users and Roles & Permissions APIs/UI, last-Owner protection, and authorization audit records. Existing business-area routes remain on legacy enforcement until each route declares and tests its replacement permission code.

Phase 1 adds the `clientpulse` and `integrations` module boundaries, enriches canonical contacts and identities, normalizes exact identity keys, supports tenant-checked WhatsApp linking/unlinking, and records ambiguous exact matches for review. Linking and duplicate generation are explicit dry-run-first management operations; deployment does not rewrite WhatsApp contact records automatically.

Phase 2 adds company-scoped ClientPulse profiles, ownership, lifecycle and priority, reusable tags, editable notes with append-only audit activities, contact consent, do-not-contact controls, linked identity visibility, server-paginated directory/profile APIs and UI, and safe company defaults.

Phase 3 adds company-scoped durable reminders, recurrence, snoozing, in-app notifications, dashboard metrics, the `clientpulse` queue and per-company scheduler, and idempotent WhatsApp activity projection. Reminder delivery never creates an outbound customer message. Automated follow-up remains disabled.

Phase 4 adds permission-scoped manual WhatsApp follow-up from a ClientPulse profile. It resolves only company-owned linked WhatsApp contacts, enforces CRM suppression and configured consent policy, performs live destination preflight, and delegates text or image messages to the existing outbound queue. Timeline entries reference the outbound ledger and expose its live queued, sent, delivered, read, blocked, or failed state. Baileys receipt callbacks advance delivery state monotonically and use the worker fallback journal when Django is unavailable.

The 2026-10-06 UI and conversion checkpoint adds creation of a ClientPulse profile from an existing WhatsApp contact. The candidate endpoint is company-scoped and permission-protected. Owners, admins, and superusers may search all communication accounts owned by the active company; other users may search only WhatsApp accounts assigned to them. Group, newsletter, and broadcast identities are excluded. The directory uses one remotely searchable contact selector rather than separate account/contact selectors.

---

## 2. Mandatory Architectural Decisions

### 2.1 Canonical contact

`tenancy.CompanyContact` remains the canonical company-owned person or organization.

Do not introduce a second independent customer table. A second contact database would create conflicting names, phone numbers, tags, and channel histories.

### 2.2 Channel-local contacts

`WhatsAppContact` remains the WhatsApp account-local operational contact. Its existing optional `company_contact` relationship links it to the canonical contact.

One `CompanyContact` may be linked to:

- multiple WhatsApp contacts from different company accounts,
- multiple phone numbers,
- multiple email addresses,
- one or more external Google contact resources,
- future Telegram, email, or other channel identities.

### 2.3 Module ownership

```text
tenancy
  Owns Company and canonical CompanyContact identity

clientpulse
  Owns CRM profile, lifecycle, activity, reminders, sequences,
  consent, ownership, tags, merge review, and CRM reporting

integrations
  Owns external connections, credentials, provider adapters,
  synchronization state, external links, conflicts, and sync history

whatsapp_bridge
  Owns WhatsApp-local contacts, chats, messages, preflight,
  outbound messages, delivery state, and account limits

task_management / queue_management
  Own durable execution, scheduling, retry, timeout, and observability
```

### 2.4 Outbound safety

ClientPulse must never send directly through Baileys or from an IIS request.

All customer messages must use the existing outbound-message service and `outbound` queue. Existing controls remain authoritative:

- account master sending toggle,
- direct-message sending toggle,
- image sending toggle,
- per-contact and global intervals,
- concurrency policy,
- new-chat confirmation and capacity,
- WhatsApp registration checks,
- session availability,
- consent and CRM suppression rules.

### 2.5 Safe defaults

- ClientPulse automated sending: OFF.
- Follow-up sequences: manual enrollment only.
- Google Contacts synchronization: OFF until connected.
- Initial Google mode: read-only import.
- Automatic duplicate merge: OFF.
- External deletion must not delete a ClientPulse contact.
- Reminder notifications: ON inside ChatLens.

---

## 3. Scope

### 3.1 Initial production scope

- company-scoped customer directory,
- customer profile and consolidated identities,
- tags, ownership, lifecycle stage, priority, and notes,
- customer activity timeline,
- manual reminders and recurring reminders,
- manual follow-up from ClientPulse,
- link existing WhatsApp contacts to canonical contacts,
- Google Contacts read-only import through Integrations,
- duplicate review and explicit merge,
- company-scoped permissions and reporting.

### 3.2 Later scope

- automated follow-up sequences,
- two-way Google Contacts synchronization,
- email and calendar integrations,
- custom fields,
- scoring and churn-risk policies,
- AI-assisted summaries or follow-up suggestions.

### 3.3 Explicitly out of scope for the first release

- sales invoices and accounting,
- unrestricted marketing blasts,
- automatic merging based only on names,
- automatic deletion caused by an external provider,
- bypassing outbound account restrictions,
- AI-dependent contact synchronization.

---

## 4. Django Applications

### 4.1 `apps/clientpulse`

Recommended structure:

```text
apps/clientpulse/
  admin.py
  apps.py
  models/
  services/
    contact_service.py
    identity_service.py
    activity_service.py
    reminder_service.py
    sequence_service.py
    merge_service.py
    reporting_service.py
  tasks/
    reminder_tasks.py
    sequence_tasks.py
  api/
    serializers.py
    views.py
    urls.py
  migrations/
  tests/
```

### 4.2 `apps/integrations`

Recommended structure:

```text
apps/integrations/
  admin.py
  apps.py
  models/
  connectors/
    base.py
    google_contacts.py
  services/
    connection_service.py
    credential_service.py
    contact_import_service.py
    sync_service.py
  tasks/
    google_contact_tasks.py
  api/
    serializers.py
    views.py
    urls.py
  migrations/
  tests/
```

Provider-neutral interfaces belong in `integrations.connectors.base`. Google-specific field mapping, OAuth behavior, error translation, and People API calls belong only in `integrations.connectors.google_contacts`.

---

## 5. Data Model

Every mutable business model must be directly company-owned unless ownership is safely immutable through a required parent. Querysets must still be explicitly company-scoped.

### 5.1 Existing model changes

#### `tenancy.CompanyContact`

Retain the existing model and add only generally useful canonical-contact fields:

- `contact_type`: person or organization,
- `first_name`, `middle_name`, `last_name`,
- `display_name`,
- `legal_name`,
- `is_active`,
- `archived_at`,
- `created_by`,
- `updated_by`,
- `created_at`, `updated_at`.

The existing category remains compatible with supplier/customer/both behavior. ClientPulse lifecycle stage must be separate from contact category.

#### `tenancy.CompanyContactIdentity`

Extend the existing model with:

- `company` for direct tenant scoping and indexing,
- `normalized_value`,
- `label`,
- `is_verified`,
- `is_active`,
- `source_type`: manual, WhatsApp, integration, import,
- `source_reference`,
- `created_at`, `updated_at`.

Normalization rules:

- phone numbers use a normalized international representation where possible,
- email addresses are trimmed and case-normalized,
- WhatsApp JIDs are normalized without losing LID aliases,
- raw source values remain available for audit.

Do not enforce company-wide uniqueness initially. Shared company numbers and shared email addresses are legitimate. Instead, generate duplicate candidates for review.

### 5.2 ClientPulse models

#### `ClientProfile`

One-to-one with `CompanyContact`.

Fields:

- `company`,
- `contact`,
- `owner` referencing a company member/user,
- `lifecycle_stage`: lead, prospect, active_customer, dormant, lost, blocked,
- `status`: active, paused, archived,
- `priority`: low, normal, high, critical,
- `source`: manual, WhatsApp, Google Contacts, import, referral, other,
- `preferred_channel`,
- `preferred_language`,
- `timezone`,
- `last_contacted_at`,
- `last_inbound_at`,
- `next_follow_up_at`,
- `do_not_contact`,
- `do_not_contact_reason`,
- `created_by`, `updated_by`,
- `created_at`, `updated_at`.

Indexes:

- company and lifecycle stage,
- company and owner,
- company and next follow-up,
- company and last contacted,
- company and status.

#### `ClientTag`

Tags are company-owned reusable labels managed from the ClientPulse customer profile. The tag API supports list/create and individual read/update/delete operations. Deletion is soft at the definition level, removes active profile assignments, and allows the same normalized name to be reactivated later. The profile UI reports assignment usage before deletion and supports name and color maintenance.

- `company`,
- `name`,
- `color`,
- `is_active`,
- timestamps.

Constraint: unique normalized tag name per company.

#### `ClientTagAssignment`

- `company`,
- `profile`,
- `tag`,
- `assigned_by`,
- `created_at`.

Constraint: one assignment per profile/tag pair.

#### `ClientNote`

- `company`,
- `profile`,
- `body`,
- `is_pinned`,
- `created_by`, `updated_by`,
- timestamps.

Notes are editable. Changes should produce an audit event.

#### `ClientActivity`

Append-only timeline record.

Fields:

- `company`,
- `profile`,
- `activity_type`: inbound_message, outbound_message, note, call, meeting, reminder, status_change, sequence_event, sync_event,
- `occurred_at`,
- `title`,
- `summary`,
- `channel`,
- `direction`,
- `source_model`, `source_id`,
- `metadata`,
- `created_by`,
- `created_at`.

Constraint: optional unique source tuple to prevent duplicate timeline projection.

The activity timeline references raw messages; it does not copy full message history unnecessarily.

#### `ClientReminder`

- `company`,
- `profile`,
- `assigned_to`,
- `title`, `description`,
- `due_at`,
- `timezone`,
- `priority`,
- `status`: pending, due, completed, snoozed, cancelled,
- `recurrence_type`: none, daily, weekly, monthly, custom,
- `recurrence_rule`,
- `snoozed_until`,
- `completed_at`, `completed_by`,
- `next_occurrence_at`,
- `created_by`,
- timestamps.

Indexes:

- company, status, due date,
- assigned user, status, due date,
- profile and due date.

#### `ContactConsent`

- `company`,
- `profile`,
- `channel`,
- `purpose`: transactional, follow_up, marketing,
- `status`: unknown, granted, denied, revoked,
- `source`,
- `captured_at`,
- `revoked_at`,
- `evidence`,
- timestamps.

Automated sending requires a non-blocking consent state defined by company policy. `do_not_contact` always wins.

#### `FollowUpSequence`

- `company`,
- `name`, `description`,
- `is_active`,
- `sending_mode`: reminders_only or automated,
- `stop_on_reply`,
- `created_by`,
- timestamps.

#### `FollowUpStep`

- `company`,
- `sequence`,
- `position`,
- `delay_seconds`,
- `action_type`: create_reminder, queue_message, change_stage,
- `channel`,
- `message_template`,
- `configuration`,
- `is_active`.

Constraint: one position per sequence.

#### `SequenceEnrollment`

- `company`,
- `sequence`,
- `profile`,
- `status`: active, paused, completed, stopped, failed,
- `current_step`,
- `next_action_at`,
- `stop_reason`,
- `enrolled_by`,
- timestamps.

Constraint: at most one active enrollment for a profile in the same sequence.

#### `ContactMergeCandidate`

- `company`,
- `left_contact`, `right_contact`,
- `match_reasons`,
- `confidence`,
- `status`: pending, merged, rejected,
- `reviewed_by`, `reviewed_at`,
- timestamps.

#### `ContactMergeAudit`

- `company`,
- `surviving_contact`,
- `merged_contact_snapshot`,
- `moved_relationships`,
- `merged_by`,
- `created_at`.

Merges must execute in one database transaction and must never cross company boundaries.

### 5.3 Integrations models

#### `IntegrationConnection`

- `company`,
- `provider`: initially `google_contacts`,
- `display_name`,
- `status`: pending, connected, attention_required, disabled, revoked,
- `external_account_id`,
- `external_account_email`,
- `granted_scopes`,
- encrypted credential reference,
- `sync_mode`: import_only or two_way,
- `is_active`,
- `last_connected_at`,
- `last_successful_sync_at`,
- `last_error`,
- `created_by`,
- timestamps.

Credentials must not be returned by serializers or written to normal logs.

#### `IntegrationSyncCursor`

- `connection`,
- `resource_type`,
- encrypted or protected cursor/token value,
- `parameters_hash`,
- `expires_at` when known,
- timestamps.

The parameters hash prevents reuse of a cursor with incompatible provider query parameters.

#### `ExternalContactLink`

- `company`,
- `connection`,
- `company_contact`,
- `external_resource_name`,
- `external_etag`,
- `external_updated_at`,
- `external_deleted_at`,
- `last_payload_hash`,
- `last_imported_at`,
- timestamps.

Constraints:

- external resource unique within a connection,
- one link cannot point across company boundaries.

#### `IntegrationSyncRun`

- `company`,
- `connection`,
- `sync_type`: full or incremental,
- `status`: queued, running, succeeded, partial, failed,
- task correlation ID,
- start and finish timestamps,
- fetched, created, linked, updated, skipped, deleted, conflict, and failed counts,
- error summary,
- structured diagnostics.

#### `IntegrationConflict`

- `company`,
- `connection`,
- `external_resource_name`,
- candidate contacts,
- conflicting fields,
- source snapshot,
- status: pending, resolved, ignored,
- resolution,
- resolved_by and resolved_at,
- timestamps.

---

## 6. Contact Linking and Deduplication

### 6.1 Deterministic matching order

1. Existing `ExternalContactLink` for the same connection and resource name.
2. Exact normalized verified phone identity in the same company.
3. Exact normalized email identity in the same company.
4. Exact WhatsApp JID or known phone/LID mapping in the same company.
5. Otherwise create a new canonical contact.

Name similarity must never be sufficient for automatic linking.

### 6.2 Ambiguous identity

If an identity matches more than one contact:

- do not select a contact arbitrarily,
- create `IntegrationConflict` or `ContactMergeCandidate`,
- retain the source snapshot,
- expose the conflict in the UI,
- allow an authorized user to link, create separately, or ignore.

### 6.3 Merge behavior

The merge service must:

- lock both contacts,
- verify equal company ownership,
- choose an explicit surviving contact,
- move identities, WhatsApp links, CRM profile data, tags, reminders, activities, and external links,
- resolve collisions predictably,
- archive the merged contact,
- create a complete audit record.

No background synchronization task may perform a merge automatically in the first release.

---

## 7. Activity Projection

ClientPulse should present a unified timeline without becoming another message store.

### 7.1 Timeline sources

- inbound WhatsApp messages,
- outbound message state changes,
- manual notes,
- calls and meetings entered by users,
- reminder creation/completion/snooze,
- lifecycle and ownership changes,
- sequence enrollment and execution,
- integration sync/link events.

### 7.2 Projection rules

- Raw WhatsApp messages remain in `whatsapp_bridge`.
- Client activities reference raw records through source type and ID.
- Projection is idempotent.
- Historical backfill is an explicit management task, not automatic on deployment.
- New inbound/outbound events update `last_inbound_at` and `last_contacted_at` asynchronously.

---

## 8. Reminder Processing

### 8.1 Execution design

Use a recurring scheduler entry to enqueue a reminder scan. Do not create one `BackgroundTaskSchedule` row for every reminder.

```text
Task Scheduler
  -> clientpulse.scan_due_reminders
  -> query due rows with locking
  -> enqueue clientpulse.deliver_reminder per reminder
  -> create in-app notification and activity
  -> calculate next recurrence if applicable
```

### 8.2 Reminder rules

- Store all timestamps in UTC and retain the reminder timezone.
- A reminder delivery is idempotent per reminder occurrence.
- Completing a recurring reminder creates or advances the next occurrence exactly once.
- Snoozing changes the effective due time without losing the original due time.
- Assignment must be limited to active members of the same company.
- Reminder delivery failure must be visible and retryable.
- Reminder processing must not send a customer message.

---

## 9. Follow-Up Sequences

### 9.1 First sequence release

Implement reminders-only sequences first. Automated message steps remain feature-disabled until manual reminders are stable.

### 9.2 Automated sequence requirements

Before a message step is enqueued, verify:

- sequence and enrollment are active,
- company automated sending setting is enabled,
- contact is active and not blocked,
- contact is not marked do-not-contact,
- consent policy allows the purpose and channel,
- preferred identity and account are still available,
- no qualifying customer reply occurred after the prior step,
- outbound account settings allow the operation.

The sequence handler creates an `OutboundMessage`; the outbound queue owns preflight and delivery.

### 9.3 Stop conditions

- customer reply,
- consent denied or revoked,
- do-not-contact enabled,
- contact archived,
- sequence disabled,
- manual stop,
- unrecoverable destination failure,
- maximum failure count reached.

---

## 10. Integrations Connector Contract

Every external contact connector must implement a provider-neutral interface similar to:

```python
class ContactConnector:
    def build_authorization_url(self, state): ...
    def exchange_authorization_code(self, code): ...
    def refresh_credentials(self, credentials): ...
    def get_account_identity(self): ...
    def full_sync(self, cursor=None): ...
    def incremental_sync(self, cursor): ...
    def normalize_contact(self, provider_record): ...
    def validate_connection(self): ...
    def revoke_connection(self): ...
```

The normalized contact contract should include:

- provider resource ID,
- etag/version,
- deletion state,
- display and structured names,
- organizations,
- phone identities,
- email identities,
- addresses,
- birthday when authorized,
- provider update timestamp,
- raw payload hash,
- minimal diagnostic metadata.

ClientPulse receives only normalized import records through `contact_import_service`.

---

## 11. Google Contacts Integration

### 11.1 API and authorization

Use Google People API `people.connections.list` for contact synchronization.

Initial scope:

```text
https://www.googleapis.com/auth/contacts.readonly
```

Do not request write scope in the initial release. Google OAuth setup must include:

- OAuth client configuration,
- exact redirect URI,
- state validation,
- PKCE where supported by the chosen server flow,
- encrypted refresh-token storage,
- granted-scope validation,
- reconnect and revoke actions.

### 11.2 Full synchronization

1. Create `IntegrationSyncRun`.
2. Enqueue `integrations.google_contacts.full_sync`.
3. Page through connections using a fixed field mask.
4. Normalize each provider record.
5. Link, create, update, skip, or record conflict.
6. Store the returned next sync token only after the full run succeeds.
7. Record counts and completion state.

### 11.3 Incremental synchronization

1. Load the connection cursor and original parameters hash.
2. Enqueue `integrations.google_contacts.incremental_sync`.
3. Request changes using the sync token.
4. Process changed and deleted resources.
5. Replace the cursor only after successful completion.
6. If Google reports an expired token, enqueue a controlled full sync.

Google incremental sync tokens expire after seven days, deleted contacts are returned with deleted metadata, and requests using a sync token must preserve the original request parameters. The implementation must account for all three behaviors.

### 11.4 External deletion

When Google marks a resource deleted:

- mark `ExternalContactLink.external_deleted_at`,
- record a sync activity,
- retain the canonical contact and its local data,
- do not remove WhatsApp links, reminders, notes, or history,
- optionally show an operator review action.

### 11.5 Future two-way mode

Two-way sync requires a separate implementation phase with:

- Google write scope,
- explicit source-of-truth policy per field,
- etag conflict handling,
- local dirty-field tracking,
- retry-safe provider writes,
- deletion confirmation,
- loop prevention.

It must not be enabled merely by changing `sync_mode` in the database.

---

## 12. Durable Tasks and Queues

### 12.1 Queue definitions

Add two queues:

- `clientpulse`: reminders, activity projection, sequence progression, reporting maintenance.
- `integrations`: OAuth-independent synchronization and provider API work.

Outbound messages continue to use `outbound`.

### 12.2 ClientPulse task keys

- `clientpulse.scan_due_reminders`
- `clientpulse.deliver_reminder`
- `clientpulse.project_activity`
- `clientpulse.advance_sequence`
- `clientpulse.stop_sequences_on_reply`
- `clientpulse.refresh_profile_metrics`

### 12.3 Integrations task keys

- `integrations.google_contacts.full_sync`
- `integrations.google_contacts.incremental_sync`
- `integrations.google_contacts.validate_connection`
- `integrations.cleanup_expired_sync_runs`

### 12.4 Task requirements

- versioned payloads,
- company ownership validation inside every handler,
- explicit idempotency keys,
- retry-safe database transitions,
- bounded provider timeout,
- rate-limit-aware retry delay,
- correlation IDs containing connection, sync run, reminder, or enrollment identity,
- no credentials or personal source payloads in task event messages.

---

## 13. API Design

All endpoints are under `/api/clientpulse/` or `/api/integrations/` and derive the active company from the authenticated request.

### 13.1 ClientPulse endpoints

```text
GET/POST   /api/clientpulse/clients/
GET/PATCH  /api/clientpulse/clients/{id}/
POST       /api/clientpulse/clients/{id}/archive/
GET        /api/clientpulse/clients/{id}/timeline/
GET/POST   /api/clientpulse/clients/{id}/notes/
GET/POST   /api/clientpulse/clients/{id}/reminders/
POST       /api/clientpulse/clients/{id}/link-whatsapp-contact/
POST       /api/clientpulse/clients/{id}/follow-up/
POST       /api/clientpulse/clients/{id}/enroll-sequence/

GET/POST   /api/clientpulse/reminders/
PATCH      /api/clientpulse/reminders/{id}/
POST       /api/clientpulse/reminders/{id}/complete/
POST       /api/clientpulse/reminders/{id}/snooze/

GET/POST   /api/clientpulse/sequences/
GET/PATCH  /api/clientpulse/sequences/{id}/
POST       /api/clientpulse/sequences/{id}/activate/
POST       /api/clientpulse/sequences/{id}/disable/

GET        /api/clientpulse/merge-candidates/
POST       /api/clientpulse/merge-candidates/{id}/merge/
POST       /api/clientpulse/merge-candidates/{id}/reject/

GET        /api/clientpulse/dashboard/
GET        /api/clientpulse/reports/follow-up/
```

### 13.2 Integrations endpoints

```text
GET/POST   /api/integrations/connections/
GET        /api/integrations/connections/{id}/
POST       /api/integrations/google-contacts/authorize/
GET        /api/integrations/google-contacts/callback/
POST       /api/integrations/connections/{id}/sync/
POST       /api/integrations/connections/{id}/validate/
POST       /api/integrations/connections/{id}/disable/
POST       /api/integrations/connections/{id}/revoke/
GET        /api/integrations/connections/{id}/sync-runs/
GET        /api/integrations/conflicts/
POST       /api/integrations/conflicts/{id}/resolve/
```

OAuth callback state must identify the initiating user and company without trusting a company ID supplied by the browser.

---

## 14. Users, Roles, and Permissions

### 14.1 Goal

The authorization system must support multiple users in one company with different access to Conversations, Trading, Campaigns, ClientPulse, Reports, Integrations, Settings, and Task Operations.

Authorization has three independent layers:

1. **Tenant boundary:** which company the request is operating in.
2. **Capability:** which action the user may perform.
3. **Record scope:** which company records the user may perform that action on.

A permission never widens the tenant boundary. Even a company owner cannot read another company through a company-scoped endpoint.

### 14.2 Current-state limitation

`CompanyMembership.role` currently stores one of `super_user`, `admin`, `manager`, `user`, or `viewer`. `TenantRolePermission` then converts HTTP methods into broad access decisions.

This is insufficient because:

- a user cannot be granted Campaign access without also receiving unrelated write access,
- Integrations and automated sending require stronger restrictions than ordinary editing,
- ClientPulse agents need assigned-client scope rather than all-company access,
- frontend visibility and backend authorization cannot be described from one permission set,
- adding every new area would require more hardcoded role branches.

The existing role field remains during migration, but it must stop being the final authorization source after RBAC is enabled.

### 14.3 Authorization models

The following models belong in `apps/tenancy` because roles apply across ChatLens, not only to ClientPulse.

#### `PermissionDefinition`

Global registry of capabilities shipped by ChatLens.

Fields:

- `code`, globally unique, for example `clientpulse.clients.update`,
- `area`, for example `clientpulse`,
- `label`,
- `description`,
- `supports_scope`,
- `is_sensitive`,
- `is_active`,
- timestamps.

Permission definitions are created through migrations or a deterministic seed service. Company administrators cannot invent arbitrary permission codes.

#### `CompanyRole`

Company-owned reusable role.

Fields:

- `company`,
- `key`, unique within the company,
- `name`,
- `description`,
- `is_system_role`,
- `is_owner_role`,
- `is_active`,
- `created_by`, `updated_by`,
- timestamps.

Constraints:

- unique `(company, key)`,
- only the seeded Owner role may have `is_owner_role=True`,
- system role keys cannot be changed,
- a role referenced by active memberships cannot be deleted; it may be disabled only after reassignment.

#### `CompanyRolePermission`

Grant of one capability to one role.

Fields:

- `company`,
- `role`,
- `permission`,
- `record_scope`: `all`, `assigned`, or `own`,
- `created_by`,
- `created_at`.

Constraint: one grant per role and permission.

Scope meanings:

- `all`: all records in the active company that the endpoint normally exposes.
- `assigned`: records assigned to the current user, plus explicitly shared records where supported.
- `own`: records created by or directly owned by the current user.

If a resource does not implement assigned/own filtering, its permission definition must set `supports_scope=False` and only `all` is valid. Do not present a scope selector that the backend cannot enforce.

#### `MembershipRoleAssignment`

Many-to-many assignment between `CompanyMembership` and `CompanyRole`.

Fields:

- `company`,
- `membership`,
- `role`,
- `assigned_by`,
- `assigned_at`.

Constraints:

- unique membership/role pair,
- membership, role, and direct company must agree,
- inactive memberships receive no effective permissions.

Multiple roles are allowed. Grants are additive. There are no explicit deny rules in the first implementation because mixed allow/deny precedence is difficult to explain and audit. If a user needs an exception, create or assign a more suitable role.

#### `AuthorizationAuditEvent`

Append-only audit trail.

Fields:

- `company`,
- `actor`,
- `target_membership`,
- `target_role`,
- `event_type`,
- before and after snapshots,
- request correlation ID,
- IP and user-agent metadata where available,
- `created_at`.

Audit events are required for invitation, activation, deactivation, role assignment, role removal, permission changes, ownership transfer, and Integration-management changes.

### 14.4 User and membership lifecycle

The Django user remains a login identity. `CompanyMembership` remains the relationship between that user and a company.

Required membership states:

- invited,
- active,
- suspended,
- deactivated.

Add or formalize:

- invitation email/token and expiry,
- invited by and invited at,
- accepted at,
- last company access at,
- membership status,
- optional job title,
- optional default role assignment.

Rules:

- one user may belong to multiple companies,
- roles are assigned separately inside each company,
- switching active company recalculates permissions from that membership,
- suspended/deactivated membership receives no company access,
- removing a membership must not delete records created by that user,
- the last active Owner membership cannot be removed, suspended, or stripped of the Owner role,
- ownership transfer requires another active membership and an audit event.

### 14.5 Default company roles

Seed the following roles for every company. Companies may create additional roles or clone a default role.

#### Owner (`super_user` compatibility key)

- complete company access,
- manage users, roles, settings, Integrations, sending policy, and automation,
- transfer company ownership,
- cannot bypass the company tenant boundary,
- cannot disable the final active Owner.

#### Administrator (`admin` compatibility key)

- manage ordinary users and non-Owner roles,
- manage company settings and Integrations,
- manage ClientPulse configuration and campaigns,
- cannot transfer ownership or grant/remove Owner role,
- cannot access control-company infrastructure unless separately authorized as a platform operator.

#### Manager (`manager` compatibility key)

- view and update operational records across the company,
- manage ClientPulse clients, reminders, and sequences,
- run campaigns and view reports,
- assign work to users,
- cannot manage company Integrations, users, roles, or sensitive sending settings by default.

#### Sales Agent (`user` compatibility key)

- access assigned ClientPulse customers and reminders,
- add notes and perform manual follow-up,
- use permitted conversations and trading workflows,
- no automated sending, role management, Integrations, or company settings.

#### Viewer (`viewer` compatibility key)

- read-only access to explicitly granted areas,
- no message send, export, edit, reminder completion, or configuration changes.

#### Campaign Operator (new template)

- view required contacts and products,
- create and operate campaigns,
- perform permitted manual sends,
- no ClientPulse merge, Integrations, user administration, or automation enablement.

#### Integration Manager (new template)

- view and manage Integrations connections and conflicts,
- run synchronization,
- view synchronization logs,
- no user/role administration and no general CRM deletion rights.

### 14.6 Permission naming convention

Permission codes use `<area>.<resource>.<action>`.

Actions should use a stable vocabulary:

- `view`,
- `create`,
- `update`,
- `delete`,
- `manage`,
- `send`,
- `export`,
- `execute`,
- `approve`.

Do not encode HTTP methods into permission names.

### 14.7 Initial permission catalog

#### Conversations

- `conversations.chats.view`
- `conversations.messages.view`
- `conversations.messages.send`
- `conversations.contacts.update`
- `conversations.accounts.manage`

#### Trading

- `trading.board.view`
- `trading.inquiries.update`
- `trading.matches.manage`
- `trading.products.view`
- `trading.products.manage`
- `trading.automation.manage`

#### Campaigns

- `campaigns.campaigns.view`
- `campaigns.campaigns.create`
- `campaigns.campaigns.update`
- `campaigns.campaigns.delete`
- `campaigns.messages.send`
- `campaigns.audiences.manage`

#### ClientPulse

- `clientpulse.clients.view`
- `clientpulse.clients.create`
- `clientpulse.clients.update`
- `clientpulse.clients.archive`
- `clientpulse.notes.manage`
- `clientpulse.reminders.view`
- `clientpulse.reminders.manage`
- `clientpulse.sequences.view`
- `clientpulse.sequences.manage`
- `clientpulse.messages.send_manual`
- `clientpulse.messages.send_automated`
- `clientpulse.contacts.merge`
- `clientpulse.consent.manage`
- `clientpulse.reports.view`
- `clientpulse.data.export`

#### Integrations

- `integrations.connections.view`
- `integrations.connections.manage`
- `integrations.sync.execute`
- `integrations.sync.view_history`
- `integrations.conflicts.resolve`

#### Reports and operations

- `reports.company.view`
- `reports.company.export`
- `tasks.company.view`
- `tasks.company.retry`

#### Administration

- `settings.company.view`
- `settings.company.manage`
- `users.memberships.view`
- `users.memberships.manage`
- `users.roles.view`
- `users.roles.manage`
- `sending.policy.manage`
- `automation.company.enable`

Sensitive permissions must be marked in `PermissionDefinition`. Sensitive examples include automated sending, Integration credentials, data export, role management, and company-wide sending policy.

### 14.8 Default role matrix

This table summarizes defaults; the seeded grant records remain the executable source of truth.

| Area | Owner | Admin | Manager | Sales Agent | Campaign Operator | Integration Manager | Viewer |
|---|---|---|---|---|---|---|---|
| Conversations | Full | Full | Full | Assigned/operational | View + send | View | View |
| Trading | Full | Full | Manage | Operational | Product view | None | View |
| Campaigns | Full | Full | Manage | View | Manage + send | None | View |
| ClientPulse clients | Full | Full | All clients | Assigned clients | View required audience | View | View |
| Reminders | Full | Full | All | Assigned | None | None | View |
| Sequences | Full | Full | Manage | View assigned | None | None | View |
| Automated send | Enable + execute | Enable + execute | Execute if enabled | None | None | None | None |
| Integrations | Full | Full | View status | None | None | Manage | View status |
| Reports | Full | Full | Full | Assigned scope | Campaign reports | Sync reports | View |
| Users and roles | Full | Manage non-Owner | View | None | None | None | None |
| Company settings | Full | Manage | View | None | None | None | None |
| Task Operations | Company data | Company data | View company data | None | None | Sync tasks | None |

### 14.9 Effective permission calculation

For the active company:

1. Load the active membership.
2. Reject inactive, suspended, or deactivated membership.
3. Load all active assigned roles.
4. Union their permission grants.
5. For duplicate grants, choose the widest scope: `own < assigned < all`.
6. Apply immutable platform restrictions such as Owner-only ownership transfer.
7. Return permission codes and scopes to the request authorization service.

The effective permission result may be cached briefly by `(membership_id, authorization_version)`. Increment `authorization_version` whenever membership, role, or grant data changes so revocation takes effect immediately without waiting for cache expiry.

### 14.10 Backend enforcement

Add central services in `apps.tenancy.services.authorization`:

```python
has_company_permission(user, permission_code, company=None)
permission_scope(user, permission_code, company=None)
require_company_permission(user, permission_code, company=None)
scope_queryset_for_permission(queryset, user, permission_code, ownership_field, assignee_field)
```

Add reusable DRF permission classes:

```python
RequiredCompanyPermission
RequiredAnyCompanyPermission
CompanyOwnerPermission
```

Each protected view declares permission codes explicitly. Example:

```python
required_permissions = {
    'list': 'clientpulse.clients.view',
    'retrieve': 'clientpulse.clients.view',
    'create': 'clientpulse.clients.create',
    'partial_update': 'clientpulse.clients.update',
    'archive': 'clientpulse.clients.archive',
}
```

Rules:

- frontend hiding is not authorization,
- service methods performing sensitive operations must check authorization even when called outside a view,
- task handlers validate company ownership and rely on the authorizing user snapshot captured when work was requested,
- permission checks occur before revealing whether a foreign-company object exists,
- unauthorized cross-company access returns the existing non-disclosure behavior, normally 404 for objects and 403 for unavailable actions.

### 14.11 Background task authorization

Long-running tasks must not become authorized merely because they are running as a worker.

Task producers for user-initiated sensitive work store:

- `created_by`,
- company,
- required permission code,
- authorization version or immutable authorization snapshot,
- business object ID.

At execution:

- revalidate active company membership for destructive or send operations,
- revalidate automated sending and company safety settings,
- cancel clearly if access was revoked,
- never store a credential or full permission list in a task payload.

Scheduled system maintenance uses a documented system principal/policy and cannot perform user-only actions such as granting roles.

### 14.12 Frontend behavior

`GET /api/auth/me/` should return for the active company:

```json
{
  "membership": {
    "id": 10,
    "status": "active",
    "roles": [{"id": 4, "key": "sales_agent", "name": "Sales Agent"}]
  },
  "permissions": {
    "clientpulse.clients.view": "assigned",
    "clientpulse.reminders.manage": "assigned",
    "clientpulse.messages.send_manual": "assigned"
  },
  "authorization_version": 12
}
```

The frontend must:

- hide navigation areas without view permission,
- hide or disable actions without action permission,
- explain disabled sensitive actions where useful,
- refresh auth context after company switch or role change,
- treat a backend 403 as authoritative,
- never infer permissions from role names.

### 14.13 User and role management UI

Add under Settings:

```text
Settings
  Users
  Roles & Permissions
```

Users screen:

- active, invited, suspended, and deactivated tabs,
- invite user,
- assign/remove roles,
- show effective permission summary,
- suspend/reactivate membership,
- transfer ownership where authorized,
- audit history.

Roles & Permissions screen:

- default and custom role list,
- clone role,
- grouped permission matrix by area,
- scope selector only for scope-aware permissions,
- sensitive-permission warning,
- affected-user count,
- unsaved-change protection,
- role audit history.

### 14.14 Users and roles API

```text
GET/POST   /api/company/users/
GET/PATCH  /api/company/users/{membership_id}/
POST       /api/company/users/invite/
POST       /api/company/users/{membership_id}/suspend/
POST       /api/company/users/{membership_id}/reactivate/
POST       /api/company/users/{membership_id}/assign-role/
POST       /api/company/users/{membership_id}/remove-role/
POST       /api/company/users/transfer-ownership/

GET/POST   /api/company/roles/
GET/PATCH  /api/company/roles/{role_id}/
POST       /api/company/roles/{role_id}/clone/
POST       /api/company/roles/{role_id}/disable/
GET        /api/company/permissions/
GET        /api/company/authorization-audit/
```

### 14.15 Migration from existing roles

Migration must be staged to avoid removing current access unexpectedly.

1. Create permission definitions and RBAC tables.
2. Seed default roles for every existing company.
3. Map legacy `CompanyMembership.role` values to matching default roles.
4. Assign each existing membership its mapped role.
5. Run comparison logging: evaluate legacy and RBAC decisions without enforcing RBAC.
6. Review mismatches for all major routes.
7. Enable RBAC enforcement behind a company setting/feature flag.
8. Migrate viewsets from coarse `TenantRolePermission` to declared permission codes.
9. Remove legacy authorization branches only after route coverage is complete.
10. Keep the legacy `role` column temporarily for compatibility reporting, then remove it in a later migration.

Do not partially enforce RBAC on navigation while APIs still use unrelated legacy logic without documenting the route-level state.

### 14.16 Authorization acceptance criteria

1. A user can belong to multiple companies with different roles in each.
2. Company switching changes effective permissions immediately.
3. No role or permission grants cross-company data access.
4. A Sales Agent can be limited to assigned ClientPulse records.
5. A Campaign Operator can send permitted campaigns without receiving Integrations or user-management access.
6. An Integration Manager can synchronize Google Contacts without gaining general administrator access.
7. Viewer access is read-only at the API, not only in the UI.
8. The final Owner cannot be removed or disabled.
9. Sensitive role changes are audited with before and after state.
10. Revoked send or Integration permissions prevent queued sensitive work from starting.
11. Frontend navigation and actions derive from permission codes, not role names.
12. Every protected route has an automated permission-matrix test.

---

## 15. Company Settings

Seed the following settings during company enrollment:

```json
{
  "clientpulse_enabled": true,
  "reminder_notifications_enabled": true,
  "automated_follow_up_enabled": false,
  "automatic_contact_merge_enabled": false,
  "default_contact_timezone": "Asia/Dubai",
  "sequence_max_messages_per_contact_per_day": 0,
  "google_contacts_sync_enabled": false,
  "google_contacts_sync_interval_minutes": 60
}
```

`0` automated messages means disabled until an administrator configures and enables the feature.

---

## 16. Frontend Information Architecture

### 16.1 Navigation

```text
ClientPulse
  Dashboard
  Customers
  Reminders
  Sequences
  Activity

Settings
  ClientPulse
  Integrations
  Users
  Roles & Permissions
```

### 16.2 Dashboard

- reminders due today,
- overdue reminders,
- customers without future follow-up,
- dormant customers,
- recent replies,
- active sequences,
- sync health and unresolved conflicts,
- follow-up completion and response metrics.

### 16.3 Customer list

- compact paginated grid,
- server-side search/filter/sort,
- lifecycle, owner, priority, tags, source, last contact, next follow-up,
- saved filters,
- bulk owner/tag/stage actions,
- duplicate warning,
- create and import actions.

Implemented behavior:

- the grid uses the common data-table treatment and server pagination,
- filters use shared searchable selects and inputs,
- the create-client dialog uses the large, tall shared modal,
- manual creation exposes name, phone, owner, lifecycle, and priority,
- WhatsApp conversion uses one searchable selector,
- candidate search is server-side and follows company/user account visibility rules.

### 16.4 Customer profile

- profile summary,
- contact identities,
- linked WhatsApp contacts and accounts,
- owner, lifecycle, priority and tags,
- consent and do-not-contact state,
- timeline,
- notes,
- reminders,
- sequence enrollment,
- manual contact actions,
- paginated direct conversation history across linked communication accounts,
- related inquiries and campaigns.

Implemented behavior:

- all cards, inputs, selects, checkboxes, badges, notices, empty states, and actions use shared UI components,
- the profile is responsive: two-column cards collapse to one column on narrower screens,
- the manual WhatsApp follow-up composer uses the same shared controls,
- text/image limits, image preview, live preflight, consent, do-not-contact, and outbound queue behavior remain unchanged,
- activity displays outbound state without sending synchronously from the profile request.
- conversation history is limited to linked direct chats and account visibility granted to the current user; group messages are excluded.

### 16.5 Reminder workspace

- My Reminders,
- Overdue,
- Today,
- Upcoming,
- Completed,
- assigned-user and company filters,
- complete, snooze, reassign, cancel actions.

### 16.6 Integrations screen

- provider connection cards,
- Google account identity and granted scope,
- connected/attention/disabled status,
- last success and last error,
- Sync Now, Reconnect, Disable and Revoke actions,
- sync history grid,
- imported/updated/skipped/conflict counts,
- conflict-resolution screen.

---

## 17. Reporting Metrics

- total active clients,
- clients by lifecycle, owner, source, and tag,
- clients due or overdue for follow-up,
- clients without a future reminder,
- average time from inbound message to follow-up,
- reminder completion and overdue rates,
- manual and automated message outcomes,
- sequence enrollment, reply, completion, stop, and failure rates,
- dormant-client count,
- integration sync duration and failure rate,
- imported, linked, created, updated, skipped, deleted, and conflict counts.

Metrics must be company-scoped and computed from auditable source records.

---

## 18. Security and Privacy

- Encrypt OAuth refresh tokens at rest.
- Never expose provider credentials through APIs.
- Never place credentials in task payloads, logs, or task event metadata.
- Validate active company ownership at API and service layers.
- Use OAuth state with expiry and one-time consumption.
- Request the minimum Google scope required.
- Record who connected, reconnected, disabled, or revoked a provider.
- Keep personal-data exports and deletion as explicit audited operations.
- Apply retention rules to raw provider payloads.
- Keep contact suppression and consent history even if a contact is archived.

---

## 19. Migration and Rollout Plan

### Phase 0 - Company RBAC foundation

- Add permission definitions, company roles, role grants, membership assignments, and authorization audit events.
- Seed and map existing Owner, Admin, Manager, User, and Viewer memberships.
- Expose effective permissions from the active-company auth response.
- Build Users and Roles & Permissions settings screens.
- Run legacy/RBAC comparison logging before enforcement.
- Migrate ClientPulse and Integrations endpoints directly to declared RBAC permissions.

Exit criteria:

- all existing memberships retain intended access,
- role changes invalidate effective permissions immediately,
- last-Owner protection is enforced transactionally,
- frontend visibility and API authorization use the same permission codes,
- permission-matrix and cross-company tests pass.

### Phase 1 - Canonical contact hardening

- Extend `CompanyContact` and identities.
- Add normalization services.
- Link existing WhatsApp contacts deterministically where safe.
- Produce merge candidates for ambiguity.
- Do not rewrite raw WhatsApp contact records.

Exit criteria:

- every new CRM contact is company-scoped,
- no cross-company identity links,
- WhatsApp links can be created and removed safely,
- duplicate candidates are reviewable.

### Phase 2 - ClientPulse directory and profiles

**Implemented; shared UI migration completed 2026-10-06.**

- Add ClientProfile, tags, notes, consent and ownership.
- Build customer list and profile UI.
- Add permissions and company settings.
- Add audit events.
- Allow authorized users to create a profile from an existing visible WhatsApp contact.
- Apply the shared Inspinia component system to the directory and profile workspace.

Exit criteria:

- users can maintain a complete customer profile,
- filters and pagination work at production volume,
- tenant-isolation tests pass.

### Phase 3 - Timeline and reminders

**Implemented 2026-10-01; shared UI migration completed 2026-10-06.**

- Add activity projection.
- Add reminders and in-app notifications.
- Register ClientPulse queue and tasks.
- Add dashboard reminder metrics.

Exit criteria:

- reminders survive restart,
- recurrence is idempotent,
- overdue and assigned views are accurate,
- no reminder sends a customer message.

### Phase 4 - Manual customer contact

**Implemented 2026-10-02.**

- Add manual WhatsApp follow-up actions.
- Use existing preflight and outbound queues.
- Project delivery state to the timeline.
- Record clicks and queue outcomes.

Exit criteria:

- all existing outbound restrictions remain effective,
- timeline shows queued, sent, delivered, and failed states,
- no synchronous provider send occurs in IIS.

### Phase 5 - Integrations foundation and Google Contacts import

- Create Integrations app and connector contract.
- Implement Google OAuth and read-only People API connector.
- Add full and incremental sync tasks.
- Build Integrations settings and sync-history UI.
- Add conflict handling.

Exit criteria:

- credentials are encrypted,
- full sync is resumable/retry-safe,
- incremental sync uses the stored cursor,
- expired cursor triggers controlled full sync,
- external deletion does not delete CRM history,
- repeated sync does not duplicate contacts.

### Phase 6 - Follow-up sequences

- Add reminders-only sequences.
- Add enrollment and stop conditions.
- Measure sequence execution.
- Keep automated sending feature-disabled.

Exit criteria:

- sequence steps execute exactly once,
- replies stop eligible sequences,
- pause and manual stop work immediately.

### Phase 7 - Controlled automated sending

- Add explicit company enablement.
- Add consent policy and daily contact limits.
- Route message steps through outbound queue.
- Add operational dashboards and emergency stop.

Exit criteria:

- automation is OFF by default,
- do-not-contact and reply stop conditions are enforced,
- all sends respect account throttles and preflight,
- administrators can stop all ClientPulse automation immediately.

### Phase 8 - Optional Google two-way sync

- Define field ownership policy.
- Request write scope separately.
- Add dirty tracking and etag conflicts.
- Add provider write tasks and confirmation UI.

This phase requires separate approval and must not be implied by the read-only integration.

---

## 20. Testing Strategy

### 20.1 Unit tests

- phone/email/JID normalization,
- deterministic matching,
- duplicate candidate generation,
- merge collision rules,
- reminder recurrence,
- sequence stop conditions,
- provider normalization,
- token-expiry error translation.

### 20.2 API tests

- company isolation for every endpoint,
- role and permission enforcement,
- default-role permission matrix,
- multiple-role grant union and scope precedence,
- membership suspension and immediate revocation,
- last-Owner protection and ownership transfer,
- cross-company relationship rejection,
- pagination/filtering/ordering,
- OAuth state validation,
- credential omission from responses,
- merge and conflict resolution.

### 20.3 Task tests

- idempotency under duplicate enqueue,
- retry after transient provider failure,
- timeout behavior,
- cursor replacement only after success,
- expired sync-token recovery,
- reminder delivery exactly once per occurrence,
- reply-triggered sequence stop.

### 20.4 Integration tests

- mocked Google full sync with pagination,
- mocked incremental changes and deletions,
- rate limit and authorization revocation,
- outbound preflight and queue integration,
- WhatsApp timeline projection.

### 20.5 Visual tests

- desktop and mobile customer directory,
- large profile timelines,
- overdue reminder states,
- empty and failed integration states,
- sync progress and history,
- duplicate/conflict comparison,
- permission-hidden actions,
- long names, multiple identities, and missing contact details.

---

## 21. Operational Observability

Task Operations must show ClientPulse and Integrations tasks scoped to the active company for normal tenants.

Required operational fields:

- queue and task key,
- company,
- correlation ID,
- connection/sync run or reminder/enrollment reference,
- attempts and timeout,
- provider response category without secrets,
- fetched/processed/conflict counts,
- duration and throughput,
- terminal result and retry reason.

Provide alerts for:

- repeated OAuth refresh failure,
- revoked connection,
- sync cursor expiry loops,
- high conflict rate,
- reminder backlog,
- sequence task backlog,
- outbound failure spike.

---

## 22. Definition of Done

ClientPulse initial production scope is complete when:

1. Each company has an isolated canonical customer directory.
2. Existing WhatsApp contacts can link to canonical contacts without changing ingestion behavior.
3. Users can maintain profile, ownership, lifecycle, tags, notes, consent, and reminders.
4. The customer timeline combines CRM and referenced WhatsApp activity without duplicate records.
5. Reminders are durable, assigned, recurring, snoozable, and observable.
6. Manual follow-up uses the existing outbound queue and all safety policies.
7. Integrations can connect a Google account and perform read-only full and incremental contact synchronization.
8. Repeated Google synchronization does not duplicate contacts.
9. Ambiguous matches are held for review instead of merged automatically.
10. External deletion does not destroy ClientPulse history.
11. All APIs, tasks, reports, and UI data are company-scoped.
12. Automated customer messaging remains disabled until separately enabled and accepted.

---

## 23. Recommended First Implementation Slice

The first coding round should include only:

1. Company RBAC models, permission registry, default roles, authorization service, and audit events.
2. Existing membership-to-role migration and comparison mode.
3. Users and Roles & Permissions APIs and settings screens.
4. `clientpulse` and `integrations` Django app scaffolding.
5. Canonical contact identity normalization fields and services.
6. ClientProfile, ClientTag, ClientNote, ClientActivity, and ClientReminder models.
7. Tenant-scoped ClientPulse directory/profile/reminder APIs using declared permission codes.
8. ClientPulse navigation, customer list, profile, and reminder UI.
9. `clientpulse` queue registration and durable reminder tasks.
10. Safe company defaults.
11. Tests for tenant isolation, permission matrices, identity normalization, reminder idempotency, and revocation.

Google OAuth and synchronization should begin only after this first slice proves the canonical contact and duplicate-handling behavior.

---

## 24. External References

- Google People API overview: https://developers.google.com/people
- Google `people.connections.list`: https://developers.google.com/people/api/rest/v1/people.connections/list
- Google OAuth 2.0: https://developers.google.com/identity/protocols/oauth2
- Google API OAuth scopes: https://developers.google.com/identity/protocols/oauth2/scopes
- Google sensitive-scope verification: https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification
