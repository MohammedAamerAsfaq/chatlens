# ChatLens Development Document

> **Status:** Living document — reflects the system as actually built, not the original plan.
> Last updated: 2026-07-08 (contact categorization, Buying Inquiries, product match-confidence contract, embed-failure isolation)

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

### 6.8 trading_product

Product master used for AI matching (aliases) and inventory tracking. No LIKE/fuzzy queries against `aliases` — matching is entirely AI-driven at classification time. Only `is_active=True AND qty > 0` rows are sent to the AI as the product master block (`product_cache.get_product_prompt_block()`) — a product with zero stock is never offered as a classification match, `exact` or `near`, even if it's otherwise a perfect spec match. Product Master screen also shows a per-product Margin column and a filter-aware Total PNL badge (Σ margin × qty), and supports inline click-to-edit on Qty/Cost/Sale directly in the table.

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| name | varchar(255) | |
| brand | varchar(100) | |
| category | varchar(100) | |
| sku | varchar(100) | |
| aliases | jsonb (list) | free-text aliases traders use, e.g. `["17PM", "17 Pro Max"]` |
| is_active | boolean | soft-delete flag |
| qty | integer | inventory quantity |
| cost_price | decimal(12,2) nullable | |
| sale_price | decimal(12,2) nullable | |
| currency | varchar(10) | default `USD` |
| created_at / updated_at | timestamptz | |

### 6.9 trading_message_classification

One row per classified `WhatsAppMessage`. Created by the AI classification service after every successful call.

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| message_id | FK → whatsapp_message, one-to-one | |
| tags | jsonb (list) | one or more of `wtb`, `wts`, `price_inquiry`, `stock_inquiry`, `negotiation`, `deal_confirmation`, `greeting`, `joke`, `spam`, `other` |
| products | jsonb (list) | `[{product_id, match_type, canonical_name, quantity, price, currency}]` snapshot at classification time. `match_type` is `"exact"` (all of model/storage/color/region matched a catalog entry), `"near"` (product_id references the closest available entry, but at least one attribute — including model tier suffix like "Pro" vs "Pro Max" — differs from what was requested), or `null` (no confident match; `product_id` is also null in that case) |
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

Operator-editable overrides for the three AI prompts used by the trading pipeline. Falls back to the built-in default body when no row exists for a key.

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| key | varchar(100), unique | `product_extraction`, `inquiry_classification`, or `inventory_update` |
| label | varchar(200) | |
| body | text | the prompt text sent to the AI |
| updated_at | timestamptz | |

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
| skip_reason | varchar(30) | blank when `status=sent`; else one of `no_text`, `outbound`, `too_old`, `chat_disabled`, `account_disabled` |
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
| `unresolvable_lid` | sender JID is a LID but neither `senderPn`/`participantPn` nor the session cache can resolve it to a phone JID |
| `forward_failed` | Django returned an error on `message-ingest` |
| `build_error` | unexpected exception in `_buildPayload` |
| `messageStubType:N` | WhatsApp group notification stub (member joined, left, etc.) |

`senderKeyDistributionMessage` is only dropped when the field is the **sole content** of `msg.message`. If a real message is bundled in the same envelope (combined envelope), the key distribution field is stripped and the message passes through.

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
| POST | `/api/internal/whatsapp/contacts-update/` | Contact names from `contacts.set` / `contacts.upsert` |
| POST | `/api/internal/whatsapp/dropped-message/` | Fire-and-forget drop notification |
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
| POST | `/api/accounts/:id/disconnect/` | Disconnect session |
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
| GET/POST/PATCH/DELETE | `/api/products/` | Product CRUD |
| POST | `/api/products/parse-text/` | AI-extract products from a pasted price list |
| POST | `/api/products/bulk-create/` | Bulk-create parsed products |
| POST | `/api/products/parse-inventory/` | AI-extract qty/cost/sale price from free text |
| POST | `/api/products/bulk-update-inventory/` | Apply parsed inventory update |
| GET  | `/api/products/stats/` | Per-product WTB/WTS counts |
| GET/PATCH | `/api/inquiries/` | Inquiry list/detail + status/remarks update |
| GET  | `/api/inquiries/stats/` | Dashboard aggregates |
| GET  | `/api/inquiries/open-feed/` | Live feed of open inquiries |
| GET  | `/api/inquiries/classification-activity/` | Recent classification events (diagnostics) |
| POST | `/api/inquiries/retry-inquiries/` | Re-run classification for failed/skipped inquiries |
| POST | `/api/inquiries/backfill-classify/` | Classify recent unclassified messages (<24h old) |
| GET  | `/api/classifications/` | Read-only classification records, filterable by message |
| GET/PATCH/DELETE | `/api/prompts/` | Prompt override CRUD |
| GET/PATCH | `/api/prompts/active-agent/` | Active AI agent/model config for trading |
| GET  | `/api/agent-logs/` | AI call audit log (tokens, duration, success/error) |
| GET  | `/api/ai-parsing-logs/` | Per-message sent/skipped routing log (§6.13), filterable by `account`/`status`/`skip_reason` |
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

