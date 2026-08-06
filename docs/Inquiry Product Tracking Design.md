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

## Classification Versions

The current live inquiry classification pipeline is now treated as **Classification V1**.

V1 behavior:

- One AI pass receives the WhatsApp message, account/contact context, the inquiry-classification
  instruction, and the full in-stock product master block.
- AI classifies the message as inquiry/non-inquiry.
- AI decides `buy`, `sell`, or `both`.
- AI extracts product lines.
- AI attempts to match each product line against the supplied product master and returns
  `product_id`, `match_type`, and `canonical_name`.
- ChatLens validates the JSON shape and stores the result in `MessageClassification` and
  `Inquiry.products`.

V1 remains the default behavior until V2 is implemented, tested, and explicitly enabled.

The proposed retrieval-assisted pipeline is **Classification V2**.

V2 target behavior:

```text
Incoming WhatsApp message
  -> eligibility checks
  -> AI pass 1: classify intent and extract product lines only
  -> Inquiry created/updated immediately from pass 1
  -> Trading board displays the inquiry with pass 2 pending indicator
  -> ChatLens retrieves candidate inventory products for each extracted line
     using embeddings and safe structured filters
  -> AI pass 2: compare extracted line against shortlisted candidates only
  -> validated match decision updates the inquiry product lines
  -> manual InquiryProduct traceability workflow
```

V2 separates responsibilities:

- AI pass 1 extracts what the sender wrote. It should not decide inventory `product_id`.
- ChatLens searches inventory and produces a small candidate list.
- AI pass 2 judges only the shortlisted candidates and returns exact/near/no-match decisions.
- ChatLens stores the candidates considered and the final match decision for auditability.

V2 user-visible behavior:

- As soon as pass 1 confirms that the message is an inquiry and extracts product lines, the inquiry
  should appear on the Trading board.
- The Trading board card should clearly show that product matching is still in progress, for
  example: `Product matching in progress...`.
- This message should appear near the bottom of the inquiry card content so users know the inquiry is
  visible but final inventory matching is not completed yet.
- The inquiry should not wait for pass 2 before becoming visible.
- The `Inquiry Products` popup should show the extracted product list from pass 1 immediately.
- The pass-1 extracted product list should remain stable and visible even while pass 2 is running.
- Pass 2 may later update match fields such as `product_id`, `match_type`, candidates considered,
  match reason, and confidence, but it should not remove the pass-1 extracted line from the popup.

Expected advantages of V2:

- Avoids sending the full inventory catalog with every message.
- Reduces prompt size and AI cost as product count grows.
- Reduces product-match mistakes caused by forcing AI to search a large catalog.
- Makes match decisions easier to debug because the considered candidate list can be stored.
- Allows gradual account-by-account rollout without breaking current V1 behavior.

V2 must not silently replace V1. It should be selectable, observable, and reversible.

## Version Selection And Account Settings

Classification version selection should be account-level.

Required behavior:

- There should be one tenant/company default classification version.
- Every WhatsApp account should inherit the company default unless explicitly overridden.
- A control company super user can change the company default.
- A control company super user can override the classification version for an individual account.
- Existing accounts should continue on V1 by default after migration.
- The selected version must be visible in account settings.
- The AI Parsing Log and Agent Call Log should record which classification version handled a
  message.

Suggested setting values:

```text
inherit
v1
v2
```

Effective version resolution:

```text
if account.classification_version_override is v1 or v2:
    use account override
else:
    use company default
```

Initial defaults:

```text
company.default_classification_version = v1
account.classification_version_override = inherit
```

This keeps the current application behavior unchanged until the user intentionally enables V2 for a
company or a specific account.

Implementation status:

- Company default classification version field exists.
- WhatsApp account classification version override field exists.
- Effective version resolves as account override first, otherwise company default.
- Tenant Admin exposes the company default selector.
- Account settings expose the account override selector.
- AI Parsing Log, Agent Call Log, MessageClassification, and Inquiry can store the version.
- V1 remains the active default and preserves current behavior.
- V2 two-pass classification is implemented as one extraction call plus one batched match-decision
  call per message.
- V2 pass 1 creates/updates the inquiry immediately with `product_match_status = pending`.
- V2 pass 2 retrieves tenant-scoped in-stock product candidates for every extracted product line,
  sends all product lines and their candidate lists to AI in one batched request, then updates
  `MessageClassification.products` and `Inquiry.products`.
