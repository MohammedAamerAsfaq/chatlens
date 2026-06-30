# B2B Trading Intelligence — Implementation Plan

**Project:** ChatLens  
**Feature:** Real-Time B2B Wholesale Trading Dashboard  
**Scope:** Message classification, product recognition, inquiry lifecycle, trading dashboard

---

## 1. Business Context

At the start of each trading day, WhatsApp messages begin arriving from direct chats, groups, and communities. Traders send buying and selling inquiries, negotiate prices, confirm deals, or send greetings and casual messages. The business operates on a sub-minute response window — an unacknowledged inquiry is almost certainly a lost deal.

ChatLens must:

- Detect buying and selling inquiries automatically as messages arrive.
- Recognise products from free-text, including informal abbreviations traders use.
- Create and maintain an Inquiry record for each genuine business opportunity.
- Deduplicate inquiries when the same person sends the same offer to multiple groups.
- Surface everything on a live trading dashboard so operators can act immediately.

---

## 2. System Architecture

### 2.1 End-to-End Pipeline

```
WhatsApp message arrives
        │
        ▼
  WhatsAppMessage saved to PostgreSQL          ← existing
        │
        ▼
  Background thread starts                     ← existing
  ├── embed_message()                          ← existing
  └── classify_message()                       ← NEW (runs immediately after embed)
              │
              ▼
        MessageClassification record created
        (tags, matched products, inquiry flag, summary)
              │
              ├── is_inquiry = False → done
              │
              └── is_inquiry = True
                        │
                        ▼
                  Deduplication check
                  ├── Existing open Inquiry found → link message, update record
                  └── No match → create new Inquiry (status: Open)
                        │
                        ▼
                  Dashboard reflects change (15-second poll)
```

### 2.2 Target Latency

| Step | Target |
|---|---|
| Message saved to DB | < 1 second (existing) |
| Embedding generated | + 1–2 seconds (existing) |
| AI classification completed | + 1–3 seconds (new AI call) |
| Inquiry created or updated | + < 1 second (DB write) |
| **Total: message → Inquiry visible on dashboard** | **< 6 seconds** |

This satisfies the under-one-minute business requirement with a large margin.

---

## 3. New Django Application

All trading intelligence lives in a new first-class Django app: `apps/trading/`.

```
apps/trading/
├── __init__.py
├── apps.py
├── models/
│   ├── __init__.py
│   ├── product.py
│   ├── message_classification.py
│   └── inquiry.py
├── services/
│   ├── classification_service.py
│   ├── inquiry_service.py
│   └── product_cache.py
├── migrations/
├── serializers.py
├── views.py
└── urls.py
```

---

## 4. Data Models

### 4.1 Product (Product Master)

**File:** `apps/trading/models/product.py`

```python
class Product(models.Model):
    name        = models.CharField(max_length=255)     # "iPhone 17 Pro Max"
    brand       = models.CharField(max_length=100)     # "Apple"
    category    = models.CharField(max_length=100)     # "Smartphones"
    sku         = models.CharField(max_length=100, blank=True)
    aliases     = models.JSONField(default=list)
    # aliases example: ["17PM", "17 Pro Max", "17 PRO MAX", "17ProMax", "Apple 17 PM"]
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_product'
        ordering = ['brand', 'name']
```

**Design notes:**
- Aliases are stored as a plain JSON array on the product itself, not a separate table. This keeps the product-alias string compact when building AI prompts.
- The AI does all fuzzy matching. The database never does string-similarity queries against aliases — it just stores them.
- Products are managed by operators via the Products UI screen. Seed data covers the initial mobile inventory.

---

### 4.2 MessageClassification

**File:** `apps/trading/models/message_classification.py`