_forwardHistoryBatch:
  1. _buildPayload for each message (isHistory=true, no media download)
  2. djangoClient.sendMessageIngestBatch
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
                no_text | outbound | too_old (>24h) | chat_disabled | account_disabled
           - AiParsingLog.objects.update_or_create(message=..., status=sent|skipped, skip_reason=...)
           - if not skipped → classify_message(message)
```

`_classify_skip_reason` replaced the old boolean `_should_classify` — same rules (chat-level tri-state override wins, else the account's `ai_parsing_enabled` default), but it now returns *why* instead of just true/false, so every routing decision is auditable via `trading_ai_parsing_log` (§6.13) instead of silently disappearing for skipped messages.

History-sync batch messages (`ingest_batch`) are still embedded but never classified or logged to `trading_ai_parsing_log` — they would all read as `too_old` and just add noise.

**Classification prompt context:** `classify_message` passes the sender's *existing* `whatsapp_contact.category` into the prompt (`"not set"` if blank) alongside the product master block (§6.8, now qty>0 filtered) — see §6.9 for the resulting `suggested_contact_category` output and §6.9's `match_type` field for the exact/near/null product-matching contract. Both are prompt-instruction-only mechanisms; no code-side matching or validation logic re-derives them (see below).

**Frontend trust boundary:** `TradingView.vue` used to independently re-verify `match_type` with its own exact-string-name comparison (`isReliableMatch`) before trusting a matched product's price — this duplicated the same fuzzy-matching problem the AI is already paid to solve, with a strictly worse tool, and produced its own false positive (brand name written as a bare prefix, e.g. "Apple iPhone..." vs the catalog's brand-less "iPhone..."). `isReliableMatch` now does nothing but read `match_type !== 'near'` — the AI's verdict is authoritative; `stripBrandPrefix` remains only for cosmetic cleanup of the outgoing WhatsApp text, never for match verification.

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

1. `msg.key.senderPn` — Baileys-provided real phone JID for inbound individual LID chats
2. `msg.key.participantPn` — Baileys-provided real phone JID for LID group participants
3. `session.lidToPhone` — in-memory cache populated from `contacts.set` / `contacts.upsert` at connect time and updated whenever a `senderPn`/`participantPn` is seen. Also **seeded from the DB** (`GET /api/internal/whatsapp/lid-mappings/:id/`, built from existing `whatsapp_contact.lid_jid`/`username` rows) when a session is restored on worker restart, so the cache isn't cold immediately after a restart — previously it rebuilt from scratch and dropped `unresolvable_lid` for senders that were already known contacts until a fresh `contacts.set` repopulated it.

### Strict rule

If a LID cannot be resolved to a phone JID via any of the above, the message is dropped with reason `unresolvable_lid`. Creating a phantom `@lid` contact in Django is explicitly forbidden.

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

Top nav is grouped into three hover dropdowns (`App.vue`) to keep the bar from overflowing as screens were added — **Lists**, **Settings**, and **Logs** — each highlights as active when the current route is one of its children. Everything else stays a flat top-level link.

| Route | Screen | Nav placement | Purpose |
|---|---|---|---|
| `/login` | Login | (public, no nav) | Session auth gate — only unauthenticated screen |
| `/conversations` | Conversations | top-level | Chat list + message view, WhatsApp deep-link ("open in WhatsApp") on messages/chats |
| `/trading` | Trading Dashboard | top-level | Live WTB/WTS feed, open-inquiry cards with status actions, urgency indicators. Per-card WhatsApp actions (all prefill the compose box via `text=`, never auto-send, and never include the customer's requested quantity in the text): **WA** — item(s) + our sale price (only when `match_type !== 'near'`); **Ask Price** (WTB + WTS) — item(s) + blank line + `Price?`; **Price List** (WTB only) — every active in-stock product as `Name - Price`. Stock hints turn amber with a ⚠ when the matched inventory item is only a `"near"` match, instead of the normal green ✓. Each card also has a quick contact-category selector (Uncategorized/Supplier/Customer/Both) that pre-fills with the AI's `suggested_contact_category` when one is pending, applied with one click; category-save failures show a dismissible error banner rather than failing silently. "Incorrect Match" status opens an inline reason prompt instead of saving immediately |
| `/trading-analytics` | Trading Analytics | top-level | Product demand, source breakdown, hourly activity, response/conversion time |
| `/buying-inquiries` | Buying Inquiries | top-level | Manually create a purchase request (§6.14); auto-populates a card per tagged supplier with Ask Price / Log Quote / No Stock actions and a status badge per supplier |
| `/contacts` | Contacts | under **Lists** | Contact management, display name editing, LID/username alias display, per-contact AI-parse toggle, supplier/customer/both category tagging (filterable), sortable columns (Display Name/WhatsApp Name/Phone/Category/Msgs, server-side via `ordering`) |
| `/groups` | Groups | under **Lists** | Group/community list, sync trigger, per-group AI-parse toggle |
| `/products` | Products | under **Lists** | Product master CRUD, AI bulk-import from pasted price lists, bulk inventory update via AI. Table shows Qty/Cost/Sale/**Margin** (sale − cost) per product and a **Total PNL** badge (Σ margin × qty across the visible/filtered rows); the Aliases column was dropped from the table (still editable under "Advanced" in the Add/Edit modal). Qty/Cost/Sale/Currency are directly editable in the Add/Edit modal, plus inline click-to-edit on the Qty/Cost/Sale table cells themselves (Enter/blur to save, Escape to cancel) |
| `/` | Sessions | under **Settings** | Create/manage WhatsApp accounts, QR connect (formerly "Accounts") |
| `/storage` | Storage | under **Settings** | Per-account storage stats, media controls, embedding status + backfill |
| `/ai-providers` | AI Providers | under **Settings** | Manage voyage/openai/etc. provider config and API keys |
| `/ai-instructions` | AI Instructions | under **Settings** | Edit trading prompt overrides (§6.11), view AI agent call log/diagnostics (§6.12) |
| `/activity` | Activity Log | under **Logs** | Sync log with filter by account/type, embedding status per event |
| `/message-logs` | Message Logs | under **Logs** | Raw per-session worker log viewer |
| `/dropped-messages` | Dropped Messages Log | under **Logs** | All messages the worker dropped, expandable raw key with `_msgKeys`; rows that later self-healed (§6.7 `resolved_at`) show a green "Recovered" badge |
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

---

## 18. Security

- `INTERNAL_API_TOKEN` — shared secret between Node.js worker and Django. Set in `.env`. All internal endpoints validate this header.
- Session auth + CSRF gate every frontend route except `/login`. Enforced client-side by the Vue Router `beforeEach` guard (`frontend/src/router/index.ts`) calling `/api/auth/me/`, and server-side by DRF session auth on every `apps/api`/`apps/trading` viewset.
- `whatsapp-worker/sessions/` — WhatsApp E2E session keys. Never committed.
- `.env` / `.env.local_dev` — API keys and secrets. Never committed.
- `whatsapp-worker/message-logs/` — raw message logs for debugging. Not committed.

---

## 19. Migration History

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

### Phase 10 — ML Intelligence (planned)
- Lead scoring
- ERP product master integration / two-way sync
- Cross-account analytics rollups