- If V2 pass 2 fails, the inquiry is marked `product_match_status = error` with the error text.
- A dedicated `AI Parse V2 Logs` screen records the pass 1 request, pass 1 response, parsed pass 1
  output, pass 2 request, pass 2 response, parsed pass 2 output, status, and error text.
- V2 is still a new path and should be tested on one account before enabling as a company default.

## AI Instruction Versioning

AI instructions must be version-specific.

Current prompt:

```text
inquiry_classification
```

This should be treated as the V1 prompt.

Suggested V2 prompt keys:

```text
inquiry_classification_v1
inquiry_extraction_v2
inquiry_match_decision_v2
```

Compatibility approach:

- Keep the existing `inquiry_classification` key as an alias/fallback for V1 so existing saved
  tenant prompt overrides do not break.
- Introduce `inquiry_classification_v1` for clear naming going forward.
- Introduce `inquiry_extraction_v2` for pass 1.
- Introduce `inquiry_match_decision_v2` for pass 2.

V2 pass 1 instruction should focus only on:

- whether the message is a genuine inquiry
- inquiry direction: `buy`, `sell`, or `both`
- product lines exactly as stated
- normalized/canonical product text
- manufacturer/product brand when explicitly stated, or the best safe inference from well-known
  product families
- commonly available product-defining attributes such as Series, Model, Storage, Color, Region,
  SIM Type, Network, Condition, and Variant
- quantity, price, currency
- summary
- dedup key
- contact role suggestion

V2 pass 1 must not receive the full product master and must not return inventory `product_id`.
The extracted brand is not an inventory match; it is a hard retrieval constraint. When pass 1
returns a brand, pass 2 candidate selection should search only active in-stock products for the same
tenant and brand. If no same-brand candidates exist, ChatLens should send no candidates for that line
instead of falling back to unrelated high-scoring embeddings from another brand.
Brand correction must be handled through AI instructions or future data-backed brand alias models,
not through hardcoded product-family mappings in code.
Extracted attributes are also retrieval constraints, but only when the same attribute key already
exists in that tenant's active in-stock inventory. This prevents free-form fields that are not yet
modeled in inventory from eliminating every candidate, while still stopping obvious wrong candidates
such as a different color, storage size, series, or model from entering pass 2 when those attributes
are present in both the inquiry and inventory.
If candidate retrieval returns no candidates for every extracted product line, ChatLens must not call
AI pass 2. It should mark those lines unmatched with a clear no-candidate reason, complete the inquiry
matching status, and write the skipped decision into the V2 parse log. If only some lines have no
candidates, pass 2 should be called only for the candidate-backed lines and the no-candidate lines
should be merged back as deterministic unmatched results.

V2 pass 2 instruction should receive:

- original WhatsApp message
- all extracted product lines from the message
- each line's shortlisted inventory candidates generated by ChatLens
- strict exact/near/no-match rules

V2 pass 2 should return:

```json
{
  "results": [
    {
      "line_index": 0,
      "product_id": 123,
      "match_type": "exact",
      "confidence": 0.92,
      "reason": "Model, tier, storage, color, and region all match.",
      "rejected_candidate_ids": [124, 130]
    }
  ]
}
```

If no candidate is acceptable:

```json
{
  "results": [
    {
      "line_index": 0,
      "product_id": null,
      "match_type": null,
      "confidence": 0,
      "reason": "No candidate matches the requested color and region.",
      "rejected_candidate_ids": [124, 130]
    }
  ]
}
```

All prompt bodies must remain editable through `PromptConfig` and visible in the AI Instructions
screen. No classification instructions should be hardcoded outside the prompt defaults except the
minimal parser/validator schema rules required to reject invalid AI output.

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

## Non-Inventory Tracking Phase 1

Purpose:

Track product lines that are mentioned in inquiries but are not currently mapped to an inventory
`Product`. These records allow ChatLens to measure demand/supply trends for products that are not
yet part of the stock list, without forcing the user to create inventory rows prematurely.

This phase is schema-only. It does not yet change inquiry processing, AI parsing, inventory matching,
or trading board behavior.

### Implemented Models

`NonInventoryProduct`

Canonical product concept for an item not currently in inventory.

Key fields:

- `company`: tenant owner.
- `canonical_name`: display name for the tracked non-inventory item.
- `normalized_name`: normalized searchable name.
- `normalized_key`: deterministic identity key built later from brand plus normalized product-defining attributes.
- `brand`: product brand when known.
- `attributes`: JSON product-defining attributes such as series, model, storage, color, region, SIM type, condition, and variant.
- `status`: `tracking`, `promoted_to_inventory`, `dismissed`, or `merged`.
- `promoted_product`: optional link to inventory `Product` when the item is later added to stock.
- `merged_into`: optional link to another `NonInventoryProduct` when duplicate tracked products are merged.
- `mention_count`, `buy_mention_count`, `sell_mention_count`: denormalized counters for reporting.
- `embedding`, `embedding_model`, `embedding_metadata`, `embedding_status`, `embedding_error`: prepared for later semantic matching.
- `first_seen_at`, `last_seen_at`: trend window markers.

Uniqueness guard:

- `company + normalized_key` is unique when `normalized_key` is not blank.
- This prevents deterministic duplicate canonical products once the resolver starts generating stable keys.

`NonInventoryProductMention`

Occurrence-level record for every inquiry/message mention linked to a non-inventory product.

Key fields:

- `company`: tenant owner.
- `non_inventory_product`: canonical tracked product.
- `inquiry`: inquiry where the item appeared.
- `inquiry_product`: optional link to the structured `InquiryProduct` row.
- `source_message`: original WhatsApp message.
- `account`, `contact`, `company_contact`: source ownership/contact context.
- `inquiry_type`: buy/sell direction.
- `source_product_index`: original product-line index from AI extraction.
- `raw_text`: sender wording.
- `canonical_name_from_ai`, `normalized_name_from_ai`, `brand_from_ai`, `attributes_from_ai`: AI-extracted product details at the time of mention.
- `quantity`, `price`, `currency`: commercial details from the inquiry line.
- `match_source`: `deterministic`, `embedding`, `ai`, or `manual`.
- `match_confidence`, `match_reason`: audit detail explaining why this mention was linked to the tracked product.
- `message_time`: source message time.

Duplicate mention guard:

- `company + inquiry_product` is unique when `inquiry_product` is present.
- This prevents the same structured inquiry product line from being linked repeatedly.

### Intended Future Flow

The future resolver should run only after normal inventory matching has completed.

```text
WhatsApp message
  -> AI inquiry extraction
     -> inventory matching
        -> matched product_id: normal inventory traceability
        -> product_id null: non-inventory resolver
             -> find/create NonInventoryProduct
             -> create NonInventoryProductMention
```

Matching should be layered:

1. Deterministic `normalized_key` match.
2. Attribute-aware comparison.
3. Embedding search against non-inventory products.
4. AI comparison only when deterministic/embedding confidence is ambiguous.
5. Manual review when confidence is still weak.

Strict principle:

Do not silently merge weak non-inventory matches. A bad merge corrupts trend analytics. If the
resolver is unsure, it should either create a separate tracked product or mark the candidate for
manual review.

### Admin Visibility

Both models are registered in Django admin for early inspection:

- `NonInventoryProduct`
- `NonInventoryProductMention`

This is intentionally basic visibility only. Dedicated UI, APIs, resolver service, promotion,
manual merge, and reporting are later phases.

## Non-Inventory Tracking Phase 2A

Implemented next small step:

`apps.trading.services.non_inventory_product_service`

This service provides deterministic non-inventory resolution, but it is not yet wired into live
inquiry processing.

Current capabilities:

- Build a normalized product name using the same product-name normalization used by `InquiryProduct`.
- Build a deterministic `normalized_key` from:
  - brand
  - canonical product name
  - known product-defining attributes
- Product-defining attributes currently considered:
  - `Series`
  - `Model`
  - `Storage`
  - `Color`
  - `Region`
  - `SIM Type`
  - `Network`
  - `Condition`
  - `Variant`
- Resolve an unmatched extracted product line to an existing `NonInventoryProduct` by `company + normalized_key`.
- Create a new `NonInventoryProduct` when no deterministic match exists.
- Create a `NonInventoryProductMention` linked to:
  - inquiry
  - optional `InquiryProduct`
  - source message
  - account
  - contact/company contact
- Update mention counters only when a new mention is created:
  - total mentions
  - buy mentions
  - sell mentions
  - last seen time
- Fail loudly with `NonInventoryResolutionError` when required data is missing or a mention would be linked to a different already-resolved product.

Important boundary:

This phase does not perform embedding search, AI matching, manual review, UI display, reporting, or
automatic invocation from inquiry creation. It only provides a safe deterministic foundation for the
next integration step.

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