```python
class MessageTag(models.TextChoices):
    WTB               = 'wtb',               'Want To Buy'
    WTS               = 'wts',               'Want To Sell'
    PRICE_INQUIRY     = 'price_inquiry',     'Price Inquiry'
    STOCK_INQUIRY     = 'stock_inquiry',     'Stock Availability'
    NEGOTIATION       = 'negotiation',       'Negotiation'
    DEAL_CONFIRMATION = 'deal_confirmation', 'Deal Confirmation'
    GREETING          = 'greeting',          'Greeting'
    JOKE              = 'joke',              'Joke / Casual'
    SPAM              = 'spam',              'Spam'
    OTHER             = 'other',             'Other'


class MessageClassification(models.Model):
    message       = models.OneToOneField(
        'whatsapp_bridge.WhatsAppMessage',
        on_delete=models.CASCADE,
        related_name='classification',
    )
    tags          = models.JSONField(default=list)
    # tags example: ["wtb", "price_inquiry"]

    products      = models.JSONField(default=list)
    # products example:
    # [{"product_id": 5, "canonical_name": "iPhone 17 Pro Max",
    #   "quantity": 10, "price": null, "currency": null}]

    is_inquiry    = models.BooleanField(default=False)
    inquiry_type  = models.CharField(
        max_length=10,
        choices=[('buy', 'Buy'), ('sell', 'Sell'), ('both', 'Both')],
        blank=True,
    )
    ai_summary    = models.TextField(blank=True)
    raw_response  = models.JSONField(null=True, blank=True)
    classified_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_message_classification'
```

**Design notes:**
- One record per `WhatsAppMessage`. Created after every successful AI classification call.
- `tags` is a list so a message can have multiple tags (e.g. `["wtb", "price_inquiry"]`).
- `products` stores a snapshot of the matched products at classification time, including extracted quantity and price if the AI found them in the text.
- Only text messages are classified. Media-only messages (images, audio, documents without captions) are skipped.
- History sync messages (flagged `is_history=True`) older than 24 hours are not classified. Classification is only meaningful for live messages.

---

### 4.3 Inquiry and InquiryMessage

**File:** `apps/trading/models/inquiry.py`

```python
class InquiryStatus(models.TextChoices):
    OPEN      = 'open',      'Open'
    CLOSED    = 'closed',    'Closed'
    DEAL_DONE = 'deal_done', 'Deal Done'


class Inquiry(models.Model):
    account      = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='inquiries',
    )
    contact      = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='inquiries',
    )
    inquiry_type = models.CharField(
        max_length=10,
        choices=[('buy', 'Buy'), ('sell', 'Sell')],
    )
    status       = models.CharField(
        max_length=20,
        choices=InquiryStatus.choices,
        default=InquiryStatus.OPEN,
        db_index=True,
    )
    products     = models.JSONField(default=list)
    # Snapshot of products at creation time. Updated when follow-up messages add detail.

    summary      = models.TextField()
    remarks      = models.TextField(blank=True)

    dedup_key    = models.CharField(max_length=512, db_index=True)
    # Format: "{type}:{product_slug}:{qty_bucket}:{contact_id}"
    # Used for cross-group deduplication. Same person, same product, same qty = same inquiry.

    source_type  = models.CharField(
        max_length=20,
        choices=[('direct', 'Direct'), ('group', 'Group'), ('community', 'Community')],
    )
    first_seen_at = models.DateTimeField()   # timestamp of the originating message
    closed_at     = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_inquiry'
        ordering = ['-first_seen_at']


class InquiryMessage(models.Model):
    inquiry  = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name='inquiry_messages')
    message  = models.ForeignKey(
        'whatsapp_bridge.WhatsAppMessage',
        on_delete=models.CASCADE,
        related_name='inquiry_links',
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_inquiry_message'
        unique_together = [('inquiry', 'message')]
```

**Design notes:**
- An `Inquiry` represents a business opportunity, not a single message. Multiple messages (from multiple groups) can link to the same `Inquiry` via `InquiryMessage`.
- `dedup_key` is the primary deduplication mechanism. It is generated by the AI as part of the classification response.
- `first_seen_at` is the timestamp of whichever message first created this inquiry. It does not change when follow-up messages arrive.
- `closed_at` is recorded when status moves to `closed` or `deal_done` so response and conversion time can be calculated.

---

## 5. AI Classification Service

### 5.1 Product Cache

**File:** `apps/trading/services/product_cache.py`

