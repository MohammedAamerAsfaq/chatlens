# Non-Inventory Product Data Quality Remediation

## Status

Proposed implementation. No cleanup or behavioral change has been applied yet.

This document extends `Inquiry Product Tracking Design.md`. Its purpose is to make the
non-inventory product dataset accurate enough for market analysis, semantic search, product
promotion, and future automation without deleting the original inquiry evidence.

## Problem Statement

The current pipeline treats every unmatched AI-extracted product line as a trustworthy product:

1. V2 extracts product lines from a message.
2. Inventory matching leaves some lines unmatched.
3. `_auto_track_non_inventory_products` sends every unmatched line to the resolver.
4. The resolver creates or reuses a `NonInventoryProduct` using a deterministic normalized key.
5. A mention is recorded and the canonical product is embedded immediately.

This is unsafe when extraction is wrong. Cross-line leakage, hallucinated variants, inconsistent
attributes, and repeated reposts can become durable canonical products and contaminate embedding
search and market statistics.

## Measured Baseline

Snapshot taken on 19 September 2026:

| Metric | Value |
|---|---:|
| Canonical non-inventory products | 38,514 |
| Mentions | 45,308 |
| Products with exactly one mention | 35,095 (91.1%) |
| Duplicate normalized-name groups | 4,977 |
| Products inside duplicate-name groups | 15,569 |
| Embedded products | 38,492 |
| Pending embeddings | 14 |
| Embedding errors | 8 |
| Products marked `tracking` | 38,514 |
| Products dismissed or merged | 0 |
| Mentions marked deterministic | 45,308 |
| Largest number of mentions from one message | 129 |

Examples of fragmentation include 59 canonical rows named `iphone 17 pro max 256gb`, 46 rows
named `iphone 18 pro max 256gb burgundy`, and 44 rows named `airpods 4 anc`.

## Root Causes

### Unverified Canonicalization

An unmatched AI line becomes canonical without proving that its model, storage, color, region,
condition, and quantity are present in the source message.

### Over-Specific Identity Keys

The normalized key combines the AI canonical name with every available identity attribute.
Equivalent products split when the AI changes spelling, casing, attribute keys, abbreviations, or
attribute placement.

### Misleading Confidence

Automatically created mentions use `deterministic` with a default confidence of `1.0`. This only
means the generated key matched itself; it does not establish that extraction was correct.

### Immediate Embedding

New records enter semantic search before validation. Bad records then become candidates for later
matching and can amplify earlier errors.

### Missing Review Operations

The model supports dismissed and merged states, but production UI/API flows do not currently
verify, reject, merge, split, or reassign mentions.

### Reposts and Source Duplication

Repeated identical messages inflate mention counts and apparent market depth unless commercial
signals are deduplicated separately from raw message evidence.

## Design Principles

1. Preserve original messages and mention evidence.
2. Stop new contamination before cleaning historical records.
3. Separate observed mentions from trusted canonical products.
4. Never silently merge weak matches.
5. Make every automated cleanup reversible and auditable.
6. Do not use unverified candidates in trusted semantic search or market totals.
7. Do not treat repeated reposts as independent market participants.
8. Keep inventory products and non-inventory candidates separated until promotion is approved.

## Target Trust Model

Add explicit lifecycle states:

- `candidate`: automatically observed but not trusted.
- `verified`: source-grounded canonical product approved for search and analytics.
- `rejected`: invalid extraction or non-product content; evidence remains available.
- `merged`: duplicate canonical row redirected to another product.
- `promoted_to_inventory`: approved and linked to an inventory product.

Existing `tracking` rows must not be assumed verified. During migration they should be treated as
legacy candidates until evaluated.

Each canonical product should also expose:

- `trust_score` from 0 to 1.
- `verification_source`: automatic, manual, merge review, or inventory promotion.
- `verified_at` and `verified_by`.
- `rejection_reason` where applicable.
- `quality_flags` containing machine-readable audit findings.

## Source-Grounding Validator

The validator runs before canonical product resolution. It evaluates the extracted line against
the exact original message, not the summary or candidate inventory products.

Checks include:

- Product family/model tokens occur in the source.
- Storage, memory, color, region, SIM type, condition, and SKU values are explicitly supported.
- Quantity and price occur near the applicable product line or section.
- The line is not a heading, total, date, phone number, or unrelated descriptive text.
- The extracted variant does not inherit attributes from another product line.
- WTB/WTS direction agrees with the message-level classification.
- The source product index maps to a valid parsed line.

Validator outcomes:

- `grounded`: eligible for candidate resolution.
- `ambiguous`: retain as a mention for review but do not create a trusted canonical product.
- `rejected`: retain audit evidence and exclude from canonical search.

The validator must store reasons and individual check results. It must not rewrite source data.

## Trust Scoring

The initial score should be deterministic and explainable. Suggested positive signals:

- Strong source grounding.
- Repeated mentions from independent contacts.
- Consistent normalized attributes across mentions.
- Exact SKU or model-code agreement.
- Manual verification.
- Successful inventory promotion.

Suggested penalties:

- Single mention only.
- Same contact reposting identical text.
- Conflicting model/storage/color attributes.
- Product name contains values absent from the source.
- Direction mismatch.
- Excessive product lines produced from one message.
- AI-only inferred identity with no source support.

Thresholds must be configurable and initially run in observational mode.

## Canonical Identity

Canonicalization should use a controlled product identity schema instead of raw AI phrasing:

- Product family and model are required.
- Identity attributes use normalized keys and controlled values.
- Display attributes that do not define identity must not fragment the key.
- Synonyms such as `TRA`, `TDRA`, and `UAE` require an explicit normalization policy.
- Units and casing must normalize consistently (`1 tb` to `1TB`, `256 gb` to `256GB`).
- Color and condition aliases must map to canonical values while preserving original text.

