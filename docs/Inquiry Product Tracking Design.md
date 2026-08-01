# Inquiry Product Tracking Design

## Objective

Track product mentions from inquiries in a proper structured form, with full traceability back to
the incoming message and parsed inquiry.

The current phase is not focused on final analytics or report counting. If the data is stored
correctly, multiple reports can be built from it later. WTB/WTS demand and supply counts are only
two examples of reports that can be derived from the same structure.

The long-term business questions include:

- Which products are most requested by customers or buyers?
- Which products are most offered by suppliers?
- Which products have high demand but low or no inventory?
- Which products have high supply but low demand?
- Which product names are being used by parties but are not yet mapped to inventory?
- Which source message and party caused a product mention to enter the market flow?
- How does one product inquiry spread across contacts, groups, accounts, or time?

For future reporting:

- WTB inquiries represent demand.
- WTS inquiries represent supply.
- Both-direction inquiries can initially count once in both demand and supply until more detailed line-level direction parsing is implemented.

## Current State

Inquiries currently store parsed product information inside `Inquiry.products` as JSON.

Example structure:

```json
[
  {
    "product_id": 11,
    "match_type": "exact",
    "canonical_name": "17 Pro max 512gb Silver 1 Physical sim",
    "quantity": null,
    "price": null,
    "currency": null
  }
]
```

This is useful for display, but it is not ideal for analytics because:

- JSON rows are harder to query and aggregate reliably.
- Product mentions without an inventory match are difficult to track over time.
- There is no first-class place to record matching status, match source, or manual confirmation.
- Alias discovery is not tracked separately from the original inquiry.

## Implemented Phase: Manual-First Traceability

The first implementation is intentionally manual-first. Automatic creation of `InquiryProduct`
rows during live inquiry processing has been removed for now.

Current flow:

```text
Incoming WhatsApp message
  -> AI classification
     -> Inquiry created/updated
        -> parsed products remain in Inquiry.products JSON
           -> user opens Inquiry Products manually
              -> user creates inventory product from a selected unmapped line
                 -> Product row is created
                 -> InquiryProduct trace row is created
                 -> Inquiry.products[index].product_id is updated
```

This keeps the existing trading board behavior stable:

- Inquiry creation continues to use the current `Inquiry` and `InquiryMessage` path.
- The trading board still reads `Inquiry.products` for display and stock suggestions.
- Product analytics still counts existing inventory mentions from `Inquiry.products[*].product_id`.
- Unmapped parsed product lines do not create trace rows automatically.
- No backfill runs automatically.

Manual UI entry points:

- Trading board WTB/WTS cards show an `Inquiry Products` button when the inquiry has parsed products.
- The Inquiries page also exposes the same `Inquiry Products` action.
- The separate `Lists -> Inquiry Products` page lists already-created trace rows.

Manual review behavior:

- The popup lists every product line in the selected inquiry.
- Each row checks whether it already has an inventory mapping through `product_id`.
- Each row also checks exact active inventory product name match before offering creation.
- Rows with an existing mapping or existing trace row are shown as linked.
- Unmapped rows expose `Create Product`.

Manual product creation behavior:

- Creates a new inventory `Product` under the inquiry company.
- Starts with `qty = 0` so the system does not falsely add stock.
- Creates one linked `InquiryProduct` trace row.
- Updates the original `Inquiry.products` line with the created `product_id` and `match_type = exact`.
- Invalid indexes, duplicate trace rows, blank names, and missing company context fail explicitly.

This phase deliberately prioritizes controlled user decisions over automatic product proliferation.

## Target Design

Introduce a structured product mention layer.

The main model should be `InquiryProduct`.

Long term, each extracted product line from an inquiry may create one `InquiryProduct` row. In the
current manual-first phase, the row is created only after the user takes action from the inquiry UI.

The traceability chain should be:

```text
Incoming WhatsApp message
  -> parsed inquiry
     -> extracted inquiry product line
        -> inventory product when mapped
```

Traceability must start even when inventory mapping is missing or uncertain. An extracted product
line without a `product_id` is still valuable because it records that a party mentioned that product,
from a specific message, at a specific time. In the current phase, that value remains available in
`Inquiry.products` until the user creates or maps a structured trace row.

The existing `Inquiry.products` JSON should remain for now to avoid breaking current UI behavior. The new model should run alongside it until the structured design is mature.

## Proposed Model: InquiryProduct

Suggested fields:

```text
InquiryProduct
- company
- inquiry
- source_message
- account
- contact
- inquiry_type
- canonical_name
- original_text
- quantity
- price
- currency
- product
- decision_status
- match_status
- match_type
- match_source
- match_reason
- embedding
- embedding_model
- embedding_metadata
- embedding_status
- embedding_error
- first_seen_at
- created_at
- updated_at
```

Field meaning:

- `company`: Tenant owner. Required for tenant isolation and analytics scoping.
- `inquiry`: Parent inquiry.
- `source_message`: Original WhatsApp message if available.
- `account`: Account snapshot for fast filtering/reporting.
- `contact`: Contact snapshot for fast filtering/reporting.
- `inquiry_type`: Snapshot of inquiry direction: `buy`, `sell`, or `both`.
- `canonical_name`: AI-normalized product name from the inquiry.
- `original_text`: Sender wording if available. This may initially be empty until line-level extraction improves.
- `quantity`: Requested/offered quantity if parsed.
- `price`: Requested/offered price if parsed.
- `currency`: Currency if parsed.
- `product`: Inventory product match, nullable.
- `decision_status`: User workflow state, such as `pending`, `mapped`, `created`, or `dismissed`.
- `match_status`: Current tracking status, such as `exact`, `near`, `unmatched`, `manual_confirmed`, or `rejected`.
- `match_type`: Original AI match type if applicable.
- `match_source`: How the product was matched, such as `ai`, `alias`, `deterministic`, or `manual`.
- `match_reason`: Short explanation for audit/debugging.
- `embedding`: Optional line-level embedding for the extracted product mention.
- `embedding_model`: Embedding model used.
- `embedding_metadata`: Provider/dimension/debug details.
- `embedding_status`: `pending`, `embedded`, `error`, or `skipped`.
- `embedding_error`: Failure details if embedding generation failed.
- `first_seen_at`: Inquiry/message time used for time-based analytics.

## Embedding Approach

`MessageEmbedding` already exists, but it represents the full WhatsApp message. That is useful for
message search and inquiry deduplication, but it is not enough for product tracking because one
message can contain multiple product lines.

Example:

```text
WTB 17 Pro Max 512 Silver HK
also need S25 Ultra 1TB Titanium
```

This should produce two `InquiryProduct` rows, each with its own product-level meaning. Therefore
the product tracking module should support direct embeddings on `InquiryProduct`.

For this module:

- Embed the extracted product line, not the whole message.
- Use `canonical_name` as the primary embedding text.
- Include `original_text` when available and meaningfully different.
- Do not introduce a separate shared embedding table at this stage.
- If embedding fails, keep the `InquiryProduct` row and mark `embedding_status = error`.
- Do not block inquiry creation because of embedding failure.

To reduce duplicate embedding cost without adding extra schema complexity:

1. Normalize `canonical_name`.
2. Before calling the embedding provider, search for an older `InquiryProduct` in the same company
   with the same normalized text, same embedding model, and a stored embedding.
3. If found, copy/reuse that vector on the new row.
4. If not found, call the embedding provider.

Embeddings are a matching aid, not the final source of truth. Mapping decisions should still be
stored explicitly in `product`, `decision_status`, `match_status`, `match_source`, and `match_reason`.

## Future Demand And Supply Counting

This section describes one future reporting use case. It is not the primary implementation objective
for the first phase.

Analytics should count product mentions by direction.

Initial rule:

```text
if inquiry_type = buy:
    WTB count +1

if inquiry_type = sell:
    WTS count +1

if inquiry_type = both:
    WTB count +1
    WTS count +1
```

Quantity-based analytics can be added later:

```text
WTB quantity = sum(quantity) for buy inquiries
WTS quantity = sum(quantity) for sell inquiries
```

For the initial implementation, mention count is more reliable than quantity because many messages do not contain quantity.

## Product Rollup Logic

If `InquiryProduct.product_id` exists, analytics roll up to the inventory product.

Example:

```text
Product: Apple iPhone 17 Pro Max 512GB Silver Hong Kong
WTB mentions: 18
WTS mentions: 4
Current stock: 0
```

If `InquiryProduct.product_id` is null, analytics roll up by `canonical_name`.

Example:

```text
Unmatched: 17 Pro Max 512GB Silver HK
WTB mentions: 9
WTS mentions: 0
Action: map to existing product or create new product
```

This lets the business see product demand even before the product exists in inventory.

## Inventory Mapping

Mapping should happen in strict layers:

1. Use `product_id` already returned by AI if present.
2. Match against confirmed aliases.
3. Match using deterministic normalized product names/specs where safe.
4. Use manual AI verification or AI-assisted matching only when user requests it.
5. If still not matched, keep the row unmatched.

Important rule:

Do not silently force an alternate match when the product is uncertain. Mark it as `unmatched` or `near` and make the uncertainty visible.

## Product Mention Review Interface

The system provides two related interfaces:

- Inquiry-level popup from the Trading board and Inquiries page.
- Separate `Lists -> Inquiry Products` page for structured trace rows that already exist.

The inquiry-level popup is the primary workflow in the current phase.

The interface should show:

```text
Canonical Name | Direction | Contact | Account | Source Message | Suggested Match | Decision
```

Initial actions:

- Create as new inventory product. Implemented in current phase.
- Map to existing inventory product. Planned.
- Add alias/tag to an existing product.
- Dismiss/ignore.
- Open source inquiry.
- Open source message/conversation.

The user should be able to take further decisions from this queue without changing the original
message or losing the extracted product record.

## Mapping, Product Creation, And Traceability