Builds and caches the product-alias string that gets inserted into every AI prompt. Rebuilt only when the product list changes, not on every message.

```python
_cache = {'prompt_block': None, 'updated_at': None}

def get_product_prompt_block() -> str:
    """Return a compact product list string for AI prompt injection.
    Cached in memory; rebuilds automatically when products are updated."""
    ...

def invalidate():
    """Call this whenever a product is created, updated, or deleted."""
    _cache['prompt_block'] = None
```

The product block looks like:
```
ID:1  iPhone 17 Pro Max  [Apple] → aliases: 17PM, 17 PRO MAX, 17 ProMax, 17 Pro Max, Apple 17 PM
ID:2  iPhone 16          [Apple] → aliases: 16, i16, 16 plain, iPhone 16
ID:3  Samsung S25 Ultra  [Samsung] → aliases: S25U, S25 Ultra, 25U
```

If the product catalogue grows very large (hundreds of products), the prompt block is chunked and only the most-traded products are always included, with the rest available on request.

---

### 5.2 Classification Service

**File:** `apps/trading/services/classification_service.py`

Single AI call per message. Uses the active AI provider (same provider system already in ChatLens).

**AI Prompt (system):**
```
You are a B2B wholesale mobile trading classifier for a live trading desk.
Analyze the WhatsApp message below and classify it.

PRODUCT MASTER — match against these products and their aliases (case-insensitive, ignore spaces/punctuation):
{product_prompt_block}

Respond ONLY with valid JSON matching this exact schema:
{
  "tags": [...],           // one or more of: wtb, wts, price_inquiry, stock_inquiry,
                           //   negotiation, deal_confirmation, greeting, joke, spam, other
  "products": [            // list of matched products (empty if none)
    {
      "product_id": <int>,
      "canonical_name": "<string>",
      "quantity": <int or null>,
      "price": <float or null>,
      "currency": <string or null>
    }
  ],
  "is_inquiry": <bool>,    // true only if this is a genuine buy or sell business opportunity
  "inquiry_type": "buy" | "sell" | "both" | null,
  "summary": "<one sentence>",
  "dedup_key": "<string>"  // format: "{buy|sell}:{product-slug}:{qty-bucket}:{contact-id}"
                           // empty string if is_inquiry is false
}
```

**AI Prompt (user):**
```
Classify this message:

Sender: {sender_jid}
Source: {group_name or "Direct chat"}
Time: {message_time}
Message: "{message_text}"
```

**Expected response examples:**

Message: `"Need 10 units 17PM urgently"`
```json
{
  "tags": ["wtb"],
  "products": [{"product_id": 1, "canonical_name": "iPhone 17 Pro Max", "quantity": 10, "price": null, "currency": null}],
  "is_inquiry": true,
  "inquiry_type": "buy",
  "summary": "Buyer wants 10 units of iPhone 17 Pro Max urgently.",
  "dedup_key": "buy:iphone-17-pro-max:10:971501234567"
}
```

Message: `"Good morning everyone!"`
```json
{
  "tags": ["greeting"],
  "products": [],
  "is_inquiry": false,
  "inquiry_type": null,
  "summary": "Greeting message.",
  "dedup_key": ""
}
```

---

### 5.3 Integration into Background Pipeline

**File:** `apps/whatsapp_bridge/services/ingestion_service.py`  
**Change:** Replace `_embed_in_background` call with `_process_message_in_background`

Current:
```python
_embed_in_background([message.pk], sync_log_id=sync_log.pk)
```

New:
```python
_process_message_in_background(message.pk, sync_log_id=sync_log.pk)
```

The new function:
```python
def _process_message_in_background(message_id: int, sync_log_id: int = None):
    def _run():
        # Step 1: embed (existing logic)
        ok = embed_message(message_id)

        # Step 2: classify (new)
        message = WhatsAppMessage.objects.select_related('account', 'chat', 'contact').get(pk=message_id)
        if _should_classify(message):
            from apps.trading.services.classification_service import classify_message
            classify_message(message)

    threading.Thread(target=_run, daemon=True).start()


def _should_classify(message) -> bool:
    if not message.message_text:
        return False                    # no text, nothing to classify
    if message.direction == 'outbound':
        return False                    # only classify inbound messages
    age_hours = (now() - message.message_time).total_seconds() / 3600
    if age_hours > 24:
        return False                    # skip old history-sync messages
    return True
```