Canonical names should be generated from normalized identity fields. AI-provided names remain on
mentions as evidence but should not independently define identity.

## Embedding Policy

- Do not embed rejected records.
- Candidates must not participate in trusted matching by default.
- Verified records receive embeddings generated from canonical identity fields.
- A merge invalidates the source embedding and regenerates the target when its evidence changes.
- A correction to identity attributes requires embedding regeneration.
- Candidate search, if retained, must use a separate scope clearly labelled unverified.

## Historical Cleanup Workflow

Historical remediation begins only after source validation is active for new data.

### Audit

Run a read-only audit that assigns quality flags and proposed actions. Persist the audit run,
algorithm version, inputs, and counts.

### Cluster

Build duplicate clusters using normalized identity, source-grounded attributes, SKU equality, and
embedding similarity. Embeddings may propose clusters but cannot authorize a merge.

### Review

Operators can:

- Verify a canonical product.
- Correct its canonical identity.
- Merge duplicates into a selected target.
- Move a mention to another canonical product.
- Split mixed mentions into separate products.
- Reject a bad mention or entire canonical product.
- Promote a verified product to inventory.

### Apply

Approved changes execute transactionally:

1. Lock affected canonical products and mentions.
2. Reassign mentions.
3. Recalculate total, buy, and sell counters from mention rows.
4. Preserve source rows with `merged_into` or rejection metadata.
5. Write an immutable audit event.
6. Regenerate or invalidate embeddings after commit.

No cleanup job may hard-delete source messages, inquiries, or mention evidence.

## Deduplication Semantics

Maintain two counts:

- `raw_mention_count`: every stored occurrence for traceability.
- `commercial_signal_count`: deduplicated by company, account/contact identity, normalized source
  text, product identity, direction, and a configurable time window.

Repeated reposts remain visible but should not inflate market supply/demand analysis.

## UI Requirements

Extend the Non-Inventory Products screen with:

- Trust state and trust score columns.
- Quality-flag filters.
- Verified/unverified search scope.
- Duplicate-cluster review.
- Side-by-side canonical identities and source mentions.
- Original message context with highlighted supporting text.
- Verify, reject, merge, split, reassign, and undo controls.
- Dry-run batch preview with affected record counts.
- Audit history showing actor, time, reason, and before/after values.

Destructive-looking actions must describe that evidence is retained.

## API and Service Boundaries

Keep responsibilities separated:

- `source_grounding_service`: validates extracted lines against source messages.
- `non_inventory_identity_service`: normalizes identity fields and builds canonical keys.
- `non_inventory_resolution_service`: creates candidates or attaches grounded mentions.
- `non_inventory_quality_service`: calculates trust and quality flags.
- `non_inventory_cleanup_service`: produces dry-run merge/reject/reassign proposals.
- `non_inventory_review_service`: applies approved actions transactionally.
- `non_inventory_embedding_service`: enforces embedding eligibility and regeneration.

Background tasks should carry record or audit-run IDs, not complete product payloads.

## Phased Delivery

### Phase 1: Stop New Contamination

- Add source-grounding results and candidate state.
- Make new unmatched lines candidates by default.
- Prevent candidate embeddings from entering trusted search.
- Record quality metrics without changing historical rows.

### Phase 2: Observational Scoring

- Score candidates and legacy rows.
- Compare automatic findings against a manually labelled sample.
- Tune thresholds before enforcing verification or rejection rules.

### Phase 3: Review UI

- Add candidate verification, rejection, identity correction, and source inspection.
- Add duplicate clusters and manual merge operations.

### Phase 4: Historical Dry Run

- Audit all legacy rows.
- Produce proposed actions and impact reports.
- Review high-volume and high-risk clusters first.

### Phase 5: Controlled Cleanup

- Apply approved batches with rollback metadata.
- Rebuild counters and trusted embeddings.
- Validate market reports before and after each batch.

### Phase 6: Enforcement

- Enable configured automatic rejection for high-confidence invalid lines.
- Enable automatic verification only after measured precision meets the agreed threshold.

## Metrics

Track at least:

- New candidates per day.
- Source-grounding pass, ambiguous, and reject rates.
- Candidate-to-verified conversion rate.
- Duplicate canonical creation rate.
- Single-mention candidate rate.
- Repost deduplication rate.
- Merge, split, reassign, and reject volumes.
- Trusted embedding coverage and errors.
- Manual review agreement with automatic recommendations.
- Market-report changes caused by cleanup.
- False merge and false rejection rates from reviewed samples.

## Acceptance Criteria

- No ungrounded extracted line enters trusted canonical search.
- Every trusted product has source evidence or explicit manual approval.
- Every merge/rejection is auditable and reversible.
- Trusted market totals use deduplicated commercial signals.
- Counters equal their underlying mention records after every operation.
- Candidate and trusted embeddings cannot be confused by callers.
- Historical cleanup can run in dry-run mode with no mutations.
- Automated enforcement remains disabled until labelled-sample precision is approved.

## Rollout Safety

Before historical cleanup:

1. Back up the PostgreSQL database.
2. Export canonical products, mentions, counters, statuses, and embedding metadata.
3. Record the cleanup algorithm version and thresholds.
4. Test rollback on a restored database.
5. Start with a small reviewed batch.
6. Compare product search and market reports before proceeding.

## First Implementation When Work Resumes

Implement Phase 1 as one tested change:

1. Add candidate/trust and grounding audit fields.
2. Implement the source-grounding service.
3. Call it before non-inventory resolution.
4. Quarantine ambiguous/rejected observations.
5. Restrict trusted embedding and matching queries.
6. Add operational counters and logs.
7. Leave existing historical rows unchanged pending the dry-run cleanup phase.