Target state: every extracted product line should be stored first, even when it cannot be mapped to
inventory.

Current phase: extracted lines stay in `Inquiry.products` first. A structured `InquiryProduct` row
is created only when the user manually creates or later maps a product from that line.

If a product exists in inventory:

```text
InquiryProduct.product = existing Product
decision_status = mapped
```

If the product does not exist:

```text
InquiryProduct.product = null
decision_status = pending
```

In the current manual-first phase, the user can:

- Create a new inventory product from the extracted line.
- Review linked rows on the Inquiry Products page.

In later phases, the user should also be able to:

- Map the extracted line to an existing product.
- Dismiss the line if it is not useful.
- Add the sender wording as an alias candidate.

When a new product is created from an extracted line, the created `Product` should be linked back to
the `InquiryProduct`. The `InquiryProduct` remains historical evidence and should not be deleted.

When a line is mapped to an existing product, the sender's wording can be added as an alias/tag so
future incoming lines can map better.

This makes inventory traceability evidence-based:

```text
Product
  -> all related InquiryProduct rows
     -> source inquiries
        -> source messages
           -> contacts/groups/accounts
```

This traceability supports future analysis of how demand or supply spreads. For example, if one
party starts searching for a product and the same product later appears from other parties, the
system can show the first observed source message and the later related product mentions.

## Alias Discovery

When an inquiry product maps to inventory, the sender's wording can become an alias candidate.

Example:

```text
Sender wording: 17 Pro max 512gb Silver 1 Physical sim
Inventory product: Apple iPhone 17 Pro Max 512GB Silver Hong Kong
Alias candidate: 17 Pro max 512gb Silver 1 Physical sim
```

Alias should be added automatically only when confidence is high or the user manually confirms the match.

For safety, alias tracking can use a separate candidate model first.

Suggested model:

```text
ProductAliasCandidate
- company
- product
- alias_text
- source_inquiry_product
- source_message
- status
- confidence
- first_seen_at
- last_seen_at
- seen_count
- created_at
- updated_at
```

Suggested statuses:

```text
pending
confirmed
rejected
auto_confirmed
```

Confirmed aliases can later be promoted into the existing product alias table.

## Discovered Product Candidates

If a product mention does not map to inventory, it should not immediately create an active inventory product.

Instead, create or update a discovered product candidate.

Suggested model:

```text
DiscoveredProduct
- company
- canonical_name
- brand
- category
- normalized_key
- wtb_count
- wts_count
- first_seen_at
- last_seen_at
- status
- created_product
- created_at
- updated_at
```

Suggested statuses:

```text
pending
mapped
created
ignored
rejected
```

This allows a user to review frequent unmatched products and decide whether to:

- Map to an existing inventory product.
- Create a new inventory product.
- Ignore/reject the candidate.

## Tracking And Reporting Views

Initial reporting should expose:

- Product demand/supply summary.
- Unmatched product mentions.
- Frequently used aliases.
- High demand with low stock.
- High supply with low demand.

Suggested endpoint:

```text
GET /api/inquiry-products/summary/
```

Example response:

```json
[
  {
    "name": "Apple iPhone 17 Pro Max 512GB Silver Hong Kong",
    "product_id": 22,
    "wtb_count": 18,
    "wts_count": 4,
    "current_qty": 0,
    "unmatched": false
  },
  {
    "name": "17 Pro Max 512GB Silver HK",
    "product_id": null,
    "wtb_count": 9,
    "wts_count": 0,
    "current_qty": null,
    "unmatched": true
  }
]
```

## First Implementation Phase

Phase 1 should be additive only.

Steps:

1. Add `InquiryProduct` model.
2. Add migration.
3. Backfill `InquiryProduct` rows from existing `Inquiry.products`.
4. Update inquiry creation/update flow to write `InquiryProduct` rows alongside existing `Inquiry.products` JSON.
5. Add direct `InquiryProduct` embedding fields and embedding status fields.
6. Add internal/admin visibility to inspect stored `InquiryProduct` rows.
7. Verify that newly created inquiries consistently create structured product mention records.

Do not remove or replace `Inquiry.products` in this phase.

## Later Phases

Phase 2:

- Add product mention review UI.
- Add actions to map, create inventory product, add alias/tag, or dismiss.

Phase 3:

- Add alias candidate tracking if the direct review flow needs a staging layer.
- Use confirmed aliases during future inventory mapping.

Phase 4:

- Add richer analytics:
  - WTB/WTS mention counts
  - date range filters
  - account/company filters
  - group/contact source filters
  - demand vs inventory gap
  - supply vs demand imbalance

Phase 5:

- Gradually migrate UI and reports from `Inquiry.products` JSON to `InquiryProduct`.

## Development Principles

- Keep existing application behavior working.
- Do not silently change product matches.
- Log matching failures and AI failures clearly.
- Keep all AI instructions in `PromptConfig`.
- Keep tenant/company ownership on all tracking records.
- Prefer additive schema changes first, then migrate behavior after verification.