---

## 6. Inquiry Service and Deduplication

**File:** `apps/trading/services/inquiry_service.py`

Called by `classify_message()` when `is_inquiry = True`.

### 6.1 Deduplication Algorithm

Two-layer check, run in sequence:

**Layer 1 — Exact dedup_key match:**
```python
window = now() - timedelta(hours=4)
existing = Inquiry.objects.filter(
    account=account,
    contact=contact,
    dedup_key=dedup_key,
    status=InquiryStatus.OPEN,
    first_seen_at__gte=window,
).first()

if existing:
    InquiryMessage.objects.get_or_create(inquiry=existing, message=message)
    return existing  # linked, not duplicated
```

**Layer 2 — Semantic similarity fallback:**

If no exact dedup_key match, compare the new message's embedding vector against the source message embeddings of recent open inquiries from the same contact. If cosine similarity ≥ 0.92, treat as the same inquiry.

```python
recent_inquiries = Inquiry.objects.filter(
    account=account,
    contact=contact,
    status=InquiryStatus.OPEN,
    first_seen_at__gte=window,
)
for candidate in recent_inquiries:
    source_embedding = get_embedding(candidate.inquiry_messages.first().message_id)
    similarity = cosine_similarity(new_embedding, source_embedding)
    if similarity >= 0.92:
        InquiryMessage.objects.get_or_create(inquiry=candidate, message=message)
        return candidate
```

If neither layer finds a match, create a new `Inquiry`.

### 6.2 Creating a New Inquiry

```python
Inquiry.objects.create(
    account=account,
    contact=contact,
    inquiry_type=classification.inquiry_type,
    status=InquiryStatus.OPEN,
    products=classification.products,
    summary=classification.ai_summary,
    dedup_key=classification.dedup_key (from AI response),
    source_type=derive_source_type(message.chat),   # direct / group / community
    first_seen_at=message.message_time,
)
InquiryMessage.objects.create(inquiry=new_inquiry, message=message)
```

---

## 7. API Endpoints

All new endpoints are registered at `/api/` via the existing DRF router.

### 7.1 Inquiries

| Method | URL | Description |
|---|---|---|
| GET | `/api/inquiries/` | List with filters: `status`, `type`, `product_id`, `account`, `date` |
| GET | `/api/inquiries/{id}/` | Detail — includes linked messages |
| PATCH | `/api/inquiries/{id}/` | Update `status` and/or `remarks` |
| GET | `/api/inquiries/stats/` | Dashboard aggregates (see §8) |
| GET | `/api/inquiries/timeline/` | Hourly inquiry counts for the current day |

**PATCH body:**
```json
{
  "status": "deal_done",
  "remarks": "Sold 10 units at AED 3800 each, delivery Thursday"
}
```

### 7.2 Products

| Method | URL | Description |
|---|---|---|
| GET | `/api/products/` | List all products |
| POST | `/api/products/` | Create new product |
| GET | `/api/products/{id}/` | Product detail |
| PATCH | `/api/products/{id}/` | Update name, aliases, active flag |
| DELETE | `/api/products/{id}/` | Soft-delete (set `is_active=False`) |
| GET | `/api/products/stats/` | Per-product WTB/WTS counts for today |

### 7.3 Message Classifications (read-only)

| Method | URL | Description |
|---|---|---|
| GET | `/api/classifications/?message={id}` | Get classification for a specific message |

---

## 8. Dashboard Stats API

`GET /api/inquiries/stats/` — used by the trading dashboard. Returns all numbers needed to render the dashboard in a single call.

