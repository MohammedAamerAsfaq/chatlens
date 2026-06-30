# ChatLens Development Document

> **Status:** Living document — reflects the system as actually built, not the original plan.
> Last updated: 2026-06-30

---

## 1. Product Name

**ChatLens**

---

## 2. Purpose

ChatLens is a WhatsApp QR-session based conversation intelligence system. It reads WhatsApp conversations, stores them in a structured PostgreSQL database, generates vector embeddings for semantic search, and provides dashboards for analytics, contact management, and message intelligence.

ChatLens is a read-first system. Sending is deliberately disabled in the current version.

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
  whatsapp_bridge/        accounts, sessions, chats, contacts, messages, sync logs, dropped messages
  message_intelligence/   embeddings, semantic search
  api/                    public REST API for the Vue frontend
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
| created_at | timestamptz | |
| updated_at | timestamptz | |

### 6.2 whatsapp_contact

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| account_id | FK → whatsapp_account | |
| wa_contact_id | varchar(255) | **always** a phone JID (`phone@s.whatsapp.net`) or group JID (`id@g.us`) — never a LID |
| lid_jid | varchar(255) nullable | LID alias when the contact uses WhatsApp privacy mode (e.g. `200506303578143@lid`) |
| phone_number | varchar(50) | digits only, derived from wa_contact_id |
| display_name | varchar(255) | user-editable label; seeded from push_name on first create only |
| push_name | varchar(255) | the name set on the contact's WhatsApp profile |
| is_business | boolean | |
| raw_payload | jsonb | |
| created_at | timestamptz | |
| updated_at | timestamptz | |

**Constraints:**
- `UNIQUE(account_id, wa_contact_id)`
- `UNIQUE(account_id, lid_jid)` where `lid_jid IS NOT NULL AND lid_jid != ''`

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
| raw_payload | jsonb | |

**Constraints:** `UNIQUE(account_id, wa_chat_id)`

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
| POST | `/api/internal/whatsapp/contacts-update/` | Contact names from `contacts.set` / `contacts.upsert` |
| POST | `/api/internal/whatsapp/dropped-message/` | Fire-and-forget drop notification |

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

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/accounts/` | WhatsApp account CRUD |
| POST | `/api/accounts/:id/start-session/` | Start worker session |
| GET  | `/api/accounts/:id/qr/` | Poll QR code |
| POST | `/api/accounts/:id/disconnect/` | Disconnect session |
| GET  | `/api/accounts/:id/storage/` | Storage stats |
| GET  | `/api/chats/` | Chat list |
| GET  | `/api/chats/:id/messages/` | Messages in a chat |
| GET  | `/api/contacts/` | Contact list (paginated, filterable) |
| GET  | `/api/contacts/stats/` | `{total, phone, lid, group}` counts |
| PATCH | `/api/contacts/:id/` | Update `display_name` only |
| GET  | `/api/activity/` | Sync log entries |
| GET  | `/api/dropped-messages/` | Dropped message log |
| POST | `/api/dropped-messages/clear-all/` | Clear drop log |
| POST | `/api/intelligence/search/` | Semantic search |
| GET  | `/api/intelligence/embedding-status/` | Embedding coverage stats |
| POST | `/api/intelligence/backfill/` | Trigger background embedding of pending messages |
| GET/POST | `/api/ai-providers/` | AI provider config |

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
  → _upsert_contact   (raises ValueError if wa_contact_id ends with @lid)
  → _upsert_chat      (last_message_at is monotonically advancing)
  → _insert_message   (get_or_create by provider_message_id)
  → _embed_in_background (daemon thread, fire-and-forget)
```

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
3. `session.lidToPhone` — in-memory cache populated from `contacts.set` / `contacts.upsert` at connect time and updated whenever a `senderPn`/`participantPn` is seen

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

| Route | Screen | Purpose |
|---|---|---|
| `/` | Dashboard | Message volume, account stats |
| `/accounts` | Accounts | Create/manage WhatsApp accounts, QR connect |
| `/conversations` | Conversations | Chat list + message view |
| `/contacts` | Contacts | Contact management, display name editing, LID alias display |
| `/storage` | Storage | Per-account storage stats, media controls, embedding status + backfill |
| `/activity` | Activity Log | Sync log with filter by account/type, embedding status per event |
| `/dropped-messages` | Dropped Messages Log | All messages the worker dropped, expandable raw key with `_msgKeys` |
| `/ai-providers` | AI Providers | Manage voyage/openai/etc. provider config and API keys |

---

## 17. Worker Session State

Each active session (`this.sessions.get(sessionId)`) holds:

```javascript
{
  sock,               // Baileys socket
  sessionId,
  historyDays,        // from account settings
  lastActivityAt,
  lidToPhone: {},     // Map: normalized LID JID → full phone JID
                      // Populated from contacts.set and participantPn/senderPn on live messages
}
```

---

## 18. Security

- `INTERNAL_API_TOKEN` — shared secret between Node.js worker and Django. Set in `.env`. All internal endpoints validate this header.
- `whatsapp-worker/sessions/` — WhatsApp E2E session keys. Never committed.
- `.env` / `.env.local_dev` — API keys and secrets. Never committed.
- `whatsapp-worker/message-logs/` — raw message logs for debugging. Not committed.

---

## 19. Migration History

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

### Phase 5 — Analytics Dashboard (planned)
- Message volume by day/hour
- Top chats, top contacts
- Intent/sentiment distribution
- Response-time analytics

### Phase 6 — ML Intelligence (planned)
- Intent detection (price inquiry, stock inquiry, complaint, etc.)
- Product mention extraction + fuzzy matching
- Lead scoring
- ERP product master integration
