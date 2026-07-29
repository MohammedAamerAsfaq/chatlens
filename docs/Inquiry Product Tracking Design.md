# Inquiry Product Tracking Design

## Objective

Track product mentions from inquiries in a proper structured form.

The current phase is not focused on final analytics or report counting. If the data is stored
correctly, multiple reports can be built from it later. WTB/WTS demand and supply counts are only
two examples of reports that can be derived from the same structure.

The long-term business questions include:

- Which products are most requested by customers or buyers?
- Which products are most offered by suppliers?
- Which products have high demand but low or no inventory?
- Which products have high supply but low demand?
- Which product names are being used by parties but are not yet mapped to inventory?

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

## Proposed Design

Introduce a structured product mention layer.

The main model should be `InquiryProduct`.

Each extracted product line from an inquiry should create one `InquiryProduct` row.

The existing `Inquiry.products` JSON should remain for now to avoid breaking current UI behavior. The new model should run alongside it until the structured design is mature.

## Proposed Model: InquiryProduct

Suggested fields:

```text
InquiryProduct
- company
- inquiry
- source_message
- inquiry_type
- canonical_name
- original_text
- quantity
- price
- currency
- product
- match_status
- match_type
- match_source
- match_reason
- first_seen_at
- created_at
- updated_at
```

Field meaning:

- `company`: Tenant owner. Required for tenant isolation and analytics scoping.
- `inquiry`: Parent inquiry.
- `source_message`: Original WhatsApp message if available.
- `inquiry_type`: Snapshot of inquiry direction: `buy`, `sell`, or `both`.
- `canonical_name`: AI-normalized product name from the inquiry.
- `original_text`: Sender wording if available. This may initially be empty until line-level extraction improves.
- `quantity`: Requested/offered quantity if parsed.
- `price`: Requested/offered price if parsed.
- `currency`: Currency if parsed.
- `product`: Inventory product match, nullable.
- `match_status`: Current tracking status, such as `exact`, `near`, `unmatched`, `manual_confirmed`, or `rejected`.
- `match_type`: Original AI match type if applicable.
- `match_source`: How the product was matched, such as `ai`, `alias`, `deterministic`, or `manual`.
- `match_reason`: Short explanation for audit/debugging.
- `first_seen_at`: Inquiry/message time used for time-based analytics.

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
5. Add internal/admin visibility to inspect stored `InquiryProduct` rows.
6. Verify that newly created inquiries consistently create structured product mention records.

Do not remove or replace `Inquiry.products` in this phase.

## Later Phases

Phase 2:

- Add alias candidate tracking.
- Add UI to confirm/reject alias candidates.
- Use confirmed aliases during future inventory mapping.

Phase 3:

- Add discovered product candidate tracking.
- Add UI to map/create/ignore discovered products.

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