```json
{
  "today": {
    "wtb_total": 47,
    "wts_total": 31,
    "open": 22,
    "closed": 18,
    "deal_done": 8,
    "missed": 14
  },
  "by_product": [
    {"product_id": 1, "name": "iPhone 17 Pro Max", "wtb": 18, "wts": 9, "deals": 4},
    {"product_id": 2, "name": "iPhone 16",          "wtb": 11, "wts": 7, "deals": 2}
  ],
  "by_source": {
    "direct":    {"wtb": 12, "wts": 8},
    "group":     {"wtb": 30, "wts": 20},
    "community": {"wtb": 5,  "wts": 3}
  },
  "avg_response_minutes": 4.2,
  "avg_deal_minutes": 38.5,
  "timeline": [
    {"hour": "08:00", "wtb": 3, "wts": 1},
    {"hour": "09:00", "wtb": 8, "wts": 5},
    ...
  ]
}
```

**Missed definition:** An inquiry that remained `OPEN` for more than 60 minutes without any status change. Computed at query time.

---

## 9. Frontend Views

### 9.1 Product Master (`/products`)

Simple data-maintenance table.

- Columns: Name | Brand | Category | Aliases | Active
- Aliases edited as comma-separated chips (similar to tag input)
- Add / Edit / Deactivate actions per row
- Changes to aliases trigger product cache invalidation on the server (`POST /api/products/{id}/` calls `product_cache.invalidate()`)

---

### 9.2 Inquiries Screen (`/inquiries`)

Split-panel layout consistent with existing Chats and Groups screens.

**Left panel — filtered list:**
- Filter bar: Type (All / WTB / WTS), Status (All / Open / Closed / Deal Done), Product dropdown, Date
- Each row shows: type badge, contact name, product(s), summary excerpt, source (D/G/C icon), age
- Rows younger than 1 minute get a yellow pulse border (urgent)
- Auto-refresh every 10 seconds

**Right panel — inquiry detail:**
- Contact info, source chat(s)
- Summary and products block
- All linked messages in chronological order with source chat label
- Status action buttons: **Mark Closed** | **Mark Deal Done**
- Remarks textarea (saved on blur)

---

### 9.3 B2B Trading Dashboard (`/trading`)

Live trading monitor. Polling interval: 15 seconds.

**Top stat row:**
```
[ WTB: 47 ]  [ WTS: 31 ]  [ Open: 22 ]  [ Closed: 18 ]  [ Deals: 8 ]  [ Missed: 14 ]
```

