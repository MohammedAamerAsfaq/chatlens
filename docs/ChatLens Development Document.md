# ChatLens Development Document

> **Status:** Living document — reflects the system as actually built, not the original plan.
> Last updated: 2026-07-18 (§17.2 — 6th connection-reliability incident: a third, distinct failure mode identified — silent inbound non-delivery with zero trace anywhere in the pipeline, not a decrypt failure or a logged drop. No fix possible from this codebase; opened as a watch item to track further occurrences)
>
> Previous: 2026-07-18 (§17.2 — 5th connection-reliability incident: `MessageCounterError` decrypt failures confirmed to cause real, permanent outbound-message loss on reconnect-triggered backlog delivery — 106 of 407 recent decrypt failures had no earlier successful copy anywhere; same root cause as the 4th incident, still deferred)
>
> Earlier: 2026-07-14 (Trading Analytics date-range filter + close-stale housekeeping, human-in-the-loop match correction — Fix/Auto/embedding search + 1-5 classification rating, popup/modal UX overhaul made draggable and click-outside-proof across the trading desk and Products page, Worker Alerts list-endpoint bug fix, `connection_unhealthy` clear-on-reconnect bug fix, new Stuck Receipts system, product aliases rebuilt from a JSON list into a first-class `ProductAlias` model with per-alias embeddings and multi-vector retrieval, embedding-status/backfill visibility)

---

## 1. Product Name

**ChatLens**

---

## 2. Purpose

ChatLens is a WhatsApp QR-session based conversation intelligence system. It reads WhatsApp conversations, stores them in a structured PostgreSQL database, generates vector embeddings for semantic search, and provides dashboards for analytics, contact management, message intelligence, and — as of the B2B Trading Intelligence feature — real-time AI classification of buy/sell inquiries for a wholesale trading desk.

ChatLens is a read-first system. Sending is deliberately disabled; the one exception is `whatsapp://send?phone=` deep links from the UI, which hand off to the user's own WhatsApp client rather than sending through the platform — optionally with a `text=` param that prefills the compose box (e.g. inquiry item + price, a price-check, or the full price list). The user still has to press send themselves; ChatLens never sends on their behalf.

---

## 3. Technology Stack

### Backend
- **Django** + Django REST Framework
- **PostgreSQL** with the `pgvector` extension
- Daemon threads for background embedding (no Celery in current version)

### WhatsApp QR Worker
- **Node.js** microservice using the **Baileys** library
- Communicates with Django over an internal REST API secured by `INTERNAL_API_TOKEN`

### Frontend
- **Vue 3** (Vite) — single-page app served separately
- Tailwind CSS

### Embedding
- **Voyage AI** — `voyage-3-lite` model, **512-dimension** vectors
- One embedding per message that has non-empty text

---

## 4. Architecture

```
WhatsApp Mobile
   ↓ scans QR
Node.js Baileys Worker (whatsapp-worker/)
   ↓ captures every message.upsert event
   ├─ live messages  → POST /api/internal/whatsapp/message-ingest/
   ├─ history sync   → POST /api/internal/whatsapp/message-ingest-batch/
   ├─ contact names  → POST /api/internal/whatsapp/contacts-update/
   ├─ session events → POST /api/internal/whatsapp/session-status/
   └─ dropped events → POST /api/internal/whatsapp/dropped-message/
Django API (apps/)
   ↓ ingestion service normalises payload
PostgreSQL
   ├─ whatsapp_* tables (messages, contacts, chats, accounts)
   └─ message_embedding (pgvector, 512-dim)
Vue 3 Frontend
   └─ /api/* public REST API
```

All internal worker→Django calls carry the `X-Internal-Token` header. All frontend→Django calls use session auth + CSRF.

---

## 5. Django Apps

```
apps/
  chatlens_core/          system settings
  whatsapp_bridge/        accounts, sessions, chats, contacts, groups/communities, messages, sync logs, dropped messages
  message_intelligence/   embeddings, semantic search
  ai_providers/           AI provider config (Voyage, OpenAI, etc.)
  trading/                B2B trading intelligence — products, classification, inquiries, prompts, agent call logs
  api/                    public REST API for the Vue frontend + session auth (login/logout/me)
```

---

## 6. Database Schema (actual)

### 6.1 whatsapp_account

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| display_name | varchar(255) | |
| phone_number | varchar(50) | |
| session_status | varchar(50) | see §8 |
| worker_session_id | varchar(255) | |
| last_connected_at | timestamptz | |
| last_disconnected_at | timestamptz | |
| is_active | boolean | |
| sync_history | boolean | whether to ingest message history on connect |
| history_days | integer | null = no limit |
| idle_disconnect_minutes | integer | 0 = never auto-disconnect |
| auto_download_media | boolean | |
| ai_parsing_enabled | boolean | account-level default for trading classification; **default `False`** (opt-in, flipped from `True` in migration `0014`) |
| connection_unhealthy | boolean | set by the worker when it detects a degraded session that reconnecting can't fix (repeated Signal-protocol decrypt failures or post-connect handshake timeouts) — see §17.2. **Plumbing only as of migration `0018`/`0019`: no detection call site currently sets this true.** The original detection mechanism caused a production incident and was reverted; only the inert DB/API/UI plumbing remains, ready for a safe reimplementation |
| connection_unhealthy_reason | text | human-readable reason, blank when `connection_unhealthy=False` |
| connection_unhealthy_since | timestamptz nullable | when it was flagged; `null` when healthy |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### 6.2 whatsapp_contact

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| account_id | FK → whatsapp_account | |
| wa_contact_id | varchar(255) | **always** a phone JID (`phone@s.whatsapp.net`) or group JID (`id@g.us`) — never a LID |
| lid_jid | varchar(255) nullable | LID alias when the contact uses WhatsApp privacy mode (e.g. `200506303578143@lid`) |
| username | varchar(35) nullable | WhatsApp username alias (rolling out from 2026-07-07). Same alias treatment as `lid_jid` — never becomes the canonical identifier |
| phone_number | varchar(50) | digits only, derived from wa_contact_id |
| display_name | varchar(255) | user-editable label; seeded from push_name on first create only |
| push_name | varchar(255) | the name set on the contact's WhatsApp profile |
| is_business | boolean | |
| category | varchar(20) | `supplier` / `customer` / `both` / blank (uncategorized). User-assigned tag, editable inline on the Contacts page or as a quick action right on a trading inquiry card. Drives the supplier picker on the Buying Inquiries page (§16) and is fed back into AI classification as context (§12) |
| raw_payload | jsonb | |
| created_at | timestamptz | |
| updated_at | timestamptz | |

**Constraints:**
- `UNIQUE(account_id, wa_contact_id)`
- `UNIQUE(account_id, lid_jid)` where `lid_jid IS NOT NULL AND lid_jid != ''`
- `UNIQUE(account_id, username)` where `username IS NOT NULL AND username != ''`

**Design rule:** `wa_contact_id` is always canonical (phone/group). LIDs are stored as aliases only. The worker must resolve any LID to a phone JID before forwarding a message. If it cannot, it drops the message with reason `unresolvable_lid`.

### 6.3 whatsapp_chat

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| account_id | FK → whatsapp_account | |
| wa_chat_id | varchar(255) | phone JID for 1:1, group JID for groups |
| chat_type | varchar(50) | `individual` / `group` |
| name | varchar(255) | group name or empty for individuals |
| contact_id | FK → whatsapp_contact nullable | set for individual chats only |
| last_message_at | timestamptz | monotonically advancing — never rolled back by history replay |
| unread_count | integer | |
| is_archived | boolean | |
| ai_parsing | boolean nullable | tri-state override: `True`/`False` force on/off for this chat, `NULL` = inherit `whatsapp_account.ai_parsing_enabled` |
| raw_payload | jsonb | |

**Constraints:** `UNIQUE(account_id, wa_chat_id)`

### 6.3.1 whatsapp_group / whatsapp_group_participant

Introduced to give groups and communities first-class identity, separate from `whatsapp_chat` (which still holds the message-list row for a group chat).

| Column (whatsapp_group) | Type | Notes |
|---|---|---|
| id | bigint PK | |
| account_id | FK → whatsapp_account | |
| wa_group_id | varchar(255) | group JID |
| chat_id | FK → whatsapp_chat, nullable, one-to-one | links to the existing chat row |
| name | varchar(512) | |
| description | text | |
| owner_jid | varchar(255) | |
| community_id | FK → whatsapp_group (self), nullable | set when this group is a sub-group of a community |
| is_community | boolean | true when this row is the community umbrella, not a regular group |
| participant_count | integer | |
| created_at / updated_at | timestamptz | |

**Constraints:** `UNIQUE(account_id, wa_group_id)`

| Column (whatsapp_group_participant) | Type | Notes |
|---|---|---|
| id | bigint PK | |
| group_id | FK → whatsapp_group | |
| wa_jid | varchar(255) | |
| contact_id | FK → whatsapp_contact, nullable | |
| role | varchar(20) | `member` / `admin` / `superadmin` |
| is_active | boolean | |
| joined_at / updated_at | timestamptz | |

**Constraints:** `UNIQUE(group_id, wa_jid)`

A data migration (`0011_backfill_groups_from_chats`) seeded placeholder `whatsapp_group` rows from existing `whatsapp_chat` rows where `chat_type='group'`; these are enriched with real metadata the next time the session connects and Baileys' `groupFetchAllParticipating()` fires.

### 6.4 whatsapp_message

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| account_id | FK → whatsapp_account | |
| chat_id | FK → whatsapp_chat | |
| contact_id | FK → whatsapp_contact nullable | |
| provider_message_id | varchar(255) | Baileys message key ID |
| sender_number | varchar(50) | digits only |
| direction | varchar(20) | `inbound` / `outbound` |
| message_type | varchar(50) | see §7 |
| message_text | text | |
| message_time | timestamptz | |
| has_media | boolean | |
| media_mime_type | varchar(255) | |
| media_file_name | varchar(255) | |
| media_url | text | |
| raw_payload | jsonb | full Baileys message object |

**Constraints:** `UNIQUE(account_id, provider_message_id)`

### 6.5 message_embedding

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| message_id | FK → whatsapp_message | |
| embedding | vector(512) | voyage-3-lite embedding |
| embedding_model | varchar(255) | model identifier |
| metadata | jsonb | |
| created_at | timestamptz | |

Index: `USING ivfflat (embedding vector_cosine_ops)`

### 6.5.1 product_embedding

Mirrors `message_embedding` exactly, but one row per `Product` instead of per message. Added ahead of an anticipated catalog-size need, not because the current catalog (~30 active products) requires it — see "Product retrieval" note in §12.

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| product_id | FK → trading_product, one-to-one | |
| embedding | vector(512) | voyage-3-lite embedding of `{brand} {name}` only — **not** aliases, as of Phase 20; each alias gets its own separate embedding instead (§6.8.1) |
| embedding_model | varchar(255) | model identifier |
| metadata | jsonb | |
| created_at / updated_at | timestamptz | |

Index: `USING ivfflat (embedding vector_cosine_ops)`

Generated in the background (`apps/message_intelligence/services/embedding_service.py`: `embed_product` / `embed_products_batch`), fire-and-forget, triggered from `ProductViewSet.perform_create`/`perform_update`/`bulk_create` in `apps/trading/views.py` — same non-blocking pattern as live message embedding, a provider hiccup here never blocks a product save. **Not currently read at classification time** — `find_similar_products()` (multi-vector cosine-distance top-K lookup across this table and `product_alias_embedding`, §6.8.1) is used by the trading dashboard's "Auto" match-fix search (§20 Phase 17) but isn't wired into the classification prompt itself; the live catalog is still small enough to send as plain text in full (`product_cache.py`). See §12.

### 6.6 sync_log

Audit trail for every ingestion event.

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| account_id | FK → whatsapp_account | |
| event_type | varchar(50) | `message_ingest`, `history_sync`, `session_status`, etc. |
| status | varchar(20) | `success`, `warning`, `error` |
| message | text | human-readable detail |
| metadata | jsonb | varies by event_type (see §14) |
| created_at | timestamptz | |

### 6.7 whatsapp_dropped_message

Captures every message the worker decided not to forward to Django, with its reason. Used to debug silent message loss.

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| account_id | FK → whatsapp_account | |
| msg_id | varchar(255) nullable | Baileys message key ID |
| raw_jid | varchar(255) nullable | `msg.key.remoteJid` |
| from_me | boolean nullable | |
| has_message | boolean | whether `msg.message` was non-null |
| reason | varchar(100) | see §9 |
| raw_key | jsonb | `msg.key` + `_msgKeys` (field names present in `msg.message`) |
| created_at | timestamptz | |
| resolved_at | timestamptz nullable | set when a later message with the same `msg_id` was ingested successfully — i.e. Baileys' retry request eventually got the sender to resend and decryption succeeded. Distinguishes self-healed drops (mostly `no_message_content`) from permanent loss. |

Two new `reason` values as of the silent-message-loss audit (Phase 14, §12): `history_build_error` (a `_buildPayload` throw during history-sync/redelivered-live processing, previously only a raw `logger.warn` — see §12) and `batch_persist_failed` (a message the worker successfully delivered that then failed to persist in Django — `raw_key` holds the **full original payload**, not just `msg.key`, so the content is recoverable even though the `WhatsAppMessage` row was never created).

### 6.7.1 whatsapp_worker_alert

Structured, queryable, UI-visible record of a worker-side failure that would otherwise only exist as an unstructured line in a raw log file — the root-cause fix for the class of bug where something goes wrong deep in the pipeline (often inside Baileys itself, before `whatsapp_dropped_message` can even see it) and the only trace is a raw text file nobody is watching. See §12 for the full mechanism and §16 for the Worker Alerts screen.

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| account_id | FK → whatsapp_account, nullable | null for failures with no session context (e.g. a process-level uncaught exception) |
| alert_type | varchar(30) | `decrypt_failure` / `handshake_timeout` / `history_build_failed` / `batch_persist_failed` / `batch_partial_failure` / `drop_report_failed` / `uncaught_exception` / `other` |
| severity | varchar(10) | `warning` / `error` |
| message | text | human-readable summary |
| context | jsonb nullable | raw details — the offending log line's fields, a stack trace, batch counts, etc. |
| created_at | timestamptz | |
| acknowledged_at | timestamptz nullable | |
| acknowledged_by | FK → auth user, nullable | |

Every occurrence is logged immediately — this is **not** a threshold/count mechanism like `whatsapp_account.connection_unhealthy` (which only flags a session as needing re-linking after repeated failures). This table is the audit trail; `connection_unhealthy` is a derived, session-level escalation built on top of the same underlying events (§17.2).

**Bug found and fixed (2026-07-14):** `WorkerAlertSerializer` declared `account_name = serializers.SerializerMethodField()` but was missing the `get_account_name` method that field requires — every request to `GET /api/worker-alerts/` that actually had rows to serialize (i.e. basically always) crashed with a 500, silently swallowed by the frontend's bare `catch {}`. The nav badge (a separate, simpler `.count()` aggregate query, no serialization involved) was unaffected, which is exactly why it could show a real unacknowledged count (54) while the table underneath showed nothing. Predates this session's other work — never caught earlier because verification up to that point only ever queried the DB directly (`manage.py shell`), never through the actual list endpoint. Fixed by adding the missing method.

### 6.7.2 whatsapp_stuck_receipt