**Main section — two live feed columns:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  BUYING (WTB)                  SELLING (WTS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ● iPhone 17 PM ×10  <1min    ● iPhone 16 ×20   3min
    Ahmed | Group Alpha           Khalid | Direct
    [Close] [Deal Done]           [Close] [Deal Done]

  ● Samsung S25 ×5    4min     ● iPhone 15 PM ×8  7min
    ...                          ...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

- Only `OPEN` inquiries shown in live feed, newest first.
- Action buttons (Close / Deal Done) update status inline without leaving the dashboard.
- Age indicator turns red after 1 minute.

**Bottom analytics section (collapsible):**

| Panel | Content |
|---|---|
| Product Demand Table | Product → WTB count / WTS count / Deals / Conversion % |
| Source Breakdown | Direct vs Group vs Community for WTB and WTS |
| Hourly Activity Chart | Bar chart of inquiry count per hour for today |
| Response & Conversion | Avg time to first response, avg time to deal |

---

### 9.4 Message Tag Badges (existing Chat View)

Each classified message in the chat messages list gets a small tag badge:

- `WTB` — green
- `WTS` — orange
- `DEAL` — blue
- `GREETING` — gray
- `OTHER` — light gray
- `SPAM` — red

The `MessageSerializer` is extended to include a `classification` nested field (nullable — messages not yet classified or skipped show nothing).

---

## 10. Implementation Phases and Order

| Phase | What | Files | Est. Days |
|---|---|---|---|
| 1 | `apps/trading` app scaffolding, Product model, migrations, product cache | `apps/trading/` | 0.5 |
| 2 | Product CRUD API + serializers + URL registration | `apps/trading/serializers.py`, `views.py`, `urls.py` | 0.5 |
| 3 | MessageClassification model + migration | `apps/trading/models/message_classification.py` | 0.5 |
| 4 | Inquiry + InquiryMessage models + migration | `apps/trading/models/inquiry.py` | 0.5 |
| 5 | Classification service (AI call + structured response parsing) | `apps/trading/services/classification_service.py` | 1.5 |
| 6 | Inquiry service (dedup logic, create/update) | `apps/trading/services/inquiry_service.py` | 1.0 |
| 7 | Integration into ingestion pipeline | `apps/whatsapp_bridge/services/ingestion_service.py` | 0.5 |
| 8 | Inquiry CRUD API + stats endpoint | `apps/trading/views.py`, `serializers.py` | 1.0 |
| 9 | Dashboard stats API (`/api/inquiries/stats/`) | `apps/trading/views.py` | 0.5 |
| 10 | Product Management Vue view (`/products`) | `frontend/src/views/ProductsView.vue` | 0.5 |
| 11 | Inquiries Vue view (`/inquiries`) | `frontend/src/views/InquiriesView.vue` | 1.0 |
| 12 | B2B Trading Dashboard Vue view (`/trading`) | `frontend/src/views/TradingView.vue` | 1.5 |
| 13 | Tag badges on existing chat messages view | `frontend/src/views/ChatsView.vue` | 0.5 |
| **Total** | | | **~9 days** |

**Critical path:** Phases 1–7 (data models + pipeline) must complete before Phases 10–13 (UI) can show real data. Phases 10–13 can be built in parallel once the API shape (Phase 8–9) is defined.

---

## 11. Key Technical Decisions

### Product matching is AI-driven, not regex-driven

The product master stores canonical names and aliases. The AI receives the full list in the prompt and does all fuzzy matching. This handles:
- Abbreviations (17PM vs iPhone 17 Pro Max)
- Spacing variations (17ProMax vs 17 Pro Max)
- Missing brand names (just "17 PM" without "iPhone" or "Apple")
- Language mixing (common in wholesale messaging)

No database-side LIKE queries or Levenshtein distance calculations are used for product recognition.

### Deduplication uses a two-layer approach

1. **Exact dedup_key match** — fast O(1) DB lookup. Covers the most common case: same person sends identical text to multiple groups within a short window.
2. **Semantic similarity fallback** — cosine similarity of embeddings. Covers rephrased versions of the same inquiry.

The 4-hour dedup window is configurable. Same-day inquiries from the same contact for the same product that close and re-open are treated as distinct (because the first one was closed).

### Classification runs in the existing background thread

No new infrastructure (no Celery, no Redis) is required at this stage. The AI call is appended to the same daemon thread that already handles embedding. If classification volume grows to the point where threads queue up, the natural upgrade path is Celery workers, but that is a separate decision.

### History messages are not classified

Only live inbound messages (not history-sync, not outbound) are classified. The `_should_classify` check gates on `is_history`, `direction`, and message age. This prevents old messages from polluting today's inquiry list.

### `closed_at` enables response-time analytics

When a user marks an inquiry Closed or Deal Done, `closed_at` is set. The dashboard computes:
- Average response time: `avg(closed_at - first_seen_at)` for closed inquiries
- Deal conversion time: `avg(closed_at - first_seen_at)` for deal_done inquiries only
- Missed: `count(open inquiries where now() - first_seen_at > 60 minutes)`

---

## 12. Risk Items

| Risk | Mitigation |
|---|---|
| Product list too large for AI prompt | Cap prompt at 100 most-used products; add others on detection failure |
| AI returns malformed JSON | Wrap AI call in retry with exponential backoff; fall back to tagging message as `other` rather than crashing |
| Dedup false positive (two different buyers merged) | `contact_id` is part of `dedup_key` — merging only happens for the same sender |
| Dedup false negative (same inquiry not merged) | Layer 2 semantic similarity covers rephrased duplicates |
| High message volume creating thread congestion | Monitor thread queue depth; upgrade to Celery if sustained throughput exceeds ~20 msg/min |
| History sync flooding classification | `_should_classify` hard-gates on `is_history` flag and message age |

---

*Document prepared for ChatLens B2B Trading Intelligence feature.*  
*Covers architecture, models, AI pipeline, API, and frontend — ready for phase-by-phase implementation.*