WhatsApp's retry-receipt protocol asks the sender to resend a specific message when the recipient device couldn't decrypt/receive it. One specific case — a self-sync message to the account's own linked devices with an empty message ID on the receipt's base key — makes Baileys crash internally every time it tries to fulfill the resend (`TypeError` in its own `relayMessage`, confirmed by reading Baileys' source directly, not guessed). Each attempt first calls `assertSessions(..., force=true)`, an **unconditional real network round-trip to WhatsApp** to re-fetch session/prekey data, before the crash — so every repeat of the same doomed request was both crashing *and* generating a wasted live request to WhatsApp's servers. Confirmed live: 10 occurrences in 10 seconds during one burst, each preceded by its own `assertSessions` call.

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| account_id | FK → whatsapp_account, nullable | |
| remote_jid | varchar(255) | frequently absent on this specific self-sync receipt shape (Baileys derives it from `attrs.recipient`, which isn't always set) — falls back to `participant` when so, both in the worker's own skip-list key and in what gets persisted here, so the two stay consistent |
| participant | varchar(255) blank | |
| message_id | varchar(255) | the specific retry-request id that keeps failing |
| from_me | boolean | |
| context | jsonb nullable | raw `{key, ids, trace}` from the originating Baileys log line |
| occurrence_count | integer | bumped (not duplicated) on every repeat of the same `(account, remote_jid, message_id)` |
| first_seen_at / last_seen_at | timestamptz | |
| resolved_at | timestamptz nullable | manual review marker only — does not affect the worker's skip-list, which is keyed off the row's mere existence |
| resolved_by | FK → auth user, nullable | |

**Constraints:** `UNIQUE(account_id, remote_jid, message_id)`

**The fix, in two parts** — deliberately the safe half only; see the postmortem note below. (1) The worker's pino `hooks.logMethod` inspection (§12, §17.2) already fires on every Baileys log line; a new check for the exact `'error in sending message again'` message extracts `{key, ids}` and both records/upserts this row **and** adds the `(remoteJid-or-participant, id)` key to an in-memory per-session `Set`. (2) The worker's `getMessage` callback — previously an unconditional stub `async () => ({ conversation: '' })` for every key regardless of what was asked — now checks that `Set` first and returns `null` for anything already recorded, which is Baileys' own documented "message not available" path (logs at `debug`, calls `relayMessage` for nothing) instead of attempting and failing the resend again. **What this does not do**: prevent `assertSessions` on the *first* occurrence of any new stuck message (that crash is what tells the system about it in the first place, and it's already safely caught by Baileys' own try/catch — nothing new breaks), or stop WhatsApp's servers from continuing to ask (that's the server's own retry protocol, outside this system's control). Deliberately **not** implemented: removing/replacing Baileys' internal `ws.on('CB:receipt', ...)` listener to skip `assertSessions` itself too — reaching that far *before* the crash would require exactly the kind of internal-event-wiring surgery that caused the §17.2 production incident, and was ruled out for the same reason.

Verified in isolation (fed the exact real-world captured log shape into a mocked `SessionManager`, confirmed the skip-list populates with the right fallback key and `getMessage` returns `null` only for that key) before touching live code, then verified live end-to-end (added a real alias/message through the actual API, confirmed the embedding/skip-list path fires; confirmed cascade delete cleans up cleanly).

New Stuck Receipts screen (§16, `/stuck-receipts`) plus an unresolved-count badge on the **Logs** dropdown, same pattern as Worker Alerts.

### 6.7.3 whatsapp_unresolved_message

Durable preservation for a message with genuine user content whose chat-level LID could not be resolved to a phone JID at ingestion time (2026-07-21, see §13 and `docs/Contact Message Loss — LID Resolution Fix Proposal.md`). Identity resolution and message preservation are treated as separate concerns from this point on: a resolution failure no longer means the message is discarded, only that it's parked pending resolution. Distinct from `whatsapp_dropped_message` (§6.7), which remains the record for genuinely non-user-message events (protocol frames, status broadcasts, pure key-distribution envelopes) — a row here always has real content.

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| account_id | FK → whatsapp_account, nullable | |
| provider_message_id | varchar(255) nullable | nullable only when WhatsApp genuinely supplied no id |
| raw_jid | varchar(255) | original `msg.key.remoteJid` |
| participant_jid | varchar(255) blank | |
| lid_jid | varchar(255) blank, indexed | the LID that failed to resolve — indexed for the recovery lookup (`account, lid_jid, resolution_status`) |
| from_me | boolean | |
| direction | varchar(10) blank | `inbound`/`outbound` when determinable |
| message_type / message_text / has_media | | full content, not just the key |
| message_time | timestamptz nullable | original message timestamp, preserved through recovery so history-vs-live age rules stay correct |
| push_name | varchar(255) blank | |
| is_history | boolean | true for messages arriving via history sync / a reconnect `prepend` batch — routes recovery through the same live-vs-history split normal ingestion uses (no live AI classification of a resurfaced historical message) |
| reason | varchar(50) | e.g. `unresolvable_lid` |
| raw_key / raw_payload | jsonb nullable | `raw_payload` holds the full ingest-ready payload (same shape `message-ingest` expects, minus `chat_id`) — required for recovery, not optional |
| resolution_status | varchar(10) | `pending` / `resolved` / `failed`, indexed |
| resolved_contact_id / resolved_message_id | FK, nullable | set only once a real `WhatsAppMessage` actually exists — never marked resolved without one |
| resolution_error | text blank | |
| created_at / updated_at / resolved_at | timestamptz | |

**Constraints:** `UNIQUE(account_id, provider_message_id)` where `provider_message_id` is not null (partial index).

**Resolution chain that feeds this table** (`_buildPayload`, `session-manager.js`) — see §13 for the full priority order. Only reached when sources 1-3 all miss: (1) live `senderPn`/`participantPn`, (2) in-memory `session.lidToPhone`, (3) a persisted single-LID lookup against Django (`GET /api/internal/whatsapp/lid-mapping/:account_id/`, §10). Scope is deliberately limited to the chat-level LID case (an individual chat whose `remoteJid` itself is a LID) — an unresolvable LID *group participant* (the group itself is already known) still hard-drops via `whatsapp_dropped_message` unchanged, since that message's chat identity was never in question.

**Preservation endpoint:** `POST /api/internal/whatsapp/unresolved-message/` (§10) — `IngestionService.preserve_unresolved_message()`, idempotent via `update_or_create` on `(account, provider_message_id)` so a worker retry of the same POST updates the same row instead of duplicating it. Deliberately has **no** local-file fallback on failure (unlike `dropped-message`/`worker-alert`/`stuck-receipt`) — a persistence failure here must be explicit (`WorkerAlert(unresolved_message_failed)`), never silently treated as "probably fine," since a second silent source of truth for the core message path is exactly the failure mode this exists to eliminate.

**Automatic recovery:** `IngestionService.recover_unresolved_for_lid(account, lid_jid, phone_jid)`, triggered from `internal_contacts_update` (backgrounded in a daemon thread) whenever a contact's `lid_jid` becomes newly known — covers the mapping arriving via `contacts.set`/`contacts.upsert` from the worker. Reprocesses every `pending` row for that `(account, lid_jid)` through the *same* `_upsert_contact`/`_upsert_chat`/`_insert_message` path normal ingestion uses (no separate business logic), then routes post-processing through the normal live-vs-history split (`_process_message_in_background` for live, `_embed_in_background` only for history — never live-classifying a resurfaced historical message).

**Duplicate-safe:** before reprocessing a row, recovery checks for an existing `WhatsAppMessage` by `(account, provider_message_id)` — if Baileys' own retry already delivered and ingested the message normally before recovery ran, the row is linked to that existing message and marked resolved instead of creating a duplicate. A per-row failure records `resolution_error` and leaves `resolution_status` at `pending` (retryable on the next successful mapping event) rather than being marked resolved without a real `WhatsAppMessage` behind it.

**Observability:** `UnresolvedMessageViewSet` (read-only, §11) at `/unresolved-messages/` + `/unresolved-messages/counts/`; frontend page at `/unresolved-messages` (§16), plus a pending-count badge on the **Logs** dropdown, same pattern as Worker Alerts/Stuck Receipts.

**Tests:** `apps/whatsapp_bridge/tests.py` (preservation idempotency incl. null-provider-id, recovery + duplicate-safety, recovery failure handling, history-vs-live post-processing, endpoint auth/validation, contacts-update recovery trigger) and `whatsapp-worker/test/session-manager.test.js` (all three resolution sources, preserve-on-total-miss, lookup-failure and persistence-failure handling, history-sync preservation, `node --test` / `npm test` in `whatsapp-worker/`).

### 6.8 trading_product

Product master used for AI matching (aliases) and inventory tracking. No LIKE/fuzzy queries against aliases — matching is entirely AI-driven at classification time. Only `is_active=True AND qty > 0` rows are sent to the AI as the product master block (`product_cache.get_product_prompt_block()`) — a product with zero stock is never offered as a classification match, `exact` or `near`, even if it's otherwise a perfect spec match. Product Master screen shows a per-product Margin column, a filter-aware Total PNL badge (Σ margin × qty), a Product Embedding column and an Alias Embeddings column (§6.8.1, §20 Phase 20), an aggregate embedding-coverage badge with a one-click Backfill action, and supports inline click-to-edit on Qty/Cost/Sale directly in the table. The Add/Edit modal (§16) was rebuilt in Phase 20 into a proper two-column card-sectioned form with live alias chip management, replacing the old single free-text "Advanced" textarea.

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| name | varchar(255) | |
| brand | varchar(100) | |
| category | varchar(100) | |
| sku | varchar(100) | |
| is_active | boolean | soft-delete flag |
| qty | integer | inventory quantity |
| cost_price | decimal(12,2) nullable | |
| sale_price | decimal(12,2) nullable | |
| currency | varchar(10) | default `USD` |
| created_at / updated_at | timestamptz | |

**`aliases` was removed from this table in Phase 20** (migrations `0015`→`0017`) — see §6.8.1. `ProductSerializer.aliases` is still a read-only convenience field (list of alias strings), now computed from the related `ProductAlias` rows instead of a JSON column.

### 6.8.1 trading_product_alias / product_alias_embedding

Split out of `trading_product.aliases` (a plain JSON list, no per-item structure) into a first-class model so each alias can carry its **own** embedding — the actual motivation, not just normalization. A single blended `{brand} {name} {aliases}` vector per product (§6.5.1's original shape) dilutes every distinct phrasing into one average; multi-vector retrieval (below) compares a query against a product's own name **and** every one of its aliases independently, so a customer's exact phrasing can win a match even when it's nowhere near the product's canonical name.

| Column (trading_product_alias) | Type | Notes |
|---|---|---|
| id | bigint PK | |
| product_id | FK → trading_product | `related_name='alias_set'` (not `aliases` — that name was still in use by the JSONField at the point this model was added, and never renamed back afterward) |
| alias | varchar(255) | e.g. `"17PM 256"`, `"SKU-4421"` |
| created_at | timestamptz | |

**Constraints:** `UNIQUE(product_id, alias)`

| Column (product_alias_embedding) | Type | Notes |
|---|---|---|
| id | bigint PK | |
| alias_id | FK → trading_product_alias, one-to-one | |
| embedding | vector(512) | voyage-3-lite embedding of the alias string **alone** — deliberately no brand/name mixed in, so the vector represents just that one phrasing |
| embedding_model | varchar(255) | |
| metadata | jsonb | |
| created_at / updated_at | timestamptz | |

Both embed in the background (fire-and-forget, same pattern as §6.5.1) from exactly two trigger points, and nowhere else: `POST /products/:id/aliases/` (one alias) and `POST /products/bulk-create/` (one batch call for every alias created across the whole import). Deleting an alias (or its parent product) cascades to its embedding automatically. The one-time data migration that moved existing JSON aliases into this table (`0016_migrate_aliases_json_to_rows`) does **not** trigger embedding — a non-issue at the time it ran (every product's `aliases` list was already empty by then) but a latent gap if it's ever re-run somewhere with real data; the embedding-status/backfill mechanism below is the general-purpose catch for exactly this.

`find_similar_products(query, top_k)` (`embedding_service.py`) now does the actual multi-vector merge: queries `ProductEmbedding` and `ProductAliasEmbedding` independently, keeps only the single best (lowest cosine-distance) hit **per product** regardless of which table it came from, then ranks and returns the top-K. Verified with crafted test vectors: a product whose own name embedding was deliberately far from the query still ranked first because one of its aliases was a near-exact match — confirming the dedup-by-product logic picks the right vector, not just the first one found.

**Embedding visibility** — a background embed failing (provider rate-limit, etc.) used to be entirely invisible: `_embed_alias_in_background`/`_embed_product_in_background` only log a console `warning`, nothing persisted. Found in practice: two aliases added through the real UI came back with no embedding, and re-running the same embed call directly worked immediately — confirming a transient provider hiccup, not a code bug, but with zero durable trace it would otherwise have sat broken forever unnoticed. Fixed not by adding a failure-log table, but by making the "missing" state itself the durable, actionable signal:
- `GET /products/embedding-status/` — `{products: {total, embedded, missing}, aliases: {total, embedded, missing}}`.
- `POST /products/backfill-embeddings/` — synchronously (not fire-and-forget — this is a deliberate, waited-for user action) re-embeds every active product/alias currently missing one and returns real counts, not just "queued."
- Products screen shows an "Embeddings: X/Y" badge (turns amber when anything's missing) and a "Backfill (N)" button that only appears when there's a gap, plus the per-row Product Embedding / Alias Embeddings columns mentioned above for pinpointing exactly which row is affected.

### 6.8.2 trading_product_attribute

Hot-addable key/value detail on a `Product` — e.g. `Color=Silver`, `Region=USA` — for anything worth recording that doesn't warrant its own column. One row per key so keys can be added, renamed, or removed per product with no schema change and no code deploy.

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| product_id | FK → trading_product | `related_name='attribute_set'` |
| key | varchar(100) | |
| value | varchar(500) | |
| created_at / updated_at | timestamptz | |

**Constraints:** `UNIQUE(product_id, key)` (case-sensitive at the DB level; the API layer additionally rejects a case-insensitive duplicate on create).

CRUD: `GET`/`POST /products/:id/attributes/` (list/add), `PATCH`/`DELETE /products/:id/attributes/:attribute_id/` (rename key, edit value, or remove). Surfaced on the Products screen as an editable key/value section in the Add/Edit modal, plus an attribute-count column in the product list. Not embedded and not sent to the AI product-master block — purely structured display data, independent of the matching/embedding pipeline (§6.8.1, §15).

### 6.8.3 Product naming & SKU-completion standard

Established while adding the iPad Air 7 (M3) and iPad Air 8 (M4) catalog entries — the convention every new SKU variant should follow so catalog entries stay consistent and machine-parseable (the `Region`/`Flag`/`Storage`/`Color` attribute backfill in §6.8.2 depends on the name following this token order).

**Name token order:** `<Product Line> <Generation> <Screen size> <Chip> <Storage> <Color> [<Region>]`
Example: `iPad Air 8 11 inch M4 128GB Starlight`, `iPhone 17 Pro 256GB Orange Hong Kong`. Region is a trailing word/phrase and is omitted from the name only when every existing variant of that exact SKU family already shares one implied region (see "Region inference" below) — new families should still include it explicitly.

**Required attributes** (`trading_product_attribute`, §6.8.2) for every SKU variant:
- `Color` — the color word from the name, Title Case (`Starlight`, `Space Gray`).
- `Storage` — digits only, no `GB` suffix (`128`, not `128GB`); parsed from either an `NNNGB` token or an `N/NNN` RAM/storage combo token (e.g. `8/256` → `Storage=256`).
- `Region` — full region name (`USA`, `Hong Kong`), never the bare abbreviation.
- `Flag` — the region's flag emoji (🇺🇸 `USA`, 🇦🇪 `UAE`, 🇭🇰 `Hong Kong`, 🇯🇵 `Japan`).

**Required aliases** (`trading_product_alias`, §6.8.1) for every SKU variant — alternate phrasings a customer might type instead of the full canonical name:
- A screen-size alternate (e.g. `11 inch`) and a quote-mark variant (e.g. `Air 11"`) when the name spells the size out fully.
- A generation shorthand specific to that product line/generation (e.g. `Air 7` for the M3 line, `Air 8` for the M4 line) — this one **does not carry over** between generations, unlike the rest.
- The region's flag emoji, duplicated as its own alias (not just an attribute) — a bare flag character is a real, if minimal, thing a customer might paste into a search.

**Region inference:** when a new variant's name omits the region (as with the iPad Air 8 batch), the region is inferred from the only other established variant(s) of that exact SKU family already in the catalog, and stated as an explicit assumption rather than silently guessed — flag it to the user for confirmation if a family could plausibly span more than one region.

**Cloning a color variant:** when asked for "N more like this, just a different color," copy every field verbatim (brand, category, sku, qty, cost_price, sale_price, currency) except the color word in the name and the `Color` attribute value — including price/stock, which are treated as SKU-family-level, not color-specific, unless told otherwise.

### 6.9 trading_message_classification

One row per classified `WhatsAppMessage`. Created by the AI classification service after every successful call.

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| message_id | FK → whatsapp_message, one-to-one | |
| tags | jsonb (list) | one or more of `wtb`, `wts`, `price_inquiry`, `stock_inquiry`, `negotiation`, `deal_confirmation`, `greeting`, `joke`, `spam`, `other` |
| products | jsonb (list) | `[{product_id, match_type, canonical_name, quantity, price, currency}]` snapshot at classification time. `match_type` is `"exact"` (all of model/storage/color/region matched a catalog entry), `"near"` (product_id references the closest available entry, but at least one attribute — including model tier suffix like "Pro" vs "Pro Max" — differs from what was requested), or `null` (no confident match; `product_id` is also null in that case). Every `"exact"` claim is re-checked server-side against the AI's own `canonical_name` before saving — see "Backend self-consistency check" in §12 |
| is_inquiry | boolean | true only for a genuine buy/sell opportunity |
| inquiry_type | varchar(10) | `buy` / `sell` / `both` |
| ai_summary | text | one-sentence AI summary |
| dedup_key | varchar(512) | AI-generated, format `{buy|sell}:{product-slug}:{qty-bucket}:{contact_id}` |
| suggested_contact_category | varchar(20) | AI's suggested update to the sender's `whatsapp_contact.category` (`supplier`/`customer`/`both`), blank if it found no reason to suggest a change. See §12 |
| raw_response | jsonb nullable | full AI response for debugging |
| classified_at | timestamptz | |

### 6.10 trading_inquiry / trading_inquiry_message

An `Inquiry` represents a business opportunity, not a single message — multiple messages (e.g. the same offer re-sent to several groups) link to the same inquiry via `InquiryMessage`.

| Column (trading_inquiry) | Type | Notes |
|---|---|---|
| id | bigint PK | |
| account_id | FK → whatsapp_account | |
| contact_id | FK → whatsapp_contact, nullable | |
| inquiry_type | varchar(10) | `buy` / `sell` |
| status | varchar(20) | see below — expanded past the original 3-state plan |
| products | jsonb (list) | snapshot, updated as follow-up messages add detail |
| summary | text | |
| remarks | text | operator notes — also holds the reason text entered when status is set to `incorrect_match` |
| suggested_contact_category | varchar(20) | snapshot of `MessageClassification.suggested_contact_category` at creation, and re-synced whenever a follow-up message links to this inquiry. Pre-fills (not auto-applies) the category dropdown on the inquiry card |
| classification_rating | smallint | manual 1–5 human rating of how well the AI classified/matched *this* inquiry (1 = worst, 5 = exact) — defaults to `5` so a reviewer only has to touch the ones that are actually wrong, never has to confirm every single inquiry. Editable via 5 small buttons in the card footer (§16, §20 Phase 17); no aggregate reporting view yet (§20 Phase 17) |
| dedup_key | varchar(512), indexed | drives cross-group deduplication |
| source_type | varchar(20) | `direct` / `group` / `community` |
| first_seen_at | timestamptz | timestamp of the originating message; never changes on follow-ups |
| closed_at | timestamptz nullable | set when status moves to a terminal state — powers response/conversion time analytics |
| created_at / updated_at | timestamptz | |

**Status values (as implemented — expanded three times past the original plan):**
`open`, `quoted_waiting`, `no_response`, `price_high`, `no_stock`, `not_dealing`, `irrelevant`, `closed`, `deal_done`, `incorrect_match` (selecting this in the UI opens an inline text prompt for the reason, saved into `remarks`)

| Column (trading_inquiry_message) | Type | Notes |
|---|---|---|
| id | bigint PK | |
| inquiry_id | FK → trading_inquiry | |
| message_id | FK → whatsapp_message | |
| added_at | timestamptz | |

**Constraints:** `UNIQUE(inquiry_id, message_id)`

### 6.11 trading_prompt_config

Operator-editable overrides for the four AI prompts used by the trading pipeline. Falls back to the built-in default body when no row exists for a key. All four show up automatically on the AI Instructions screen (§16) — the list is driven by a dict in `PromptConfigViewSet`, not hardcoded per-screen, so a new key needs no frontend change to appear there.

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| key | varchar(100), unique | `product_extraction`, `inquiry_classification`, `inventory_update`, or `price_list_format` |
| label | varchar(200) | |
| body | text | the prompt text sent to the AI |
| updated_at | timestamptz | |

**⚠ Editor risk, confirmed by a real incident (2026-07-11):** saving a prompt here **replaces the entire body** — there is no "append" or "merge" option. A DB row was saved for `inquiry_classification` containing *only* a block of additional product-matching safety rules, with none of the base prompt underneath it (no `is_inquiry`/`tags`/`products` schema instructions, no `{product_block}` placeholder). Every classification for hours silently returned `is_inquiry: false` for genuine WTB/WTS messages — no error anywhere, since the AI just free-formed a different JSON shape on every call and `_parse_response`'s `.get(..., default)` calls quietly filled in defaults for every missing field instead of failing loudly. Caught only because inquiries visibly stopped appearing despite AI Parsing Log showing messages were being sent. **When adding rules via this screen, paste them into a full copy of the current prompt, never as a standalone replacement — always sanity-check the saved body still contains the JSON schema block at the end before trusting it.** Fixed by deleting the broken override (falls back to the Python default) and merging the valuable new rules — hard SIM-type exclusions, broader forbidden-tier-inference coverage, a rule against inferring region from stock/product_id existence — directly into `INQUIRY_CLASSIFICATION_DEFAULT` in `prompt_config.py`, so they survive future resets instead of living only in an editable DB row.

### 6.12 trading_agent_call_log

Full audit trail of every AI call made by the trading pipeline (classification and product extraction), including token counts and errors — surfaced in the AI Instructions / diagnostics screen.

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| purpose | varchar(50) | `classification` / `product_extraction` |
| provider | varchar(50) | |
| model | varchar(100) | |
| messages | jsonb | full messages array sent to the AI |
| response | text | |
| input_tokens / output_tokens | integer | |
| duration_ms | integer | |
| success | boolean | |
| error | text | |
| wa_message_id | bigint nullable, indexed | optional link back to the triggering message |
| created_at | timestamptz, indexed | |

### 6.13 trading_ai_parsing_log

One row per **live** message evaluated for AI classification eligibility — both the ones actually sent to the AI and the ones skipped, with why. Written by `_log_ai_parsing_and_classify` in `ingestion_service.py`, in the same background thread as embedding, for every created live message (history-sync batch messages are excluded — they'd all read as `too_old` and just add noise). Surfaced in the AI Parsing Log screen (§16).

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| message_id | FK → whatsapp_message, unique | one row per message; re-processing updates in place |
| account_id | FK → whatsapp_account | |
| chat_id | FK → whatsapp_chat, nullable | |
| status | varchar(10) | `sent` or `skipped` |
| skip_reason | varchar(30) | blank when `status=sent`; else one of `no_text`, `outbound`, `too_old`, `chat_disabled`, `account_disabled`, `duplicate_broadcast` (§12) |
| message_preview | varchar(200) | first 200 chars of `message_text` |
| created_at | timestamptz, indexed | |

### 6.14 trading_buying_inquiry / trading_supplier_quote

A manually-created "I need to buy X" request, separate from the AI-detected `Inquiry` model — created by the user on the Buying Inquiries screen (§16) and shopped around to a list of supplier contacts rather than tied to any inbound message.

| Column (trading_buying_inquiry) | Type | Notes |
|---|---|---|
| id | bigint PK | |
| account_id | FK → whatsapp_account | |
| product_name | varchar(255) | free text |
| quantity | varchar(100) | free text, e.g. "50 units" |
| notes | text | |
| status | varchar(10) | `open` / `closed` |
| created_at / updated_at | timestamptz | |

On creation, one `SupplierQuote` row is auto-generated for every contact currently tagged `supplier` or `both` on that account (`whatsapp_contact.category`); more can be added/removed afterward via the picker.

| Column (trading_supplier_quote) | Type | Notes |
|---|---|---|
| id | bigint PK | |
| buying_inquiry_id | FK → trading_buying_inquiry | |
| supplier_id | FK → whatsapp_contact | |
| status | varchar(10) | `not_asked` / `asked` / `quoted` / `declined` |
| asked_at | timestamptz nullable | set when "Ask Price" is clicked (prefills and opens the WhatsApp deep link; does not auto-send) |
| quoted_price | decimal(12,2) nullable | manually logged after the supplier replies |
| quoted_currency | varchar(10) | default `USD` |
| quote_note | varchar(255) | free-text feedback, e.g. "10 units available" |
| created_at / updated_at | timestamptz | |

**Constraints:** `UNIQUE(buying_inquiry_id, supplier_id)`

### 6.15 trading_formatted_price_list

Singleton table (always exactly one row, `pk=1`) holding the AI-formatted price list text, regenerated on demand from the current in-stock (`qty > 0`), priced, active catalog via the `price_list_format` prompt (§6.11). This exact text — not an ad hoc client-built string — is what the Trading Dashboard's "Price List" button sends.

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | always `1` |
| body | text | the AI-formatted price list, WhatsApp-ready |
| generated_at | timestamptz nullable | when it was last (re)generated |
| updated_at | timestamptz | auto-updated on every save |

Regenerated only on demand (Products screen → "Price List" → Regenerate, §16) — never automatically on product/inventory changes, so it doesn't burn an AI call on every edit.

---

## 7. Message Types

```
text
image
audio
video
document
sticker
location
contact
unknown
```

---

## 8. Session Statuses

```
pending_qr
qr_generated
connected
disconnected
logged_out
error
```

`error` is set by the worker's connection watchdog (see §17.1) when a session gets stuck — either the initial handshake hangs with no `connection.update` event, or setup fails outright (corrupted auth state, version-fetch failure) before a socket even exists. Before the watchdog existed, both of these left the account silently stuck in `pending_qr`/`qr_generated` forever with no error ever surfacing; now they always resolve to `error` with a human-readable `lastError` message, surfaced through `GET /sessions/:id/qr` (worker) → `GET /api/accounts/:id/qr/` (Django) → the QR modal.

---

## 9. Drop Reasons (whatsapp_dropped_message)

| Reason | When |
|---|---|
| `no_remote_jid` | `msg.key.remoteJid` is null/missing |
| `no_message_content` | `msg.message` is null/missing |
| `prepend_no_content` | history prepend message has no content |
| `status@broadcast` | WhatsApp status update — not a real message |
| `protocolMessage` | internal WA protocol signal |
| `senderKeyDistributionMessage` | pure E2E key envelope with no user content |
| `unresolvable_lid` | **group-participant LID only** (as of 2026-07-21) — the group itself is known, only the sender within it couldn't be resolved (`senderPn`/`participantPn`/cache all miss). A chat-level LID (individual chat) that can't be resolved is **no longer dropped here** — see §6.7.3, it's preserved as `whatsapp_unresolved_message` instead |
| `forward_failed` | Django returned an error on `message-ingest` |
| `build_error` | unexpected exception in `_buildPayload` (live path) |
| `history_build_error` | unexpected exception in `_buildPayload` during history-sync/redelivered-live processing — previously silent, only a raw `logger.warn`, see §12 |
| `batch_persist_failed` | Django received the message but failed to persist it — `raw_key` holds the full original payload for recovery, see §12 |
| `messageStubType:N` | WhatsApp group notification stub (member joined, left, etc.) |

`senderKeyDistributionMessage` is only dropped when the field is the **sole content** of `msg.message`. If a real message is bundled in the same envelope (combined envelope), the key distribution field is stripped and the message passes through.

> **Resolved 2026-07-21:** the chat-level `unresolvable_lid` outbound-only drop pattern documented in §17.2 "Eighth incident" (11 confirmed drops for one contact over two weeks) no longer loses content — see §6.7.3 and `docs/Contact Message Loss — LID Resolution Fix Proposal.md`. The unrelated inbound zero-trace mystery (`Silent Message Drop Investigation.md`) is untouched by this and remains open.

---

## 10. Internal API Endpoints (Worker → Django)

All require `X-Internal-Token` header.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/internal/whatsapp/session-status/` | Worker reports connect/disconnect |
| POST | `/api/internal/whatsapp/message-ingest/` | Single live message |
| POST | `/api/internal/whatsapp/message-ingest-batch/` | History sync batch |
| GET  | `/api/internal/whatsapp/account-settings/:id/` | Worker fetches account config at connect |
| GET  | `/api/internal/whatsapp/lid-mappings/:id/` | Worker seeds `lidToPhone`/`usernameToPhone` from already-known contacts on restore, so a restart doesn't start the cache cold (was causing `unresolvable_lid` drops for known senders) |
| GET  | `/api/internal/whatsapp/lid-mapping/:id/?lid_jid=...` | Single-LID lookup (§13 resolution source 3, §6.7.3) — used mid-message when `lidToPhone` misses, instead of refetching the whole mapping dict. `{found, lid_jid, phone_jid}` or `{found: false}` |
| POST | `/api/internal/whatsapp/unresolved-message/` | Preserve a message with real content whose LID couldn't be resolved (§6.7.3) — never given a local-file fallback; a failure here must surface as `WorkerAlert(unresolved_message_failed)` |
| POST | `/api/internal/whatsapp/contacts-update/` | Contact names from `contacts.set` / `contacts.upsert` — also triggers `whatsapp_unresolved_message` recovery (§6.7.3) for any LID the batch newly resolves |
| POST | `/api/internal/whatsapp/dropped-message/` | Fire-and-forget drop notification |
| POST | `/api/internal/whatsapp/worker-alert/` | Structured worker-failure report (§6.7.1) — `account` optional, so failures with no session context can still be recorded |
| POST | `/api/internal/whatsapp/stuck-receipt/` | Upserts a stuck-receipt record (§6.7.2) — first occurrence of `(account, remote_jid, message_id)` creates the row, every repeat bumps `occurrence_count`/`last_seen_at` |
| POST | `/api/internal/whatsapp/group-update/` | Group/community metadata from `groupFetchAllParticipating()` |
| POST | `/api/internal/whatsapp/group-participants-update/` | Group participant list + roles |

### message-ingest payload

```json
{
  "worker_session_id": 1,
  "provider_message_id": "3EB0...",
  "chat_id": "971503218002@s.whatsapp.net",
  "chat_type": "individual",
  "sender_number": "971503218002",
  "push_name": "Ahmed",
  "direction": "inbound",
  "message_type": "text",
  "message_text": "Is the iPhone 17 available?",
  "message_time": "2026-06-30T10:01:00Z",
  "has_media": false,
  "group_name": "",
  "raw_payload": {}
}
```

For group messages: `chat_id` is the group JID (`id@g.us`), `sender_number` is the participant's phone number (already resolved from LID if applicable).

### contacts-update payload

```json
{
  "worker_session_id": 1,
  "contacts": [
    {
      "wa_contact_id": "971503218002@s.whatsapp.net",
      "push_name": "Ahmed",
      "phone_number": "971503218002",
      "lid_jid": "200506303578143@lid"
    }
  ]
}
```

`lid_jid` is included only when Baileys exposes the mapping. Pure LID entries from `contacts.set` are **not** sent — they carry no identity the DB doesn't already have.

---

## 11. Public API Endpoints (Frontend → Django)

Session auth + CSRF, gated behind the login endpoints in §11.1.

### 11.0 Auth

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/login/` | Session login |
| POST | `/api/auth/logout/` | Session logout |
| GET  | `/api/auth/me/` | Current user (used by the router guard on every navigation) |

### 11.1 Accounts, Chats, Contacts, Groups

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/accounts/` | WhatsApp account CRUD |
| PATCH | `/api/accounts/:id/update-settings/` | Update `sync_history`, `history_days`, `idle_disconnect_minutes`, `display_name`, `ai_parsing_enabled`, `auto_download_media` |
| POST | `/api/accounts/:id/start-session/` | Start worker session |
| GET  | `/api/accounts/:id/qr/` | Poll QR code |
| POST | `/api/accounts/:id/disconnect/` | Disconnect session — thin proxy to the worker's `/sessions/:id/disconnect`. If the worker replies 404 "Session not found" (its credentials were already cleared by a WhatsApp-side logout, or the worker restarted and never restored this session) and the DB still says otherwise, this self-corrects `session_status` to `disconnected` rather than leaving stale state that makes the button permanently unusable — see the Phase 11 incident writeup |
| GET  | `/api/accounts/:id/sync-progress/` | Polled every 4s by `AccountCard.vue` while an account is connected. `{syncing, total_synced, total_processed, batch_count, has_live_messages, is_complete, connection_unhealthy, connection_unhealthy_reason}` — live since Phase 14 (§17.2); the worker now also clears `connection_unhealthy` unconditionally on every successful reconnect, not just when its own in-memory session object remembers having been unhealthy, see §17.2 |
| GET  | `/api/accounts/:id/storage/` | Storage stats |
| GET/POST | `/api/accounts/:id/backup-media/`, `/restore-messages/`, `/restore-media/` | Media/message backup & restore |
| GET  | `/api/chats/` | Chat list |
| GET  | `/api/chats/:id/messages/` | Messages in a chat |
| GET  | `/api/chats/:id/group-info/` | Group metadata + participants for a group chat |
| PATCH | `/api/chats/:id/set-ai-parsing/` | Tri-state override: `true` / `false` / `inherit` |
| POST | `/api/chats/:id/mark-read/`, `/api/chats/mark-all-read/` | Read-state management |
| GET  | `/api/contacts/` | Contact list, paginated/filterable (`account`, `type`, `category`, `search`) and sortable via `ordering` (`display_name`, `push_name`, `phone_number`, `category`, `message_count`, each with a `-` prefix for descending; unrecognized values fall back to the default rather than erroring) |
| GET  | `/api/contacts/stats/` | `{total, phone, lid, group}` counts |
| PATCH | `/api/contacts/:id/` | Update `display_name` and/or `category` (`supplier`/`customer`/`both`/blank) |
| PATCH | `/api/contacts/:id/set-ai-parsing/` | Per-contact tri-state AI parsing override |
| GET  | `/api/groups/` | Group/community list |
| GET  | `/api/groups/stats/` | Group counts |
| POST | `/api/groups/sync/` | Trigger `groupFetchAllParticipating()` refresh |
| PATCH | `/api/groups/:id/set-ai-parsing/` | Per-group tri-state AI parsing override |
| GET  | `/api/activity/` | Sync log entries |
| GET  | `/api/dropped-messages/` | Dropped message log, filterable by `account`/`reason`; each row includes `resolved_at` if it later self-healed |
| POST | `/api/dropped-messages/clear-all/` | Clear drop log |
| GET  | `/api/worker-alerts/` | Worker alert log (§6.7.1), filterable by `account`/`alert_type`/`acknowledged` (`true`/`false`/omit for all) |
| GET  | `/api/worker-alerts/unacknowledged-count/` | `{count}` — polled every 30s by the nav bar badge (§16) |
| POST | `/api/worker-alerts/:id/acknowledge/` | Mark one alert acknowledged |
| POST | `/api/worker-alerts/acknowledge-all/` | Mark all (optionally filtered by `account`) acknowledged |
| GET  | `/api/stuck-receipts/` | Stuck receipt log (§6.7.2), filterable by `account`/`resolved` (`true`/`false`/omit for all) |
| GET  | `/api/stuck-receipts/unresolved-count/` | `{count}` — polled every 30s by the nav bar badge (§16) |
| POST | `/api/stuck-receipts/:id/resolve/` | Mark one row resolved (review marker only — doesn't affect the worker's skip-list) |
| GET  | `/api/unresolved-messages/` | Unresolved-message log (§6.7.3), read-only, filterable by `account`/`resolution_status` |
| GET  | `/api/unresolved-messages/counts/` | `{pending, resolved, failed}` — polled by the nav bar badge (§16) and the page's own summary tiles |

### 11.2 Intelligence & Providers

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/intelligence/search/` | Semantic search |
| GET  | `/api/intelligence/embedding-status/` | Embedding coverage stats |
| POST | `/api/intelligence/backfill/` | Trigger background embedding of pending messages |
| GET/POST | `/api/ai-providers/` | AI provider config |

### 11.3 Trading Intelligence

| Method | Path | Purpose |
|---|---|---|
| GET/POST/PATCH/DELETE | `/api/products/` | Product CRUD. Serialized products include `has_embedding` and `alias_embedding_status: {embedded, total}` (§6.8.1, §20 Phase 20) — the per-row source for the Products table's two embedding columns |
| POST | `/api/products/parse-text/` | AI-extract products from a pasted price list |
| POST | `/api/products/bulk-create/` | Bulk-create parsed products — also creates any attached `aliases` as real `ProductAlias` rows (§6.8.1) and batch-embeds them, deduped case-insensitively per product |
| POST | `/api/products/parse-inventory/` | AI-extract qty/cost/sale price from free text |
| POST | `/api/products/bulk-update-inventory/` | Apply parsed inventory update |
| GET  | `/api/products/:id/aliases/` | List a product's aliases (§6.8.1) |
| POST | `/api/products/:id/aliases/` | Add one alias — rejects an exact case-insensitive duplicate for the same product with a 400, otherwise queues its embedding in the background |
| DELETE | `/api/products/:id/aliases/:alias_id/` | Remove one alias (cascades to its embedding) |
| GET  | `/api/products/search-embeddings/` | `?q=` — multi-vector embedding search fallback for the trading dashboard's "Auto" match-fix button (§6.8.1, §20 Phase 17); `{results: [{product, distance}]}`, top 5, 503 if the embedding provider is unavailable |
| GET  | `/api/products/embedding-status/` | `{products: {total, embedded, missing}, aliases: {total, embedded, missing}}` (§6.8.1) |
| POST | `/api/products/backfill-embeddings/` | Synchronously re-embeds every active product/alias currently missing one; returns real counts, not just "queued" (§6.8.1) |
| GET  | `/api/products/stats/` | Per-product WTB/WTS counts. Also accepts `date_from`/`date_to` (§20 Phase 16), same defaulting behavior as `/api/inquiries/stats/` below |
| GET  | `/api/products/price-list/` | Current AI-formatted price list (§6.15), `{body, generated_at}` |
| POST | `/api/products/regenerate-price-list/` | Re-run the `price_list_format` prompt against the current in-stock catalog and persist the result |
| GET/PATCH | `/api/inquiries/` | Inquiry list/detail + status/remarks/`classification_rating` update (1–5, §6.10). Serialized inquiries include `source_message_text` — the exact original text of the first linked message, used verbatim (not re-summarized) in the Trading Dashboard card body and the "WA" reply prefill |
| POST | `/api/inquiries/:id/correct-match/` | Manually override the AI's product match for one line item — `{index, product_id}` (`products` is a plain JSONField list with no per-item id, so the frontend addresses a line by its array index); sets `match_type='exact'` and flags `manually_corrected: true` on that line. Backs the trading dashboard's "Fix"/"Auto" match-correction UI (§20 Phase 17) |
| POST | `/api/inquiries/close-stale/` | Bulk-closes every `status=open` inquiry older than `{hours}` (optionally scoped to `account`) — the dashboard's "Close inquiries older than N hrs" housekeeping sweep (§20 Phase 16). Only ever touches `open` records, never anything already actioned |
| GET  | `/api/inquiries/stats/` | Dashboard aggregates. Accepts optional `date_from`/`date_to` (`YYYY-MM-DD`, inclusive both ends) — defaults to "today" when neither is given, so the Trading Dashboard's stat chips (which never pass these) keep their original behavior unchanged. Response gained `timeline_granularity` (`hourly` for a single-day range, `daily` for anything longer) and `range: {date_from, date_to}` (§20 Phase 16) |
| GET  | `/api/inquiries/open-feed/` | Paginated live feed, `{count, results}`. Params: `status`, `account`, `type` (`buy`/`sell` — WTB/WTS are fetched as two independent paginated requests, not one combined list), `limit` (default 50, max 1000). `count` is the true total for the filter, so the frontend can detect truncation and load more instead of silently capping at `limit` |
| GET  | `/api/inquiries/classification-activity/` | Recent classification events (diagnostics). Also accepts `date_from`/`date_to` (§20 Phase 16) |
| POST | `/api/inquiries/retry-inquiries/` | Re-run classification for failed/skipped inquiries |
| POST | `/api/inquiries/backfill-classify/` | Classify recent unclassified messages (<24h old) |
| GET  | `/api/classifications/` | Read-only classification records, filterable by message |
| GET/PATCH/DELETE | `/api/prompts/` | Prompt override CRUD (4 keys, §6.11) |
| GET/PATCH | `/api/prompts/active-agent/` | Active AI agent/model config for trading |
| GET  | `/api/agent-logs/` | AI call audit log (tokens, duration, success/error) |
| GET  | `/api/ai-parsing-logs/` | Per-message sent/skipped routing log (§6.13), filterable by `account`/`status`/`skip_reason` (now includes `duplicate_broadcast`, §12) |
| GET/POST/PATCH/DELETE | `/api/buying-inquiries/` | Buying Inquiry CRUD (§6.14); create auto-populates supplier cards |
| POST | `/api/buying-inquiries/:id/add-supplier/` | Add one more supplier card to an existing buying inquiry |
| PATCH/DELETE | `/api/supplier-quotes/:id/` | Log a quote (`status`, `quoted_price`, `quoted_currency`, `quote_note`) or remove a supplier card |
| POST | `/api/supplier-quotes/:id/ask/` | Mark a supplier card `asked` with `asked_at=now()` — paired client-side with opening the prefilled WhatsApp link |

---

## 12. Message Ingestion Pipeline

```
messages.upsert (Baileys event)
  ├─ type = 'prepend'  → _forwardHistoryBatch (no media download)
  ├─ type = 'notify'   → _forwardMessage (live, with media download)
  └─ type = 'append'   → _forwardMessage (live, with media download)

messaging-history.set (Baileys event)
  └─ _forwardHistoryBatch (chunked 100 at a time)

_forwardMessage:
  1. _buildPayload
     ├─ filter: status@broadcast, messageStubType, protocolMessage
     ├─ filter: pure senderKeyDistributionMessage (combined envelopes pass through)
     ├─ resolve LID chat JID → phone JID (strict: drop 'unresolvable_lid' on failure)
     ├─ resolve group LID participant → phone JID via participantPn or lidToPhone cache (strict)
     ├─ _parseMessage → messageType, messageText, hasMedia
     └─ build Django payload
  2. djangoClient.sendMessageIngest (throws on failure)
  3. on failure → _reportDropped('forward_failed')

_forwardHistoryBatch (also carries reconnect-redelivered LIVE messages via the 'prepend' branch):
  1. _buildPayload for each message (isHistory=true, no media download)
     — on throw: _reportDropped('history_build_error') (§6.7, §9 — previously only a raw
       logger.warn with no DroppedMessage row; see the silent-message-loss audit below)
  2. djangoClient.sendMessageIngestBatch
     — inspects the response's `errors` count even on a non-throwing 200; previously any
       non-throw was treated as total success and every message in the chunk was marked
       delivered in the worker's own local log, even ones Django had just reported losing
```

Django `IngestionService`:
```
ingest_message / ingest_batch
  → _upsert_contact          (raises ValueError if wa_contact_id ends with @lid)
  → _upsert_chat             (last_message_at is monotonically advancing)
  → _insert_message          (get_or_create by provider_message_id)
  → _resolve_dropped_message (marks any earlier whatsapp_dropped_message row for this
                               msg_id as resolved_at=now — see §6.7)
  → _process_message_in_background (daemon thread, fire-and-forget; called for every
                               created live message, not just ones with text — every
                               message gets an AiParsingLog row, see below)
      1. embed_message() — only when message_text is non-empty. Wrapped in its own
         try/except: a provider failure (rate limit, timeout, network blip) is logged
         and counted, but must NOT prevent step 2 from running. Before this fix, an
         uncaught exception here propagated out of the whole background task and
         silently skipped classification for that message with zero trace anywhere —
         found affecting ~30% of live messages across dozens of chats during one
         embedding-provider rough patch, not isolated to any one chat.
      2. _log_ai_parsing_and_classify(message):
           - _classify_skip_reason(message) → None (send) or one of:
                no_text | outbound | too_old (>24h) | chat_disabled | account_disabled | duplicate_broadcast
           - AiParsingLog.objects.update_or_create(message=..., status=sent|skipped, skip_reason=...)
           - if not skipped → classify_message(message)
```

`_classify_skip_reason` replaced the old boolean `_should_classify` — same rules (chat-level tri-state override wins, else the account's `ai_parsing_enabled` default), but it now returns *why* instead of just true/false, so every routing decision is auditable via `trading_ai_parsing_log` (§6.13) instead of silently disappearing for skipped messages.

History-sync batch messages (`ingest_batch`) are still embedded but never classified or logged to `trading_ai_parsing_log` — they would all read as `too_old` and just add noise.

**Silent message-loss audit and fixes (Phase 14):** triggered by a real report ("I don't see a contact's recent messages anywhere, not even the logs") that traced to a Signal-protocol decrypt failure for that one contact — Baileys decrypts internally *before* ever emitting `messages.upsert`, so a failure there never reaches `_buildPayload`/`_reportDropped` at all; the only trace was an unstructured line in `baileys-internal.log` nobody was watching. A full audit of the ingestion pipeline for the same *category* of bug (not just that one incident) found several more. All are now fixed at the root — every occurrence in each category gets a structured `WorkerAlert` (§6.7.1) or `DroppedMessage` (§6.7) row instead of only a raw log line:

1. **Decrypt failures & handshake timeouts (live *and* history)** — `_createBaileysLogger` builds the socket's Baileys logger using pino's `hooks.logMethod`, which intercepts every log call *before* formatting/writing without touching the destination stream's contract at all. `_inspectBaileysLogArgs` matches `"failed to decrypt message"` → `alert_type=decrypt_failure`, `"unexpected error in 'init queries'"` → `handshake_timeout`, and any other error-level (≥50) Baileys log against neither pattern → `alert_type=other` (a catch-all, so a genuinely new failure type doesn't stay invisible either — this is literally how the original two patterns were found, by manually grepping). Every occurrence gets its own `WorkerAlert` immediately, never batched or thresholded. Since this is the same logger instance passed to `makeWASocket` for the whole connection, it covers history-sync decrypt failures too, not just live ones — Baileys uses one logger for everything.

   *Also drives `connection_unhealthy`* (§17.2) as a separate, higher-level escalation: past 15 decrypt failures or 5 handshake timeouts since the last successful message (not a time window — a healthy session never accumulates these regardless of uptime), the session is flagged for the "needs re-link" UI banner, once, not re-alerted on every subsequent failure.

   *Safety lesson baked into the implementation*, from the incident that preceded this fix (§17.2 has the full postmortem): the log-inspection code is wrapped in its own try/catch, so a bug in `_inspectBaileysLogArgs` can never take the actual Baileys log call down with it — verified in isolation (a standalone script exercising normal calls, error calls, and a deliberately-thrown bug inside the hook) before being wired into a live session.

2. **`_forwardHistoryBatch` build failures** — now call `_reportDropped('history_build_error')` instead of only `logger.warn`, matching the live path's existing behavior. Also closes a live-traffic gap: reconnect-redelivered live messages route through this same function via the `'prepend'` branch, so this wasn't purely a history-sync issue.

3. **Django batch-ingest per-message persistence failures** — previously only counted into an aggregate `error_count`, with a log line naming just the message ID (content unrecoverable). Now writes a `DroppedMessage` row with `reason='batch_persist_failed'` and the **full original payload** in `raw_key` (not the usual `msg.key` shape — the whole payload, so the content is recoverable even though the `WhatsAppMessage` row was never created), plus a `batch_partial_failure` `WorkerAlert` for the aggregate.

4. **Worker blindly trusting a non-throwing batch response** — `sendMessageIngestBatch` can return HTTP 200 with `errors > 0` (some items in the batch failed to persist server-side); the worker used to treat any non-throw as total success and mark every message in that chunk `forward_status: 'success'` in its own local log. Now inspects `result.errors` and marks the chunk `partial_error` when nonzero, so the worker's own log doesn't contradict what Django just reported losing.

5. **The drop-reporting safety net's own failure was invisible** — `sendDroppedMessage` (and the new `sendWorkerAlert`) used to log a failed report at `debug` level (invisible at the default `LOG_LEVEL=info`) with no other trace — meaning the mechanism built specifically to catch drops had a hole exactly when Django was already unreachable, i.e. exactly when things were already going wrong. Both now log at `warn` and fall back to a local `failed-reports.ndjson` file (`DjangoClient._writeFallback`) so the report survives even a full Django outage.

6. **No process-level exception handler anywhere in the worker** — an exception inside an async Baileys event handler (`connection.update`, `messages.upsert`, `contacts.set`, etc.) had no top-level or process-level catch; whatever was in flight died to stderr, which isn't captured anywhere durable. `index.js` now registers `process.on('uncaughtException', ...)` / `process.on('unhandledRejection', ...)`, writing a durable `process-errors.ndjson` record and a best-effort `WorkerAlert` (`account=null` — no session context at this level). Deliberately does **not** call `process.exit()` the way Node's usual guidance recommends — this deployment's process supervision isn't something this fix controls, and an unexpected full-outage crash would itself be a new failure mode; the trade-off made here favors staying up and serving every other session over a clean-slate restart.

   One concrete gap this closed: `jidNormalizedUser(c.id)` in the `contacts.set`/`contacts.upsert` handler sat *outside* the try/catch protecting the rest of that loop — one malformed contact entry aborted alias-mapping for every other contact in the same batch silently. Now wrapped per-contact, logs and skips just the bad one.

**Cross-group broadcast dedup (`duplicate_broadcast`):** traders routinely post the identical WTB/WTS list to many different WhatsApp groups within minutes of each other. Before this check, every repost triggered its own full AI classification call. `_is_duplicate_group_broadcast(message)` in `ingestion_service.py` runs last in `_classify_skip_reason` (it's the most expensive check — a `pgvector` cosine-distance query — so cheaper skip reasons short-circuit first) and only applies to `GROUP`-type chats. It compares this message's embedding (already computed by the time this runs — embed always happens before classify in the same background thread) against embeddings of messages from **any** group/contact on the same account that already produced a genuine inquiry (`is_inquiry=True`) within the last hour. A cosine-similarity match ≥0.92 — the same bar `inquiry_service.py`'s same-contact layer-2 dedup already uses — skips this message with `skip_reason='duplicate_broadcast'` instead of spending another AI call on it. Deliberately **not** scoped to the same contact or the same group (a repost from a different sender into a different group still counts — that's the whole point), and fails open (proceeds to classify normally) if this message has no embedding yet, so a lagging embedding provider never silently drops a real inquiry.

**Classification prompt context:** `classify_message` passes the sender's *existing* `whatsapp_contact.category` into the prompt (`"not set"` if blank) alongside the product master block (§6.8, now qty>0 filtered) — see §6.9 for the resulting `suggested_contact_category` output and §6.9's `match_type` field for the exact/near/null product-matching contract. Both are prompt-instruction-only mechanisms; no code-side matching or validation logic re-derives them (see below) — with one narrow exception (the self-consistency check, below).

**Product retrieval (built; used for human-assisted search, still not wired into the classification prompt):** every active product gets a background-embedded vector (§6.5.1, `product_embedding`) the moment it's created or edited, and as of Phase 20 every alias gets its own too (§6.8.1, `product_alias_embedding`) — ahead of an anticipated catalog-growth need rather than a current one. `find_similar_products()` does a multi-vector cosine-distance top-K lookup across both tables, deduped to the single best match per product. The product master block passed into the classification prompt itself is still the *full* text list, unfiltered by retrieval — with ~30 active products that's cheap and simple, and a real test confirms why retrieval alone isn't a substitute for the matching logic anyway: querying for "iPhone 17 Pro Max 256GB Orange Japan" put the wrong-color variants within a distance of 0.06–0.09 of the correct one (0.0134) — far too close to trust a similarity threshold to make the exact/near/null call. It **is** now used directly, though, as a human-facing search: the trading dashboard's "Auto" match-fix button (§20 Phase 17) calls `find_similar_products()` as a fallback when a direct name/alias search over the loaded catalog comes up empty, surfacing candidates for a human to confirm — never applying a match on its own. The intended future shape for classification itself, once catalog size actually requires it: use `find_similar_products()` to narrow to the top-K candidates *before* building the prompt, then still hand only those (as text, same as now) to the AI for the precise attribute-by-attribute judgment — retrieval picks candidates, it doesn't replace the reasoning.

**Frontend trust boundary:** `TradingView.vue` used to independently re-verify `match_type` with its own exact-string-name comparison (`isReliableMatch`) before trusting a matched product's price — this duplicated the same fuzzy-matching problem the AI is already paid to solve, with a strictly worse tool, and produced its own false positive (brand name written as a bare prefix, e.g. "Apple iPhone..." vs the catalog's brand-less "iPhone..."). `isReliableMatch` now does nothing but read `match_type !== 'near'` — the AI's verdict is authoritative; `stripBrandPrefix` remains only for cosmetic cleanup of the outgoing WhatsApp text, never for match verification. The same principle was later applied to `matchInventory()`: it used to fall back to a substring search over `canonical_name` whenever `product_id` was null, silently overriding the AI's own "no confident match" decision with a guessed one — it now does nothing but look up `product_id`, full stop.

**Backend self-consistency check (`_validate_exact_matches`, `classification_service.py`):** despite repeated prompt hardening (§20 Phase 9, and further rounds — see Phase 10, 12), the AI periodically still asserts `match_type="exact"` for a `product_id` whose real catalog name contradicts what it wrote into `canonical_name` for the same product line (e.g. `canonical_name` says "Blue Japan", but the linked catalog entry is actually "Orange Japan"). This is **not** a re-match — the system never tries to find a different/better `product_id` itself, which would repeat the exact mistake the frontend trust-boundary fix above corrected. It only checks whether the AI's own two answers (the real name of the product it linked, vs. the `canonical_name` it wrote for that same line) agree word-for-word; if any word from the real catalog name is entirely absent from `canonical_name`, `match_type` is downgraded to `"near"` before the classification is saved. Runs once per classification, right before the `MessageClassification` row is created, so it protects both `MessageClassification.products` and `Inquiry.products` (the latter copies directly from the former). Fails safe — a catalog lookup error leaves `products` untouched rather than blocking classification. This check is now the confirmed safety net for the residual matching gaps documented in Phase 12 — verified directly (not assumed) to catch and downgrade every remaining wrong-`"exact"` case found during that consolidation's testing.

See §6.9–6.10 for the classification/inquiry schema and the Trading Intelligence section below for the full pipeline.

---

## 13. LID (Linked ID) Handling

WhatsApp LID is a privacy feature that replaces a user's phone JID with a random opaque identifier (`200506303578143@lid`) in group chats and certain scenarios.

### Identifiers

| Suffix | Meaning | Example |
|---|---|---|
| `@s.whatsapp.net` | Real phone-based JID | `971503218002@s.whatsapp.net` |
| `@g.us` | Group JID | `120363425330019689@g.us` |
| `@lid` | Privacy-mode alias | `200506303578143@lid` |

### Resolution sources (priority order)

For a chat-level LID (an individual chat whose `remoteJid` itself is a LID) — revised 2026-07-21, see `docs/Contact Message Loss — LID Resolution Fix Proposal.md`:

1. `msg.key.senderPn` — Baileys-provided real phone JID, **inbound only**. WhatsApp never supplies this for outbound self-echoes, which is why outbound resolution used to depend entirely on source 2 already being warm (11 confirmed `unresolvable_lid` drops for one contact over two weeks, 100% outbound — §17.2 "Eighth incident").
2. `session.lidToPhone` — in-memory cache populated from `contacts.set`/`contacts.upsert` at connect time and updated whenever `senderPn`/`participantPn` is seen. Also **seeded from the DB** (`GET /api/internal/whatsapp/lid-mappings/:id/`) when a session is restored on worker restart, so the cache isn't cold immediately after a restart.
3. **New (2026-07-21):** a persisted single-LID lookup against Django (`GET /api/internal/whatsapp/lid-mapping/:id/?lid_jid=...`, §10, §6.7.3) — queried when source 2 misses, instead of failing immediately. Closes the gap source 2 couldn't cover on its own: an outbound self-echo has no live signal at all, so without this the cache going cold on any restart meant the same contact's outbound messages kept failing until an inbound message happened to arrive first.

`msg.key.participantPn` resolves the sender *within* a group whose `remoteJid` is already a known `@g.us` JID — a separate, narrower case (the chat identity isn't in question, only who sent it), unaffected by the chain above.

### Strict rule

If a LID cannot be resolved to a phone JID via any of the above, creating a phantom `@lid` contact in Django remains explicitly forbidden — that part is unchanged. What changed 2026-07-21: for a chat-level LID, the message is **no longer dropped**. It's preserved as `whatsapp_unresolved_message` (§6.7.3) with full content, and automatically recovered the moment a later `contacts.set`/`contacts.upsert` resolves that LID. `unresolvable_lid` as a `whatsapp_dropped_message` reason is now scoped to the group-participant case only (§9) — that one still hard-drops, since only the *sender* is unresolvable there, not the chat itself, and preservation was scoped to the chat-level case per the fix-proposal document.

### Database

One contact row per real person. `wa_contact_id` is always the canonical phone JID. `lid_jid` stores the LID alias when known. A DB-level unique constraint prevents two contacts in the same account from sharing a LID.

---

## 14. Sync Log Metadata Shapes

### message_ingest

```json
{
  "provider_message_id": "3EB0...",
  "chat_id": "971503218002@s.whatsapp.net",
  "sender_jid": "971503218002",
  "push_name": "Ahmed",
  "message_type": "text",
  "message_text": "Hello (first 200 chars)",
  "direction": "inbound",
  "embedded": 1,
  "embed_errors": 0
}
```

`embedded` / `embed_errors` are patched in after the background embedding thread completes.

### history_sync

```json
{
  "total": 342,
  "created": 340,
  "skipped": 2,
  "errors": 0,
  "embedded": 310,
  "embed_errors": 0
}
```

---

## 15. Embedding

- Model: `voyage-3-lite`
- Dimensions: **512**
- Stored in `message_embedding.embedding` as `vector(512)` (pgvector)
- Index: `USING ivfflat (embedding vector_cosine_ops)`
- Triggered: daemon thread fires after each `ingest_message` and `ingest_batch` call
- Admin backfill: `POST /api/intelligence/backfill/` processes up to 500 pending messages in background

---

## 16. Frontend Screens

Top nav is grouped into four hover dropdowns (`App.vue`) to keep the bar from overflowing as screens were added — **Reports**, **Lists**, **Settings**, and **Logs** — each highlights as active when the current route is one of its children. Everything else stays a flat top-level link.

| Route | Screen | Nav placement | Purpose |
|---|---|---|---|
| `/login` | Login | (public, no nav) | Session auth gate — only unauthenticated screen |
| `/conversations` | Conversations | top-level | Chat list + message view, WhatsApp deep-link ("open in WhatsApp") on messages/chats |
| `/trading` | Trading Dashboard | top-level | Live WTB/WTS feed. Each card is a fixed-size header/body/footer layout: **header** is a single row (contact name/phone, category dropdown + AI-suggestion apply chip, group/community label, account badge, age); **body** is exactly 3 fixed-height rows — Summary, Original Message (verbatim `source_message_text`, not AI-summarized), Stock Suggestion; **footer** has the status dropdown, match-quality rating, and WhatsApp actions. Clicking a body row opens its full content in a **popup dialog** (Phase 18) instead of growing in place inside the card (the old behavior left dead space and made cards jump around in the feed) — the popup is double the original size, **draggable** by its header, has a dedicated small "×" close button, and — unlike the old behavior — does **not** close on an outside click or a click anywhere inside it (both traced to one leftover global `document` click listener from the pre-popup design, removed entirely). WTB and WTS columns are paginated independently (`open-feed?type=buy`/`type=sell`, §11.3) — each shows `loaded / total` in its header and infinite-scrolls to load more as you scroll that column, instead of the old single combined feed silently capped at 50 total across both columns. A header control lets you **close all open inquiries older than N hours** (default 1) in one click, scoped to the selected account (§20 Phase 16, `POST /inquiries/close-stale/`) — confirms before running, only ever touches `status=open` records. Stock Suggestion only ever shows products actually in stock (`qty > 0`) — a saved `sale_price` on a zero-qty item no longer displays a false ✓ "in stock". Stock hints turn amber with a ⚠ when the matched inventory item is only a `"near"` match; a mismatch pill now also carries **"Fix"** and **"Auto"** buttons (§20 Phase 17) — "Fix" opens a searchable product picker (same popup treatment: double size, draggable, dedicated close button, no outside-click-close) to manually pick the correct catalog entry, which calls `POST /inquiries/:id/correct-match/` and promotes that line to `match_type='exact'` (the pill turns green on its own, same as any AI-confirmed exact match — no separate "manually confirmed" styling needed); "Auto" runs a direct name/alias search over the already-loaded catalog first (instant, no network), falling back to the embedding-based `GET /products/search-embeddings/` only if that comes up empty, surfacing candidates tagged `exact` or `~NN% match` — either way a human still has to tick a checkbox to apply one, matching the "AI/embeddings pick candidates, they don't replace the human/AI judgment call" principle used everywhere else in this system. Each inquiry also has a manual **1–5 match-quality rating** (§6.10, §20 Phase 17) — five small buttons in the footer, defaulting to 5 (color-coded red/amber/green) so a reviewer only has to touch the ones that are actually wrong. Per-card WhatsApp actions (all prefill the compose box via `text=`, never auto-send, and never include the customer's requested quantity in the text): **WA** — the sender's original message verbatim, two blank lines, "Please check price below:", then item(s) + our sale price (only when `match_type !== 'near'` and the matched product has `qty > 0`); **Ask Price** (WTB + WTS) — item(s) + blank line + `Price?`; **Price List** (WTB only) — the stored AI-formatted price list (§6.15, §11.3) sent verbatim, not built ad hoc from the product table. Each card also has a quick contact-category selector (Uncategorized/Supplier/Customer/Both) that pre-fills with the AI's `suggested_contact_category` when one is pending, applied with one click; category-save failures show a dismissible error banner rather than failing silently. "Incorrect Match" status opens an inline reason prompt instead of saving immediately |
| `/trading-analytics` | Trading Analytics | under **Reports** | Product demand, source breakdown, activity timeline, response/conversion time. A header dropdown offers 10 date-range shortcuts (Today, Yesterday, This/Last Week, This/Last Month, This/Last Quarter, This/Last Year — default **Today**, §20 Phase 16) computed client-side into `date_from`/`date_to` and sent to `getStats`/`getProductStats`/`getClassificationActivity` (§11.3); the activity chart adapts its own granularity to the selected range (hourly bars for a single day, daily bars for anything longer, per `timeline_granularity` from the backend) and its title/section labels reflect whichever range is selected instead of a hardcoded "(Today)". The Trading Dashboard's own stat chips are unaffected — they never pass a date range, and the backend defaults to "today" when neither is given |
| `/buying-inquiries` | Buying Inquiries | top-level | Manually create a purchase request (§6.14); auto-populates a card per tagged supplier with Ask Price / Log Quote / No Stock actions and a status badge per supplier |
| `/contacts` | Contacts | under **Lists** | Contact management, display name editing, LID/username alias display, per-contact AI-parse toggle, supplier/customer/both category tagging (filterable), sortable columns (Display Name/WhatsApp Name/Phone/Category/Msgs, server-side via `ordering`) |
| `/groups` | Groups | under **Lists** | Group/community list, sync trigger, per-group AI-parse toggle |
| `/products` | Products | under **Lists** | Product master CRUD, AI bulk-import from pasted price lists, bulk inventory update via AI. Table shows Qty/Cost/Sale/**Margin** (sale − cost) per product, a **Total PNL** badge (Σ margin × qty across the visible/filtered rows), an aggregate **"Embeddings: X/Y"** badge with a **Backfill (N)** button that only appears when something's missing (§6.8.1, §20 Phase 20), and two per-row columns — **Product Embedding** (✓/✗) and **Alias Embeddings** (`N/M`, or "—" with no aliases) — for pinpointing exactly which row needs attention. Qty/Cost/Sale/Currency are directly editable in the Add/Edit modal, plus inline click-to-edit on the Qty/Cost/Sale table cells themselves (Enter/blur to save, Escape to cancel). The Add/Edit modal was rebuilt in Phase 20: double the original size, **draggable** by its header, card-sectioned (Basic Info / Pricing & Stock / Aliases) instead of one flat stacked list, does **not** close on an outside click (dedicated "×" plus "Cancel" only), and the Aliases section is a live interactive chip input — type + Enter/comma adds a chip, click "×" or press Backspace on an empty input removes the most recent one; for an existing product each add/remove persists immediately via `POST`/`DELETE /products/:id/aliases/` (own embedding queued right away), for a brand-new product they're held locally and flushed to the API the moment the product itself is created. **Price List** button opens a modal showing the current AI-formatted price list (§6.15) and when it was last generated, with a **Regenerate** button that re-runs the `price_list_format` prompt (§6.11) against the current in-stock catalog — manual only, never automatic on product/inventory changes |
| `/` | Sessions | under **Settings** | Create/manage WhatsApp accounts, QR connect (formerly "Accounts"). `AccountCard.vue` has a red "Connection needs attention" banner for `connection_unhealthy` accounts (takes priority over the sync-progress states) — live since Phase 14 (§17.2); also shows history-sync progress (awaiting/syncing/done, §11.1 `sync-progress`) |
| `/storage` | Storage | under **Settings** | Per-account storage stats, media controls, embedding status + backfill |
| `/ai-providers` | AI Providers | under **Settings** | Manage voyage/openai/etc. provider config and API keys |
| `/ai-instructions` | AI Instructions | under **Settings** | Edit trading prompt overrides (§6.11), view AI agent call log/diagnostics (§6.12) |
| `/activity` | Activity Log | under **Logs** | Sync log with filter by account/type, embedding status per event |
| `/message-logs` | Message Logs | under **Logs** | Raw per-session worker log viewer |
| `/dropped-messages` | Dropped Messages Log | under **Logs** | All messages the worker dropped, expandable raw key with `_msgKeys`; rows that later self-healed (§6.7 `resolved_at`) show a green "Recovered" badge |
| `/worker-alerts` | Worker Alerts | under **Logs** | Structured record of worker-side failures (§6.7.1, §12) — decrypt failures, handshake timeouts, batch persistence failures, uncaught exceptions — filterable by account/type/acknowledged, with per-row and bulk acknowledge. The top nav's **Logs** dropdown carries a red unacknowledged-count badge (polled every 30s, `GET /api/worker-alerts/unacknowledged-count/`), visible from anywhere in the app without opening the dropdown — the "admin should be notified" requirement this screen exists to satisfy |
| `/stuck-receipts` | Stuck Receipts | under **Logs** | Messages WhatsApp keeps asking the worker to resend that it can't fulfill (§6.7.2) — one row per distinct stuck message, occurrence count + last-seen so you can tell if it's still recurring, filterable by account/resolved, with per-row resolve. Same unresolved-count nav badge pattern as Worker Alerts (combined into the same **Logs** dropdown total) |
| `/unresolved-messages` | Unresolved Messages | under **Logs** | Messages preserved with real content whose chat-level LID couldn't be resolved (§6.7.3) — pending/resolved/failed counts, filterable by account/status, expandable to full message text and (if failed) `resolution_error`. Read-only — resolution happens automatically, not from this screen. Same pending-count nav badge pattern as Worker Alerts/Stuck Receipts |
| `/ai-parsing-log` | AI Parsing Log | under **Logs** | Every live message and whether it was sent for AI classification or skipped, and why (§6.13) — filterable by account/status/skip reason |
| `/inquiries` | Inquiries | not in top nav (direct URL only) | Split-panel inquiry list + detail, status workflow (10 states, see §6.10), remarks |

---

## 17. Worker Session State

Each active session (`this.sessions.get(sessionId)`) holds:

```javascript
{
  sock,                  // Baileys socket, null while disconnected/erroring
  status,                // one of the §8 session statuses
  qrDataUrl,             // current QR as a data: URL, or null
  phoneNumber,
  displayName,
  syncHistory,
  historyDays,           // from account settings
  autoDownloadMedia,
  idleDisconnectMs,      // 0 = disabled
  lastActivityAt,
  idleTimer,             // setInterval handle for idle-disconnect, or null
  preventReconnect,      // true = the next 'close' event should not auto-reconnect
  watchdogTimer,         // setTimeout handle for the connection watchdog (§17.1), or null
  watchdogFired,         // true between the watchdog firing and its 'close' cleanup running
  lastError,             // human-readable message set when status === 'error'
  lidToPhone: {},        // Map: normalized LID JID → full phone JID
                         // Populated from contacts.set and participantPn/senderPn on live messages
  usernameToPhone: {},   // Map: bare username → full phone JID, from contacts.set c.username
  // Connection-health counters (see §17.2) — reset to 0 on every successfully-forwarded
  // message/batch and on every fresh 'open' connect. No detection call site increments
  // them right now, so they stay at 0 / false in practice.
  consecutiveDecryptFailures: 0,
  consecutiveInitQueryTimeouts: 0,
  connectionUnhealthy: false,
}
```

### 17.1 Connection Watchdog

Added 2026-07-04 after QR connections were observed hanging indefinitely with no error ever surfacing to the UI — the frontend polled `GET /accounts/:id/qr/` forever showing "Generating QR code…" with no way to tell the difference between "still working" and "will never finish."

**The gap:** the only thing that ever changed a session's status was Baileys firing a `connection.update` event (`qr`, `open`, or `close`). If the initial WebSocket handshake stalled — bad network, WhatsApp-side throttling, a stale/corrupted auth directory — nothing ever fired, and nothing timed out. Reopening the QR modal didn't help either: `createSession()` no-ops whenever `session.sock` is already set (`session-manager.js` — `if (existing?.sock) return this._snapshot(sessionId)`), and a hung socket still counts as "set."

**The fix — two layers, both converging on `SESSION_STATUS.ERROR`:**

1. **Post-socket-creation watchdog** (`_armWatchdog` / `_clearWatchdog` / `_handleStuckConnection`). A 45-second (`WATCHDOG_TIMEOUT_MS`) timer is armed right after `makeWASocket()` returns, and re-armed every time a `qr` event fires — so a healthy handshake or a legitimate wait-for-scan (Baileys periodically re-issues `qr`) keeps pushing the deadline out. It's cleared on `open`. If it ever fires: the dead socket is torn down (`sock.end(...)`), `session.sock` is set to `null`, `status` becomes `error`, and `lastError` gets a human-readable message. Because `sock` is nulled, the *next* `createSession()` call (e.g. reopening the QR modal) is no longer a no-op — it actually reconnects.

   A `watchdogFired` flag suppresses the normal `close`-handler logic (which would otherwise overwrite the `error` status with `disconnected` and schedule a reconnect) so the error state sticks until the user retries.

2. **Pre-socket-creation try/catch** in `_connect()`. Auth-state loading (`useMultiFileAuthState`), Baileys version fetching (`fetchLatestBaileysVersion`), and socket construction all happen *before* there's a socket to arm the watchdog on. If any of these throw (corrupted `creds.json`, network failure fetching the Baileys version), the session used to stay stuck at `pending_qr` with `sock: null` forever, invisible to the watchdog. This path now catches the error directly and marks the session `error` with the real exception message — no separate mechanism, just closing the same gap earlier in the lifecycle.

**Surfacing to the UI:** `GET /sessions/:id/qr` (worker) returns HTTP 500 with `{error, status: 'error'}` whenever a session is in the error state, instead of an endless `202`. Django's `qr` view passes the status code straight through. `QRModal.vue`'s `poll()` no longer has a "keep polling silently" fallback for unrecognized errors — every failure path (404, 503, 500, or an unexpected network error) stops polling and shows an actionable message.

### 17.2 Connection Health Detection (complete — see Phase 14 for the incident and safe reimplementation)

**The problem this solves:** a session can report `connected` (and WhatsApp mobile shows the linked device as active) while its *local* copy of the Signal-protocol session is desynced enough that it can't decrypt anything, or WhatsApp's post-connect handshake keeps timing out — confirmed on a real account via `whatsapp-worker/message-logs/baileys-internal.log`: 570 "failed to decrypt message" errors and 61 "unexpected error in 'init queries'" timeouts over 5 days, with the account showing `connected` in the DB the entire time despite zero messages (live or history) actually flowing for the last ~36 hours of that window. Reconnecting doesn't fix this — it reuses the same corrupted local key state — only a fresh QR re-link (new Signal session) does.

**What's built:** `WhatsAppAccount.connection_unhealthy` / `_reason` / `_since` fields (migrations `0018`/`0019`, the latter converting `_reason` from `CharField(255)` to `TextField` after a real reason string exceeded 255 chars in testing), a `connection_unhealthy` payload field on the internal `session-status` endpoint (only ever touched when the worker explicitly includes it — a plain status ping never clears a prior flag), the same field surfaced on `sync-progress` and the account serializer, and a red "Connection needs attention" banner in `AccountCard.vue` that takes priority over the normal sync-progress states.

**Detection** (`_createBaileysLogger` / `_inspectBaileysLogArgs`, `session-manager.js`) uses pino's `hooks.logMethod` — an interception point that fires on every log call *before* formatting/writing, without touching the destination stream at all. Past 15 decrypt failures or 5 handshake timeouts since the last successful message (not a time window), the session flips to `connection_unhealthy` once — not re-alerted on every subsequent failure — while every individual occurrence, regardless of whether the threshold has tripped, also gets its own `WorkerAlert` (§6.7.1, §12) immediately. Verified in isolation (mocked `SessionManager` + `djangoClient`, fed real captured log line shapes) before being wired into a live session: correct pattern matching, correct escalate-once-then-stop behavior, correct per-occurrence alerting continuing after the threshold trips.

**This was broken once, on the first attempt (2026-07-11) — worth keeping as a concrete lesson:** the first implementation wrapped pino's file destination (`pino.destination(filePath)`) in a plain JS object implementing only `.write()`. Real pino destinations (`SonicBoom`) also implement `flushSync`, `flush`, `on`, `reopen`, `end`, and `destroy` — confirmed by direct inspection of the installed pino (`9.14.0`) destination object. Something in Baileys/pino's internals called one of the missing methods and threw with nothing to catch it, deep inside Baileys' own connection/logging pipeline — not caught by `_connect()`'s existing try/catch, which only wraps the *setup* code, not every subsequent internal Baileys operation that logs through the socket's logger for the life of the connection. Result: live sessions got stuck mid-flow and stopped responding to disconnect requests, on a running worker process that (since it's a plain `node index.js`, no `--watch`) kept the broken code loaded until manually restarted. That code was fully reverted and removed (not patched — removed, since it was never verified in isolation first) before the `hooks.logMethod` rebuild above, which **was** verified in isolation first, specifically because this incident happened.

A second, unrelated gap surfaced while debugging that incident: `apps/api/views.py`'s `disconnect` action used to be a pure proxy — if the worker replied 404 "Session not found" (which happens legitimately whenever the worker has no in-memory session for that ID, e.g. after the credentials-clearing logout flow above), Django relayed the 404 but left its own `session_status` untouched, permanently stuck at whatever it said before. This is now self-correcting: a 404 from the worker flips `session_status` to `disconnected` (unless already `logged_out`/`disconnected`) instead of leaving stale state with no working recovery path in the UI.

**Third bug found and fixed (2026-07-13): `connection_unhealthy` never cleared after a re-link.** Reported directly: an account showed "Connected" after a disconnect + fresh QR re-link, but the red "Connection needs attention" banner stayed up. Root cause — the clear-on-reconnect logic gated sending the reset to Django on the **in-memory** session object's own prior `connectionUnhealthy` value (`if (wasUnhealthy) { ...send connection_unhealthy: false... }`), but a re-link deletes the old session object entirely and constructs a brand-new one (`connectionUnhealthy: false` from the moment it's created) — so on the very next successful connect, `wasUnhealthy` was always `false` for a freshly re-linked session, and the send was skipped, leaving Django's persisted flag (and its reason text) stuck exactly as it was before the re-link, forever. Fixed by sending the clear **unconditionally** on every successful `connection === 'open'`, instead of gating it on in-memory state that can't be trusted to match a persisted DB flag across a delete/recreate boundary — the POST is cheap and correct either way (a no-op overwrite when the flag was already `false`). The stuck record found this way was corrected directly in the DB as a one-time fix; the code fix prevents it recurring on any future re-link.

**Fourth incident (2026-07-17): root cause found for the recurring handshake-timeout pattern — fix designed, not yet implemented.** This is the 4th distinct engineering pass at WhatsApp connection reliability in this codebase (Jun 30 silent-drop closure, Jul 7 reconnect backoff, Jul 11 first/reverted and second/shipped `connection_unhealthy` detection above), and the pattern across all of them was the same: each pass made the problem more *visible* (alerts, logs, a UI banner) without making it *self-heal*.

Concrete trigger: the "Expert Devices" account (id 9) got a genuine `logged_out` event, was re-linked via a fresh QR at 10:15:40, authenticated successfully (`session_status=connected`), then at 10:16:40 — one minute later — hit an `"unexpected error in 'init queries'"` handshake timeout and never processed another message. No reconnect storm preceded the logout (ruled out via `SyncLog`), so the logout itself remains unexplained; the *stuck-after-reconnect* part is now fully understood.

**Root cause, confirmed by reading Baileys' own source** (`node_modules/@whiskeysockets/baileys/lib/Socket/chats.js:761-859`): on every connect, Baileys fires `executeInitQueries()` (`fetchProps` + `fetchBlocklist` + `fetchPrivacySettings`, the same calls the official web client makes). It's invoked as `executeInitQueries().catch(error => onUnexpectedError(error, 'init queries'))` — bare catch, logged, **no retry, no reconnect, nothing**. The default query timeout (`defaultQueryTimeoutMs: 60000`, unmodified in this codebase) isn't the problem — a real 60-second round-trip to WhatsApp's servers got no response. The problem is that nothing happens after that timeout: the socket-level connection stays `open` (Baileys never emits `close`), so the existing exponential-backoff reconnect path (`session-manager.js:629-687`, the Jul 7 fix) never fires, because from the socket's perspective nothing closed — only an unrelated internal promise silently died. The session is left authenticated but functionally inert, indefinitely, with no automatic path back to working.

This is a real gap in Baileys itself, not something this codebase introduced — and it's a concrete, provable instance of the broader reason a reverse-engineered client is inherently less reliable than the official one: the official web client is Meta's own first-party implementation of this same handshake, co-evolved with the server and presumably far more defensively coded; Baileys has to reverse-engineer the same behavior and, at least at this call site, has none of that defensiveness.

**Planned fix (not yet implemented — deferred at explicit request):** in `_inspectBaileysLogArgs`, at the point the `"unexpected error in 'init queries'"` pattern is already matched (`session-manager.js` around line 175), force-close the socket immediately (`session.sock.end(new Error(...))`) instead of only logging it. This routes through the *existing* `connection.update` `'close'` handler — the same path a real network disconnect already takes — which already correctly distinguishes this from a `loggedOut` close and already reconnects with the existing exponential backoff, reusing the same saved credentials (no QR needed). No new retry/backoff mechanism needed; the fix is entirely "make sure the mechanism we already built actually gets triggered for this failure," since today it structurally can't be, because Baileys never signals a close for this failure mode. The existing 5-consecutive-timeout `connection_unhealthy` escalation stays as the higher-level "auto-reconnects aren't working either, a human should re-link" signal, and should fire far less often once single blips can self-heal within one backoff cycle instead of sitting dead until someone notices.

**Fifth incident (2026-07-18): `MessageCounterError` decrypt failures confirmed to cause real, permanent outbound-message loss — same reconnect fragility, a different symptom, still deferred.** Investigated after a single `decrypt_failure` WorkerAlert was flagged for review (account 8, `{"err":{"name":"MessageCounterError"},"key":{"id":"3EB042811F7C3164F19E65","fromMe":true,"remoteJid":"238246365806668@lid"}}`).

Baileys' `MessageCounterError` comes straight from `libsignal`'s `session_cipher.js` (`doDecryptWhisperMessage`): thrown when the message key for a given counter was already used and deleted — by the library's own comment, "most likely the message was already decrypted and we are trying to process twice... can happen if the user restarts before the server gets an ACK." This is Signal's replay protection, not inherently a bug.

Found 407 such alerts (account 8 only, 2026-07-13 → present, ~97 distinct contacts), **all `fromMe: true`** — never an inbound customer message, so no inquiry was ever silently dropped by this specific failure mode. But ChatLens never calls `sock.sendMessage()` anywhere in the worker (confirmed by search) — every outbound message is sent from the phone/WhatsApp Web via `whatsapp://send` deep links (`TradingView.vue`'s WA/Ask Price/Price List buttons), so the *only* way ChatLens ever learns what was sent is this self-sync echo. A failed decrypt here isn't necessarily harmless the way the library comment implies for the general case.

Verified empirically by cross-referencing every failed message ID against `whatsapp_message.provider_message_id`:
- **301/407 (74%) already captured** on an earlier successful delivery — genuinely harmless duplicate-suppression, exactly as the library comment describes.
- **106/407 (26%) never recorded anywhere** — real messages, permanently gone, no fallback path.

The 106 real losses aren't spread evenly — they land in sub-2-second bursts (one burst alone, 2026-07-14 15:15:55–57, accounts for 57 of them). Checking what else was happening at each burst: **14 of 16 bursts are preceded within seconds by a `"stream errored out"` alert** — i.e. these are messages WhatsApp delivered as a backlog immediately after a reconnect, which the freshly-reestablished session couldn't decrypt (first-time delivery, not a replay — no earlier copy exists to fall back on). This is the same reconnect-fragility root cause as the fourth incident above, surfacing a second, more serious symptom: not just "the session gets stuck," but "a live reconnect can silently and permanently drop real business messages sent in the same window."

**Not implemented — explicitly deferred again at the point of investigation**, consistent with the fourth incident's deferral. Documented so the two are picked up together: the planned fix above (force-close on handshake-timeout to trigger the existing backoff-reconnect path) addresses the *stuck-session* symptom; whether it also needs the backlog-delivery-vs-session-readiness ordering examined (so a fresh reconnect doesn't receive a backlog before its Signal session state is confirmed settled) is an open question for whoever implements this, not yet designed.

**Sixth incident (2026-07-18): a third, distinct failure mode — silent non-delivery with zero trace, not a decrypt failure.** Reported directly: a contact (Azan / Action Link Trading, account 8) sent "Wtb✅ iPad Pro 13 M5 256GB 5G BLACK 70pcs", visible on both WhatsApp mobile and WhatsApp Web, that never appeared anywhere in ChatLens.

This is a different shape of problem from the fourth/fifth incidents above, and was distinguished from them carefully rather than assumed to be the same thing:
- **Not a decrypt failure** — no `MessageCounterError` or any other Baileys error logged for this contact's session anywhere near the reported time. (This contact's session *does* have a history of `MessageCounterError` on other occasions, but every one of those is `fromMe: true` — our own outbound self-echo — never an inbound failure.)
- **Not a logged drop** — zero `DroppedMessage` rows for this contact.
- **Not an account-wide or group-wide outage** — the raw per-session capture log shows dozens of other senders, in multiple other groups, flowing normally in the exact same minutes.
- **Not present anywhere in the pipeline, including the earliest point** — searched the exact message text (not just a time window) across every raw per-session capture file, the internal Baileys log, `failed-reports.ndjson`, `debug-watch.ndjson`, and the database. Zero matches anywhere. (The only hits for a substring of the search were unrelated price-list messages sent to *other* contacts.)

A `MessageCounterError` at least proves something arrived and Baileys tried and failed to process it — there's a log line to trace. This case has no such trace at any layer, which means the message never reached this specific linked-device session at the WhatsApp-server level at all. WhatsApp's multi-device architecture delivers to each linked device independently (phone, personal Web session, and ChatLens's own linked device are all separate "devices" from WhatsApp's perspective); an occasional silent gap in that per-device fan-out is a plausible explanation, and not something any code in this repo can detect or recover from, since there is nothing that arrives for it to log, classify, or drop.

**Not a bug fix — a watch item.** Nothing to implement: there's no error to catch, no retry to add, no log path to fix. Documented per explicit instruction to track further occurrences and look for a pattern (e.g. specific contacts, specific times, correlation with other connection events) before deciding whether this needs a different kind of mitigation (e.g. periodic reconciliation against a second, independent view of the chat rather than relying solely on live delivery).

**Seventh incident (2026-07-20): `StuckReceipt` root-caused — 100% concentrated on one contact, not scattered.** Routine log inspection found that **every `StuckReceipt` row ever recorded (47/47, 2026-07-14 → 2026-07-20) is the same `remote_jid`** on account 8 — not scattered across contacts as the model's docstring (§6.7.2) implies. Every occurrence shares the identical crash: `context.key.remoteJid` is absent from the retry-receipt payload Baileys builds internally for `sendMessagesAgain`, so its own `relayMessage` (`messages-send.js:257`) calls `jidDecode(undefined)` and throws `TypeError: Cannot destructure property 'user' of 'jidDecode(...)' as it is undefined`. The affected contact has a `lid_jid` alias — a possible, unproven tie to the LID-resolution fragility documented in the eighth incident below. Not fixed — the existing short-circuit (`getMessage()` returning `null` for known-stuck keys) is working as designed and already prevents repeated crashes; the open question is why this one contact's retry-receipt key is missing `remoteJid` every single time, which requires tracing Baileys' own internal retry/history store, not this codebase's ingestion path.

**Eighth incident (2026-07-20): sixth incident recurred (same contact family, two days later) — two concrete, fixable silent-loss mechanisms found, distinct from the still-open zero-trace mystery.** A near-identical report came in for the same contact (Azan / Action Link Trading, account 8) and a second contact (City Choice, account 9): messages missing in both directions, zero trace anywhere — same shape as the sixth incident. Investigating triggered a full audit of the worker's error handling (not just this one contact), which found:

- **A confirmed, currently-reproducing outbound-only drop pattern for LID-chat contacts** (verified via the still-active `DEBUG_WATCH_JIDS` tap from the Sixth incident — 299 captured events, 11 confirmed `unresolvable_lid` drops for that same tracked contact spanning 2026-07-07 → 2026-07-20, **100% `from_me: true`**). Root cause: outbound self-echoes never carry `senderPn` (§13's resolution-source #1 is inbound-only), so outbound LID resolution depends entirely on `session.lidToPhone` already being warm — and it goes cold on every worker restart if the mapping was never durably persisted to Django in the first place.
- **A related reporting gap**: three of the worker's Django-reporting methods (`sendContactsUpdate`, `sendGroupUpdate`, `sendGroupParticipantsUpdate`) fail with only a transient log line — no durable fallback file, unlike their three sibling methods — so a POST failure at exactly the wrong moment permanently loses a LID mapping with no trace, directly feeding the pattern above.
- **Four further fallback/suppression code paths** that could mask this exact bug class with zero trace if they ever fire (most notably: the LID-cache-population loop in `_sendNamedContacts` skips a malformed entry with no log at all, unlike its own sibling loop ten lines away).

Root cause and proposed fix (not yet implemented, pending review) for all of the above: `docs/Contact Message Loss — LID Resolution Fix Proposal.md`. **Does not explain** the Azan/City Choice reports themselves — those resolve as plain phone JIDs, not LIDs, so this specific mechanism doesn't apply to them; they remain the same unsolved zero-trace mystery as the sixth incident, now with a second occurrence two days later. See `Silent Message Drop Investigation.md` for that still-open thread.

---

## 18. Security

- `INTERNAL_API_TOKEN` — shared secret between Node.js worker and Django. Set in `.env`. All internal endpoints validate this header.
- Session auth + CSRF gate every frontend route except `/login`. Enforced client-side by the Vue Router `beforeEach` guard (`frontend/src/router/index.ts`) calling `/api/auth/me/`, and server-side by DRF session auth on every `apps/api`/`apps/trading` viewset.
- `whatsapp-worker/sessions/` — WhatsApp E2E session keys. Never committed.
- `.env` / `.env.local_dev` — API keys and secrets. Never committed.
- `whatsapp-worker/message-logs/` — raw message logs for debugging. Not committed.

---

## 19. Migration History

### message_intelligence

| Migration | Description |
|---|---|
| 0001_initial | `message_embedding`, `message_analysis` tables |
| 0002_embedding_vector_index | `ivfflat` cosine-distance index on `message_embedding.embedding` |
| 0003_resize_embedding_to_512 | Resized embedding dimensions from 1536 to 512 (voyage-3-lite) |
| 0004_productembedding | New `product_embedding` table (§6.5.1) |
| 0005_product_embedding_vector_index | `ivfflat` cosine-distance index on `product_embedding.embedding` |
| 0006_productaliasembedding | New `product_alias_embedding` table (§6.8.1) — one embedding per `ProductAlias`, not per `Product` |

### whatsapp_bridge

| Migration | Description |
|---|---|
| 0001_initial | Base schema (account, contact, chat, message, embedding, analysis, synclog) |
| 0002_add_media_url | Added `media_url` to `whatsapp_message` |
| 0003_account_settings | Added `sync_history`, `history_days`, `idle_disconnect_minutes` to account |
| 0004_alter_media_url | Made `media_url` non-null with empty default |
| 0005_fix_lid_phone_numbers | Data fix for malformed phone numbers from early LID handling |
| 0006_add_auto_download_media | Added `auto_download_media` to account |
| 0007_add_dropped_message | New `whatsapp_dropped_message` table |
| 0008_add_lid_jid_contact | Added `lid_jid` to contact; merged existing `@lid` contact rows into phone contacts |
| 0009_add_username_contact | Added `username` alias column to contact (WhatsApp usernames rolling out 2026-07-07) |
| 0010_add_groups | New `whatsapp_group` / `whatsapp_group_participant` tables — first-class group/community identity |
| 0011_backfill_groups_from_chats | Data migration: seeded `whatsapp_group` rows from existing group-type chats |
| 0012_rename_whatsapp_dr_account_idx... | Index rename on `whatsapp_dropped_message` (Django auto-naming churn) |
| 0013_add_ai_parsing_fields | Added `ai_parsing_enabled` to account, `ai_parsing` tri-state to chat |
| 0014_ai_parsing_default_off | Flipped `ai_parsing_enabled` default from `True` to `False` — opt-in, not opt-out |
| 0015_droppedmessage_resolved_at_and_more | Added `resolved_at` to `whatsapp_dropped_message` + `(account, msg_id)` index |
| 0016_whatsappcontact_category | Added `category` to contact (`supplier`/`customer`, blank default) |
| 0017_alter_whatsappcontact_category | Added `both` to the `category` choices |
| 0018_whatsappaccount_connection_unhealthy_and_more | Added `connection_unhealthy`, `connection_unhealthy_reason`, `connection_unhealthy_since` to account (§17.2) |
| 0019_alter_whatsappaccount_connection_unhealthy_reason | Converted `connection_unhealthy_reason` from `CharField(255)` to `TextField` — a real reason string exceeded 255 chars during testing |
| 0020_workeralert | New `whatsapp_worker_alert` table (§6.7.1) |
| 0021_stuckreceipt | New `whatsapp_stuck_receipt` table (§6.7.2) |
| 0022_unresolved_message | New `whatsapp_unresolved_message` table (§6.7.3); added `unresolved_message_failed` to `whatsapp_worker_alert.alert_type` choices |

### trading

| Migration | Description |
|---|---|
| 0001_initial | `trading_product`, `trading_message_classification`, `trading_inquiry`, `trading_inquiry_message` |
| 0002_prompt_config | New `trading_prompt_config` table |
| 0003_agent_call_log | New `trading_agent_call_log` table |
| 0004_add_dedup_key_to_classification | Added `dedup_key` to `trading_message_classification` |
| 0005_add_inventory_fields_to_product | Added `qty`, `cost_price`, `sale_price`, `currency` to product |
| 0006_alter_inquiry_status | Expanded status from 3 states to 8: added `quoted_waiting`, `price_high`, `no_stock`, `not_dealing`, `irrelevant` |
| 0007_alter_inquiry_status | Added 9th status: `no_response` |
| 0008_aiparsinglog | New `trading_ai_parsing_log` table (§6.13) |
| 0009_buyinginquiry_supplierquote | New `trading_buying_inquiry` / `trading_supplier_quote` tables (§6.14) |
| 0010_alter_inquiry_status | Added 10th status: `incorrect_match` |
| 0011_inquiry_suggested_contact_category_and_more | Added `suggested_contact_category` to both `trading_inquiry` and `trading_message_classification` |
| 0012_formattedpricelist | New `trading_formatted_price_list` singleton table (§6.15) |
| 0013_alter_aiparsinglog_skip_reason | Added `duplicate_broadcast` to `skip_reason` choices (§6.13, §12) |
| 0014_inquiry_classification_rating | Added `classification_rating` (1–5, default 5) to `trading_inquiry` (§6.10, §20 Phase 17) |
| 0015_productalias | New `trading_product_alias` table (§6.8.1) |
| 0016_migrate_aliases_json_to_rows | Data migration: copied existing `trading_product.aliases` JSON into `trading_product_alias` rows (deduped case-insensitively) — a no-op in practice, every product's `aliases` list was already empty by the time this ran |
| 0017_remove_product_aliases | Removed the now-superseded `aliases` JSONField from `trading_product` |

---

## 20. Development Phases (Actual)

### Phase 1 — Foundation (complete)
- Django + DRF project, PostgreSQL, pgvector
- WhatsApp account, contact, chat, message models
- Internal ingestion API (single message + batch)
- Node.js Baileys worker — QR, session status, message forwarding
- Vue 3 frontend — accounts, conversations screens

### Phase 2 — Intelligence (complete)
- voyage-3-lite embeddings via pgvector (512-dim)
- Semantic search endpoint
- Background embedding daemon threads
- Admin embedding backfill

### Phase 3 — Observability (complete)
- Sync log / Activity screen with embedding status
- Dropped Messages Log — captures every silently-dropped message with reason
- Message log file per session (worker side)
- AI Provider management screen

### Phase 4 — Contacts & LID (complete)
- Contact management screen with inline display name editing
- LID alias column (`lid_jid`) on contacts — single row per person
- Strict LID resolution: unresolvable LIDs drop loudly, never create phantom contacts
- `senderKeyDistributionMessage` combined envelope fix — only pure key envelopes dropped
- `participantPn` used for group LID participant resolution + `session.lidToPhone` cache update
- Data migration merging historical `@lid` contact rows into canonical phone contacts

### Phase 5 — Groups, Usernames & Auth (complete)
- Group/Community split into first-class `whatsapp_group`/`whatsapp_group_participant` models with sync from `groupFetchAllParticipating()`
- WhatsApp username alias support (`username` column, same alias treatment as LID)
- Login screen + full session-auth gate on every frontend route
- Per-account and per-chat/contact/group tri-state AI-parsing toggles (default off)
- Auto-download media toggle, history sync progress bar, WhatsApp deep links (`whatsapp://send?phone=`) from chats/messages

### Phase 6 — B2B Trading Intelligence (complete)
- New `apps/trading` Django app: Product master (with inventory: qty/cost/sale price), AI classification, Inquiry lifecycle
- AI classification runs in the same background thread as embedding, immediately after `embed_message()`, gated by `_should_classify` (inbound, has text, <24h old, AI parsing enabled for the chat)
- Two-layer deduplication: exact `dedup_key` match, then embedding cosine-similarity fallback (≥0.92) for rephrased duplicates
- Inquiry status workflow expanded from the original 3-state plan (open/closed/deal_done) to 9 states covering the real trading desk workflow (quoted, no response, price too high, no stock, not dealing, irrelevant, etc.)
- AI-driven product recognition — no regex/Levenshtein matching, the AI does all fuzzy matching against the product+alias list
- Editable AI prompts (`trading_prompt_config`) and full AI call audit log (`trading_agent_call_log`) surfaced in the AI Instructions screen
- Frontend: Trading Dashboard (live WTB/WTS feed), Trading Analytics (product demand, source breakdown, response/conversion time), Inquiries (split-panel workflow), Products (CRUD + AI bulk import/inventory update)
- AI-assisted bulk product import from pasted price lists and bulk inventory updates (qty/cost/sale price) from free text

### Phase 7 — Session Connection Reliability (complete)
- Diagnosed and fixed QR/session connections silently hanging forever with no error ever surfacing (root cause: no timeout existed anywhere in the handshake path, and `createSession` no-op'd on a stuck-but-present socket)
- Connection watchdog (§17.1): 45s timeout armed after socket creation, re-armed on every QR refresh, cleared on connect — fires `SESSION_STATUS.ERROR` with a human-readable `lastError` if the handshake goes silent
- Pre-socket-creation failures (corrupted auth state, Baileys version-fetch failure) now caught and routed to the same `error` state instead of leaving the session stuck at `pending_qr`
- `GET /sessions/:id/qr` returns HTTP 500 with the error detail instead of an endless 202 once a session errors
- `QRModal.vue` — removed the "keep polling silently" fallback; every failure path now stops polling and shows an actionable message instead of spinning forever
- Not yet done: no auto-retry after the watchdog fires (user must reopen the QR modal to retry — this now actually works since the watchdog nulls the stuck socket)

### Phase 8 — Trading UX & Observability Polish (complete)
- WhatsApp deep-link actions on inquiry cards now prefill the compose box instead of just opening the chat: **WA** (item + our sale price), **Ask Price** (item + `Price?`, WTB and WTS), **Price List** (WTB only — every active in-stock product as `Name - Price`). Still never auto-sends — WhatsApp's `text=` param only prefills.
- AI buy/sell classification prompt hardened with an explicit ordered disambiguation ruleset (WTB/WTS tag > offer language > price-check template > default-to-buy) — ambiguous multi-variant price-check messages were sometimes misread as sell offers based on variant count alone.
- **AI Parsing Log** (`trading_ai_parsing_log`, §6.13): every live message now gets an auditable sent/skipped routing record instead of skipped messages silently vanishing. `_should_classify` replaced by `_classify_skip_reason`, which returns the reason instead of a bare bool.
- **Dropped-message recovery tracking**: `whatsapp_dropped_message.resolved_at` is stamped when a later message with the same `msg_id` ingests successfully (Baileys' automatic retry-request succeeded) — the Dropped Messages screen now distinguishes self-healed drops from permanent loss instead of both looking identical.
- **LID/username cache seeding on restart**: new `GET /api/internal/whatsapp/lid-mappings/:id/` endpoint seeds the worker's in-memory `lidToPhone`/`usernameToPhone` maps from already-known DB contacts when a session is restored, closing the gap where a worker restart reset the cache to empty and caused `unresolvable_lid` drops for senders that were already known.
- Product Master: added a per-product **Margin** column (sale − cost) and a **Total PNL** summary badge (Σ margin × qty, filter-aware); removed the Aliases column from the table (alias editing moved to the modal's existing "Advanced" section, unchanged).
- Top nav regrouped into hover dropdowns to stop the bar overflowing as screens were added (§16): **Lists** (Contacts/Groups/Products), **Settings** (Sessions/Storage/AI Providers/AI Instructions), **Logs** (Activity/Message Logs/Dropped/AI Parsing Log).

### Phase 9 — Supplier/Customer Categorization & Product-Match Trust (complete)
- Contacts can be tagged **supplier**/**customer**/**both** (`whatsapp_contact.category`) — inline on the Contacts page (now also sortable server-side) or as a quick action on trading inquiry cards.
- **Buying Inquiries** (§6.14): manual purchase requests shopped around a supplier list, with per-supplier Ask Price / Log Quote / No Stock tracking.
- **"Incorrect Match" inquiry status** (10th state) — selecting it opens an inline reason prompt instead of saving immediately, stored in `remarks`.
- **AI category suggestions**: classification receives the contact's existing category as prompt context and may propose an update (e.g. tagged supplier, this message shows them buying → suggest "both") — instruction-only, no code-side logic; the suggestion pre-fills (never auto-applies) the card's category dropdown.
- **Product match-confidence contract** (`match_type`: `exact`/`near`/null) added to classification, driven entirely by prompt hardening after three real incidents traced to the same root pattern — a "close enough" catalog entry (wrong tier suffix, wrong color, or a genuinely missing variant) being confidently reported as `"exact"`: tier suffixes ("Pro" vs "Pro Max") now count as part of the model name, all of model/storage/color/region must match for `"exact"`, and a mandatory word-by-word self-check against the literal product master list was added since restating the rule alone wasn't enough to stop the model defaulting to "only candidate available = must be it."
- Product master sent to the AI is now filtered to `qty > 0` — a zero-stock item is never offered as a match at all, `exact` or `near`.
- Course-corrected an architectural misstep on the frontend: `TradingView.vue` briefly re-verified `match_type` with its own exact-string product-name comparison before trusting a price, duplicating the same fuzzy-matching judgment call the AI is already paid to make, with a strictly worse tool — it produced its own false positive within one incident (bare "Apple " brand prefix). Reverted to trusting `match_type` directly.
- Fixed a live-pipeline bug where an uncaught embedding-provider exception silently skipped classification entirely for that message (found affecting ~30% of live messages across dozens of chats during one provider rough patch) — the embed call is now isolated in its own try/except so a failure there can never block classification.
- WhatsApp prefill text (WA / Ask Price buttons) no longer echoes the customer's requested quantity back to them.

### Phase 10 — Trading Reliability & Cost Controls (complete)
- **Inquiry card redesign**: fixed-size header/body/footer layout, header collapsed to a single row across three iterations of feedback, body redesigned into exactly 3 fixed-height click-to-expand/collapse rows (Summary, Original Message, Stock Suggestion). New `source_message_text` field on the inquiry serializer surfaces the verbatim original message (previously only the AI summary was available to the frontend).
- **Stock Suggestion / WA-quote qty fix**: both the card's Stock Suggestion row and the outgoing "WA" price quote used to treat a saved `sale_price` as proof of stock regardless of actual `qty`, showing a false ✓ "in stock" (and quoting a price) for zero-quantity products. Both now require `qty > 0`.
- **`matchInventory()` trust-boundary fix**: extended the Phase 9 principle — the frontend's product matcher used to fall back to a substring search over `canonical_name` whenever the AI returned `product_id: null`, silently inventing a confident match the AI had explicitly declined to make. It now does nothing but look up `product_id`.
- **Further `match_type` prompt hardening**, driven by real incidents traced the same way as Phase 9's: a UAE-vs-USA region rule (the two words are lexically similar and were being conflated), a rule against guessing an unrecognized region abbreviation (e.g. "jv" silently read as Japan), a rule against treating a bare short numeric reply as a reference to a product master ID, and a **MANDATORY ENUMERATION STEP** — the AI must now explicitly enumerate every catalog candidate sharing model+storage before assigning `product_id`, and when two or more candidates each match a *different* single attribute of the request (one matches color, another matches region, neither matches both), `product_id`/`match_type` must both be `null` rather than picking one and calling it `"exact"`.
- **Backend self-consistency check** (`_validate_exact_matches`, §12): after three rounds of prompt hardening still didn't fully stop self-contradictory `"exact"` claims (canonical_name disagreeing with the catalog entry actually linked), added a narrow code-side check — not a re-match, just a word-for-word agreement check between the AI's own `canonical_name` and its own linked product's real name — that downgrades `match_type` to `"near"` on disagreement before saving.
- **WA reply prefill** now leads with the sender's original message verbatim, then the priced item list, instead of the item list alone with no context of what was actually asked.
- **AI-formatted price list** (§6.15, §6.11, §11.3): a 4th editable prompt (`price_list_format`) turns the current in-stock catalog into a WhatsApp-ready formatted price list on demand (Products screen, manual "Regenerate" button — never automatic). The "Price List" button on inquiry cards now sends this stored, reviewed text verbatim instead of building a plain `Name - Price` list ad hoc on every click.
- **Live feed pagination fix**: `open-feed` used to silently cap results at 50 combined WTB+WTS records with no indication of truncation — a desk with hundreds of open inquiries only ever saw the newest 50, oldest ones invisible. Now returns a true `count` and supports a `type` filter; WTB/WTS paginate and infinite-scroll independently in the frontend.
- **Cross-group broadcast dedup** (§12): traders posting the identical WTB/WTS list to many different groups within minutes used to trigger a full AI classification call for every repost. A new `duplicate_broadcast` skip reason, using the same embedding-similarity mechanism as the existing same-contact dedup but scoped account-wide across groups (not restricted to the same contact or group) within a 1-hour window, now catches these before they reach the AI at all.

### Phase 11 — Prompt Integrity & Worker Stability (complete)
- **Broken AI Instructions prompt override incident** (§6.11): a saved `inquiry_classification` override contained only a block of additional safety rules with none of the base prompt underneath — no output schema, no `{product_block}` injection point. Every classification silently returned `is_inquiry: false` for real WTB/WTS messages for hours, with no error anywhere (the AI free-formed a different JSON shape per call; `_parse_response`'s permissive `.get(..., default)` calls quietly absorbed the malformed responses instead of failing loudly). Root-caused via `AgentCallLog.raw_response` inspection across several recent calls, each showing a wildly different, schema-less JSON shape. Fixed by deleting the broken override and merging its genuinely new rules (hard SIM-type exclusions, broader forbidden-tier-inference coverage beyond Pro/Pro Max, a rule against inferring region from stock/product_id existence) into `INQUIRY_CLASSIFICATION_DEFAULT` directly, so they're not lost to a future reset.
- **Connection-health detection: built, caused a production incident, reverted** (§17.2 has the full writeup). Attempted to detect degraded WhatsApp sessions (repeated Signal-protocol decrypt failures / handshake timeouts — confirmed via `baileys-internal.log`: 570 decrypt failures and 61 handshake timeouts on one real account, "connected" in the DB the whole time despite receiving nothing for ~36 hours) by wrapping pino's log destination with an incomplete plain-object stream. Real pino destinations implement several methods (`flushSync`, `flush`, `on`, `reopen`, `end`, `destroy`) that the plain wrapper didn't — something called one of them and threw uncaught deep inside Baileys' internals, hanging live sessions and breaking their ability to disconnect. Reverted fully rather than patched; the DB/API/UI plumbing (`connection_unhealthy` fields, `sync-progress` response fields, the `AccountCard.vue` banner) was left in place since it's inert without a detection call site, ready for a safe reimplementation via pino's `hooks.logMethod` instead of destination-wrapping.
- **Disconnect endpoint self-correction**: `POST /api/accounts/:id/disconnect/` used to relay the worker's response verbatim, including a 404 "Session not found," without ever correcting Django's own stale `session_status` — leaving an account permanently stuck showing a Disconnect button that could never succeed. Now flips `session_status` to `disconnected` automatically whenever the worker reports no session exists, verified by re-simulating the exact broken scenario (DB said `connected`, worker said 404 → DB now self-corrects to `disconnected`).

### Phase 12 — Prompt Consolidation (complete)
- **Root cause**: after many rounds of incremental hardening (Phase 9, 10, 11), `INQUIRY_CLASSIFICATION_DEFAULT` had grown to 16,548 characters with substantial redundancy — three separate, overlapping sections independently re-explaining "check every attribute before calling it exact" (`CRITICAL EXACT-MATCH RULE`, `MANDATORY ENUMERATION STEP`, `MANDATORY SELF-CHECK`), several near-duplicate worked examples of the same underlying mistake, and multiple separate "forbidden inference" lists. This coincided with a fresh, severe regression: a real inquiry (6 requested iPhone variants, 5 of which existed in stock with exact catalog matches) came back with `product_id: null` on every single line — confirmed via direct testing that the AI could write the *correct* catalog name into `canonical_name` while still failing to link it, and a controlled single-item test showed the same model additionally mismatching a simple, unambiguous request (asked for Orange, linked to the Silver catalog entry, called it `"exact"`). Diagnosis: prompt bloat itself, not a missing rule, degrading basic instruction-following.
- **Fix**: rewrote `INQUIRY_CLASSIFICATION_DEFAULT` down to a single consolidated 7-step `MATCHING PROCEDURE` (enumerate → score color/region → exact/near/null decision tree → self-check) replacing the three overlapping sections, condensed the SIM-type hint/exclusion rules into one section, and cut redundant worked examples down to one per concept. Net: **7,945 characters** for the rewrite (before a further reinforcement below), roughly half the original — same rule coverage, no rule dropped.
- **Regression found during verification, fixed same session**: re-testing against every documented failure case from Phase 9–11 (UAE-vs-USA, HK-vs-UAE, unrecognized region, bare digit, bare model code, plus the fresh 6-item and single-item cases) showed most were now fixed, but surfaced a new one: in genuinely ambiguous "two candidates, each off by a different attribute" cases, the model was silently rewriting `canonical_name` to match whichever candidate it leaned toward instead of preserving the original request — worse than the original bug in that specific way, since `canonical_name` integrity is meant to be inviolable regardless of match outcome. Fixed by adding an explicit standing rule at the top of `MATCHING PROCEDURE` ("canonical_name is a transcript of what the sender wrote, never of whichever catalog entry you end up picking or rejecting") plus a concrete worked example matching the exact failure pattern. Re-verified: `canonical_name` preservation held on retest for both cases; the underlying match_type still isn't 100% reliable on this specific two-candidates-same-attribute-different-values sub-case (a gap not fully covered by the existing rule set), but every residual case was confirmed to get caught and downgraded from `"exact"` to `"near"` by the existing `_validate_exact_matches` backend safety net (§12) before ever reaching the database — verified directly, not assumed.
- **Net effect**: shorter, less redundant prompt; the 6-item null-everything regression is fixed; no case tested resulted in a false-confident `"exact"` or a silently corrupted `canonical_name` reaching the frontend, whether from the prompt's own correctness or the backend safety net catching what it doesn't.

### Phase 13 — Product Embedding Infrastructure (complete, not yet load-bearing)
- New `product_embedding` table (§6.5.1) and `embed_product`/`embed_products_batch`/`find_similar_products` in `apps/message_intelligence/services/embedding_service.py`, mirroring the existing message-embedding pattern exactly (same background-thread, fire-and-forget approach; a provider hiccup never blocks a product save).
- Wired into `ProductViewSet.perform_create`/`perform_update`/`bulk_create` (`apps/trading/views.py`) so every product gets embedded the moment it's created or edited — built ahead of an anticipated catalog-growth need, not because the current ~30-product catalog requires it.
- Backfilled all existing active products (30/30, zero errors).
- **Deliberately not wired into classification** (§12, "Product retrieval"): confirmed via direct testing that embedding similarity alone isn't precise enough to make the exact/near/null call itself — querying for a specific color+region variant put the *wrong*-color/region variants within 0.06–0.09 cosine distance of the correct one (0.0134), far too close to trust a threshold. This infrastructure exists so that when the catalog does grow large enough that sending the full text list becomes impractical, retrieval can narrow to top-K candidates *before* prompt-building — the AI still does the final precise attribute comparison on that narrowed text list, same as today.

### Phase 14 — Silent Message-Loss Audit & Worker Alerts (complete)
- **Root cause**: a real report of a contact's recent messages not appearing anywhere — not even the drop log — traced to a Signal-protocol decrypt failure for that one contact's session. Baileys decrypts internally *before* ever emitting `messages.upsert`, so a failure there never reaches `_buildPayload`/`_reportDropped`; the only trace was an unstructured line in `baileys-internal.log` nobody was watching. Requested: a full audit for the same *category* of bug across the whole ingestion pipeline, and a root-cause fix — not a fix for that one contact's record.
- **Audit** (background agent, read-only) found the decrypt blind spot applies identically to history-sync messages (same Baileys logger, same mechanism), plus: `_forwardHistoryBatch` silently skipping build failures with no `DroppedMessage` row (also affects reconnect-redelivered live messages via the `'prepend'` branch); Django batch-ingest losing message content on a per-item persistence failure with only an aggregate error count; the worker blindly marking an entire batch chunk "delivered" even when Django's response reported partial failures; the drop-reporting safety net itself failing silently at `debug` log level when Django was unreachable; no process-level exception handler anywhere in the worker; and one concrete instance of it (`jidNormalizedUser` outside a protecting try/catch in the contacts handler, silently losing alias mappings for an entire batch on one malformed entry).
- **New `whatsapp_worker_alert` table** (§6.7.1): a structured, queryable, UI-visible record for this whole class of failure, populated immediately per-occurrence (not thresholded/batched) — the direct fix for "should not fail silently, a log should be created."
- **Decrypt/handshake detection rebuilt safely**, learning directly from the pino-destination-wrapping incident that broke production earlier this same investigation (§17.2 has the full postmortem): uses pino's `hooks.logMethod` instead, which intercepts log calls without ever touching the destination stream contract. Verified in isolation — mocked `SessionManager`, fed real captured log line shapes, confirmed correct pattern matching and correct once-only threshold escalation — before being wired into the live session path.
- **Six other fixes**, each verified individually against a real or simulated failure, not just reasoned about: history-batch build failures now report `history_build_error`; Django batch-persist failures now preserve the full original payload in `DroppedMessage.raw_key` and raise a `batch_partial_failure` alert; the worker now inspects batch-response error counts instead of assuming any non-throw means full delivery; `sendDroppedMessage`/`sendWorkerAlert` now log failures at `warn` (not `debug`) and fall back to a local `failed-reports.ndjson` file when Django is unreachable; `index.js` now has `uncaughtException`/`unhandledRejection` handlers writing a durable `process-errors.ndjson` record (deliberately not crashing the process — see §17.2 for the reasoning); the contacts handler's `jidNormalizedUser` call is now wrapped per-contact instead of aborting the whole batch.
- **New Worker Alerts screen** (§16, `/worker-alerts`) plus a red unacknowledged-count badge on the top nav's **Logs** dropdown, polled every 30s — visible from anywhere in the app, satisfying "admin should be notified" without requiring anyone to already know to look for it.

### Phase 16 — Trading Analytics Date Range & Housekeeping (complete)
- **Trading Analytics date-range filter** (§11.3, §16): a new `_resolve_date_range(request)` helper shared by `/inquiries/stats/`, `/products/stats/`, and `/inquiries/classification-activity/` accepts optional `date_from`/`date_to`, defaulting to "today" when neither is given — deliberately preserving the exact prior behavior for the Trading Dashboard's stat chips, which share the same `/inquiries/stats/` endpoint and never pass a range. Frontend adds a 10-shortcut dropdown (Today, Yesterday, This/Last Week, This/Last Month, This/Last Quarter, This/Last Year, default Today) computed client-side. The activity timeline switches from fixed 24 hourly buckets to adaptive granularity — hourly for a single-day range, daily for anything longer (`timeline_granularity` in the response) — since 24 hourly bars either collapse to one lump or become absurdly wide once the range spans weeks.
- **Close-stale-inquiries housekeeping**: `POST /inquiries/close-stale/` bulk-closes every `status=open` inquiry older than a given number of hours (optionally scoped to account), surfaced as an hours-input + button in the Trading Dashboard header. Only ever touches `open` records — can't undo any other status decision.
- **Testing mistake, caught and fully reverted**: while verifying `close-stale` against real data, an initial test call was scoped too broadly (matched a real account instead of an isolated test row) and closed 24 genuinely-open inquiries for a few minutes. Caught immediately; the exact 24 rows were identified via the shared bulk-`.update()` timestamp fingerprint (a single `.update()` call stamps every affected row with the identical microsecond-precision `closed_at`, which is what made isolating exactly these rows — and no others — possible) and reverted to `open`/`closed_at=null`. Disclosed directly rather than left unmentioned. Root cause was insufficiently isolated test data, not a bug in the endpoint itself — the endpoint's own logic (scoped to `status=open` + age threshold, unauthorized to touch anything else) worked exactly as intended both times.

### Phase 17 — Human-in-the-Loop Match Correction (complete)
- **Root cause investigated on request** ("agent is failing too frequently in matching the items"): sampling recent `near`-match inquiries against their actual catalog entries found that roughly 29% (42 of 147 checked) were **cosmetic-only** false negatives — missing a "GB" unit suffix, missing the "iPhone"/"iPad" brand word, or plain casing differences between the customer's phrasing and the catalog name — not genuine attribute mismatches. Traced to two independent places doing the identical too-literal word-by-word string comparison: the classification prompt's own step-7 self-check ("if even one word differs, downgrade") and the backend `_validate_exact_matches` safety net (§12) — fixing only one would have left the other silently re-downgrading the AI's now-correct answer. Both rewritten to compare **attribute-by-attribute** (model/tier/storage/color/region) instead of literal word-for-word, explicitly excusing unit-suffix and brand-word differences (`_normalize_attribute_words` in `classification_service.py`) while still catching genuine attribute differences (verified against both a cosmetic-only case and two genuine-mismatch cases, all three behaving correctly after the fix).
- **"Fix" and "Auto" match-correction UI** (§16, Trading Dashboard): a mismatch ("closest match only") stock-suggestion pill now carries two buttons. **Fix** opens a searchable product picker; ticking a candidate calls the new `POST /inquiries/:id/correct-match/` (§6.10, §11.3), which sets that line's `match_type='exact'` directly — the pill turns green automatically since it's now reading the same `match_type` field as any AI-confirmed match, no separate "manually confirmed" visual state needed. **Auto** runs a client-side direct name/alias search over the already-loaded catalog first (instant), falling back to the embedding-based `GET /products/search-embeddings/` (§6.8.1) only when that's empty — results are tagged `exact` or `~NN% match`, but still require a human tick to apply; consistent with the standing rule that embeddings/AI narrow candidates, they don't decide.
- **Manual 1–5 classification rating** (§6.10, `classification_rating`, migration `0014`): five small buttons in each inquiry card's footer, defaulting to 5 so a reviewer only has to touch the ones that are actually wrong instead of confirming every single inquiry — no aggregate reporting view built yet (filtering/analytics on this field is a natural next step, not yet requested).
- **Deferred to a later phase, by explicit request**: wiring a "Fix" correction to optionally save the customer's phrasing back as a new alias on the corrected product, so the same mistake doesn't need re-correcting next time it's phrased the same way.

### Phase 18 — Popup/Modal UX Overhaul (complete)
- **Row-expand popup** (Trading Dashboard Summary/Original Message/Stock Suggestion): rebuilt from growing in place inside the card (which left dead space for short content and made cards jump around in the feed) into a centered `Teleport`-based dialog, doubled in size, **draggable** by its header (tracked as a cumulative translate offset from center, not absolute viewport coordinates, so no `getBoundingClientRect` measurement is needed), with a dedicated small "×" close button.
- **Removed both "closes on click" behaviors, traced to one root cause**: a leftover global `document` click listener from the pre-popup design (originally meant to collapse the old in-place expansion when clicking elsewhere) fired on *any* click anywhere on the page — including inside the popup itself, since `Teleport` renders into `<body>` and clicks still bubble to `document`. That single listener was causing both "clicking on it closes it" and "clicking outside closes it"; removing it fixed both at once.
- **Same treatment applied to the "Fix match" product-picker dialog** (§20 Phase 17) and, in Phase 20, the **Product Add/Edit modal** — doubled size, draggable, no outside-click-close, dedicated close button — establishing this as the standard pattern for every popup dialog introduced from here on.
- **Two CSS bugs found and fixed during the Product modal work**: (1) `.form-group input` never had `width: 100%`, so inputs kept the browser's default intrinsic width regardless of how narrow their grid cell actually was; (2) multi-column grid rows used bare `1fr` tracks, which have an implicit `min-width: auto` and refuse to shrink below their content's minimum size — combined, a 4-input pricing row silently overflowed outside its card border once the two-column redesign made each card narrower than the old single-column layout. Fixed by adding `width: 100%; box-sizing: border-box` to inputs and switching every multi-column `.form-row` variant to `minmax(0, 1fr)` tracks.
- **Close button placement bug**: the header's `flex-direction` override was incomplete — `.product-modal-head` reset `display`/padding/background but never reset `flex-direction` back to `row`, so it inherited `column` from the shared base `.modal-head` class and the "×" button stacked below the title instead of sitting beside it. Fixed by explicitly setting `flex-direction: row`.
- **Alias chip input gained Backspace-to-remove**: pressing Backspace with the input empty removes the most recently added chip (checks not-yet-persisted ones first, then falls back to already-saved ones), matching the Gmail "To:" field convention — only triggers on an empty input, so normal typing is unaffected.

### Phase 19 — Worker Alerts Bug Fix & Stuck Receipts (complete)
- **`WorkerAlertSerializer` list-endpoint bug** (§6.7.1): `account_name = serializers.SerializerMethodField()` was declared with no matching `get_account_name` method — every `GET /api/worker-alerts/` request that had any rows to serialize (i.e. essentially always) crashed with a 500, silently swallowed by the frontend's bare `catch {}`. The nav badge showed the real count (54) via a separate, simpler `.count()` query untouched by the bug, while the table underneath showed nothing — the mismatch is what surfaced it. Predates this session's other changes; never caught earlier because every prior verification queried the DB directly rather than through the actual endpoint. Fixed by adding the missing method.
- **Live worker-alert investigation, on request**: found the day's decrypt-failure volume was mostly the already-understood post-relink Signal-session-rebuild churn (tapering hourly), plus a live, actively-recurring crash loop distinct from anything previously diagnosed — see below.
- **New `whatsapp_stuck_receipt` system** (§6.7.2): traced a repeating "error in sending message again" crash to Baileys' own internal retry-receipt handling failing on a self-sync message with an empty message-key id, confirmed by reading Baileys' source directly — each occurrence first makes a real, unconditional network round-trip to WhatsApp (`assertSessions(..., force=true)`) before crashing, so a rapid burst (10 in 10 seconds observed live) was both crashing repeatedly *and* generating wasted live requests to WhatsApp's servers. Fixed the *reachable* part safely: the existing pino log-inspection hook now also records the stuck message and adds it to an in-memory per-session skip-list; the worker's `getMessage` callback (previously an unconditional stub for every key) returns `null` for anything already on that list, so Baileys takes its own documented "message not available" path instead of attempting the same doomed resend again. Deliberately did **not** attempt to intercept `assertSessions` itself, which would require removing/replacing Baileys' internal event-listener wiring — the same category of change that caused the §17.2 production incident.
- **New Stuck Receipts screen** (§16, `/stuck-receipts`) plus an unresolved-count nav badge, same pattern as Worker Alerts.

### Phase 20 — Product Alias Architecture Overhaul (complete)
- **`ProductAlias` model replaces the `aliases` JSONField** (§6.8, §6.8.1, migrations `0015`–`0017`): the real motivation is **per-alias embeddings**, not just data-modeling tidiness — a single blended `{brand} {name} {aliases}` vector per product averages every distinct phrasing together, which can actually sit *further* from a customer's exact wording than any single alias embedded on its own would. `find_similar_products()` now does multi-vector retrieval: compares a query against a product's own name embedding **and** every one of its aliases' embeddings independently, keeping only the single best (lowest-distance) match per product regardless of which vector won — verified with crafted test vectors showing a product whose own name embedding was deliberately far from the query still ranked first via one of its aliases.
- **Alias CRUD** (`GET`/`POST /products/:id/aliases/`, `DELETE /products/:id/aliases/:alias_id/`): each add/remove is its own live API call, independent of the main product save; each addition queues its own background embedding.
- **Embedding-status visibility & backfill** (§6.8.1): background embedding failures (provider rate-limit, etc.) were previously invisible — only a console warning, nothing persisted. Found in practice: two aliases added through the real UI came back with no embedding; calling the embed function directly worked immediately, confirming a transient hiccup rather than a code bug, but with zero durable trace it would have stayed silently broken otherwise. Rather than add a separate failure-log table, the "missing an embedding" state itself became the durable, actionable signal: `GET /products/embedding-status/` reports coverage counts, `POST /products/backfill-embeddings/` synchronously re-embeds everything missing and returns real counts, and the Products screen shows an aggregate badge plus per-row **Product Embedding**/**Alias Embeddings** columns so a specific gap can be pinpointed without cross-referencing anything.
- **Product Add/Edit modal redesign** (§16, §20 Phase 18): reorganized into card-style sections (Basic Info / Pricing & Stock / Aliases) with a live interactive alias chip input, replacing the old single free-text "Advanced" textarea — and given the same doubled-size/draggable/no-outside-click-close treatment as the Trading Dashboard popups (Phase 18).

### Phase 21 — ML Intelligence (planned)
- Lead scoring
- ERP product master integration / two-way sync
- Cross-account analytics rollups

### Phase 22 — Message Preservation & Outbound LID Hardening (complete)
- New `whatsapp_unresolved_message` table (§6.7.3, migration `0022_unresolved_message`) — a chat-level LID that can't be resolved no longer means the message is discarded; it's preserved with full content and automatically recovered once the mapping becomes known.
- Third LID resolution source: a persisted single-LID Django lookup (§13, §10) closes the gap that used to leave outbound self-echoes dependent solely on a volatile in-memory cache.
- Two new internal endpoints (`unresolved-message`, `lid-mapping`), one new public read-only viewset + frontend page (`/unresolved-messages`, §16), deliberately no local-file fallback on the new endpoints' failure path (§6.7.3) — a persistence failure is always explicit (`WorkerAlert`), never silently assumed safe.
- First automated test coverage added to this codebase: `apps/whatsapp_bridge/tests.py` (Django, 17 tests) and `whatsapp-worker/test/session-manager.test.js` (Node's built-in `node:test`, 11 tests, `npm test`).
- Full design rationale, evidence, and what remains explicitly out of scope (the unrelated inbound zero-trace mystery, and two still-pending fallback/suppression fixes) in `docs/Contact Message Loss — LID Resolution Fix Proposal.md`.
