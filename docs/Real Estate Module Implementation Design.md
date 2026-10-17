# ChatLens Real Estate Module Implementation Design

**Status:** Foundation, live classification, verified inventory, embeddings, and prospect-path alignment implemented
**Prepared:** 8 October 2026  
**Last updated:** 13 October 2026
**Target industry:** `real_estate`

## 1. Purpose

This document defines the implementation plan for adding Real Estate as a first-class ChatLens industry. The module will interpret incoming communication in the context of a real-estate business and support exactly four user-facing activities:

- Buying
- Selling
- Leasing Inquiry
- Leasing Offer

Real Estate will have its own property inventory, listings, opportunities, matching, viewings, commercial offers, deals, AI instructions, task handlers, APIs, permissions, navigation, reports, and settings. It will reuse the industry-neutral ChatLens platform services without depending on trading-domain models.

## 2. Existing Foundation

The current tenancy model already supports `industry_type='real_estate'`. The established multi-industry strategy also requires new industries to use separate domain applications rather than converting `trading.Product` into a universal business object.

The following current platform capabilities are reusable:

- company tenancy and company switching;
- users, roles, permissions, and record scopes;
- WhatsApp accounts, contacts, groups, chats, and messages;
- live and history ingestion;
- durable task queues and Task Operations monitoring;
- AI providers and KiwiRouter;
- message and domain-object embeddings;
- Inbox and outbound message delivery;
- sending policy, preflight, throttling, and attachments;
- ClientPulse profiles, reminders, notes, consent, and activities;
- integrations and company-level reporting infrastructure;
- shared Inspinia UI components and data tables.

The following existing implementation points are currently trading-specific and must be extended through the same established patterns before Real Estate is connected to live ingestion:

- classification dispatch directly selects trading handlers;
- AI instruction storage uses the company-owned, domain-specific `trading.PromptConfig` pattern;
- embedding dispatch directly imports trading models;
- campaign business models are stored inside the trading application;
- frontend navigation is permission-aware but not fully industry-aware.

## 3. Architectural Principles

### 3.1 Existing architecture conformance

This is a binding implementation constraint. Real Estate must extend ChatLens through the architecture, code patterns, and visual design already in production. It must not introduce a parallel framework merely because it is a new business domain.

Required backend patterns:

- Django application boundaries under `apps/`;
- company-scoped models and querysets using the existing tenancy services;
- DRF serializers, viewsets/API views, URL registration, and service-layer separation consistent with current applications;
- durable PostgreSQL tasks using `BackgroundTask`, `BackgroundTaskEvent`, `task_handler`, payload validators, and `enqueue_task`;
- queues created through `QueueDefinition` data migrations and configured through the existing Task & Queues database settings;
- schedules created through `BackgroundTaskSchedule` and the existing task scheduler;
- existing correlation, idempotency, retry, timeout, heartbeat, worker registry, safe-stop, and Task Operations behavior;
- existing company-owned AI provider and KiwiRouter selection;
- lazy imports inside task handlers to avoid worker-startup side effects.

Required frontend patterns:

- existing Vue router, API client, stores, navigation, and permission guards;
- shared `UiPage`, `UiPageHeader`, `UiCard`, `UiToolbar`, `UiButton`, `UiInput`, `UiSelect`, `UiDatePicker`, `UiModal`, `UiDataTable`, and inline-editor components;
- existing Inspinia theme variables, responsive layout, loading, empty, error, modal, and data-grid behavior;
- module-based and reusable component organization rather than page-specific duplicate controls.

Do not add Celery, Redis, another queue broker, daemon-thread execution, another scheduler, another operations monitor, or a second UI component framework. Do not broadly refactor working Trading behavior as a prerequisite. Any shared extension must be backward-compatible and covered by Trading regression tests.

Use these established implementations as the reference for each extension:

| Concern | Existing reference pattern | Real Estate extension |
|---|---|---|
| Company ownership | `apps.tenancy` company, membership, permissions, and scoped queries | Non-null company ownership and the same authorization flow |
| Durable tasks | `apps.task_management.registry.task_handler` and `apps.queue_management.services.enqueue_task` | Versioned `real_estate.*` handlers and payload validators |
| Queue configuration | `QueueDefinition` data migrations and Task & Queues UI | Four new queue rows in the same control plane |
| Task company validation | ClientPulse versioned payload plus task-company comparison | Require `company_id` and compare it with `BackgroundTask.company_id` |
| AI instructions | Company-owned `trading.PromptConfig` with provider/KiwiRouter selection | Domain-owned `RealEstatePromptConfig` with matching behavior |
| AI routing | Existing `AIProviderConfig`, `KiwiRouter`, and provider call logging | Reuse unchanged through Real Estate prompt selection |
| Outbound delivery | Existing outbound preflight, policy, throttling, media, and queue | Reuse unchanged for Real Estate campaigns and replies |
| Operations | Existing Task Operations workers, queues, tasks, scheduler, and event ledger | Real Estate queues and task events appear in the same screens |
| Frontend controls | Shared `frontend/src/components/ui` components and Inspinia theme | Compose the same components in Real Estate views |

Before implementing each phase, identify its existing reference module and preserve its naming, validation, error response, audit, test, and UI interaction conventions. Where no reference exists, add the smallest backward-compatible extension rather than a replacement architecture.

### 3.2 Separate domain application

Create a dedicated Django application and frontend feature area:

```text
apps/real_estate/
frontend/src/features/real-estate/
frontend/src/views/real-estate/
```

All Real Estate domain models must be owned by a company from their first migration. New domain tables must not permit unowned legacy rows.

Every Real Estate table must therefore have a non-nullable `company` foreign key in its initial migration. There must be no global records, nullable ownership, or implicit fallback ownership. The existing Control Account may own the initial Real Estate records, settings, instructions, and test data. Control Account ownership is ordinary tenant ownership and does not make those records visible to other companies.

### 3.3 Shared platform, isolated business meaning

Shared platform services remain industry-neutral. Real Estate must reuse those services through stable interfaces, not by importing trading models or copying large trading services.

Real Estate must not reuse:

- `trading.Product` for properties;
- `trading.Inquiry` for property inquiries;
- trading price or quantity automation;
- supplier/customer contact classification as real-estate party roles;
- product-specific matching prompts or embeddings.

### 3.4 Industry-selected processing

Live-message business processing must continue using the existing `Company.industry_type` field:

```text
WhatsApp live message persisted
  -> resolve owning company
  -> resolve company industry_type
  -> dispatch trading, real-estate, or general pipeline
  -> enqueue industry task
```

Extend the existing classification dispatch service with one industry-aware entry point rather than introducing a second ingestion mechanism:

```python
def enqueue_company_classification(message, company) -> bool:
    if company.industry_type == Company.INDUSTRY_TRADING:
        return enqueue_trading_classification(message)
    if company.industry_type == Company.INDUSTRY_REAL_ESTATE:
        return enqueue_real_estate_classification(message)
    return False
```

The Trading branch must delegate to the current Trading classification dispatcher without changing its task keys or behavior. The Real Estate branch must enqueue the new Real Estate gate task. WhatsApp ingestion remains responsible only for persistence and dispatch.

No new module-entitlement table is required for the initial implementation. The Control Account may own initial Real Estate data because ownership and active industry are separate concerns. When the Control Account is used for live Real Estate testing, configure its existing `industry_type` as `real_estate` for that test workspace. Simultaneous Trading and Real Estate pipelines inside one company are outside the initial scope and require a separate reviewed design if later needed.

### 3.5 Backend enforcement

Industry separation cannot be a frontend-only navigation rule. Every Real Estate API must verify:

- authenticated user;
- active company membership;
- required permission;
- company validity;
- `current_company.industry_type == 'real_estate'`;
- record ownership by the selected company.

## 4. Activity Semantics

The domain has exactly four activities. Use one canonical field everywhere in models, APIs, task payloads, AI schemas, filters, reports, and user interfaces:

```text
activity_type: buying | selling | leasing_inquiry | leasing_offer
```

| Activity | Exact meaning |
|---|---|
| Buying | A person wants to buy a property |
| Selling | A person is advertising a property for sale |
| Leasing Inquiry | A person wants to rent or lease a property |
| Leasing Offer | A person is advertising a property for rent or lease |

Do not store parallel direction fields such as `market_side`, `lease_direction`, or a second activity-like transaction field. Sale-versus-lease and inquiry-versus-offer can be derived from `activity_type` when needed. Removing duplicate dimensions prevents contradictory combinations.

The four activities are mutually exclusive. `not_real_estate` and `needs_review` are processing outcomes, not activities. The AI must return one top-level decision only:

```text
decision: buying | selling | leasing_inquiry | leasing_offer | not_real_estate | needs_review
```

Persistence translates that single decision into:

```text
classification_status: classified | needs_review | not_real_estate
activity_type: buying | selling | leasing_inquiry | leasing_offer | null
```

`activity_type` is required only when `classification_status=classified`. If a real-estate message does not clearly indicate one of the four activities, store `classification_status=needs_review`, leave `activity_type` null, and prohibit automatic matching or forwarding. A user can then select one of the four activities. `not_real_estate` means the message is outside the Real Estate domain.

Apply database check constraints so a classified record must have exactly one activity and a review/not-real-estate record must have no activity. Useful derived values may be exposed by code, but must not become independently editable database fields:

```text
is_requirement = activity_type in (buying, leasing_inquiry)
is_property_offer = activity_type in (selling, leasing_offer)
listing_type = sale for buying/selling; lease for leasing_inquiry/leasing_offer
```

### 4.1 Prospect selection dimensions

The prospect path adds independent dimensions without changing the canonical four-value activity contract:

```text
market_scope: local | regional | international
ownership_eligibility: locals_only | gcc_only | all
tenure_type: freehold | long_lease | lease_99_year
```

For Local opportunities, the selected UAE emirate is stored as structured location criteria. Regional and International remain supported scopes, but their selectable geography must come from configured location data rather than hard-coded assumptions. Ownership eligibility and tenure are separate fields because a Freehold property can still have a Locals Only, GCC Only, or All eligibility rule.

The global geography hierarchy is now implemented in `apps.integrations`: control administrators can synchronize countries, first-level administrative areas, city anchors, and localities from GeoNames through the durable `integrations` queue. GeoNames administrative seats become city anchors; other populated places become localities and remain explicitly unmapped when no reliable city parent is supplied. Company-owned project/building masters complete the canonical path. Property addresses can reference every canonical level while preserving all raw and normalized source values. See `Global Geography and Integrations Implementation.md`.

These values belong to the requirement, offered-property candidate, property, or listing context where applicable. They must not be stored as permanent ClientPulse classifications because one client may have several opportunities with different eligibility, tenure, location, and activity requirements.

## 5. Domain Model

Every model in this section must contain its own non-nullable `company` foreign key, even when the company could be inferred through another relationship. Company-scoped querysets plus serializer, model, and service validation must reject relationships between records owned by different companies.

### 5.1 Property

`Property` represents the physical property or unit. It is distinct from a commercial listing.

Recommended fields:

- `company`;
- `reference_code`;
- `property_type`;
- optional parent property or building;
- title and description;
- bedrooms and bathrooms;
- built-up and plot area;
- configured area unit;
- furnishing status;
- completion status;
- developer and project name;
- construction/completion year;
- availability status;
- assigned user;
- source and external source identifier;
- active/archive state;
- created and updated timestamps.

Recommended statuses:

```text
draft | available | reserved | sold | leased | inactive
```

### 5.1.1 Property Type Master

Property types are not a fixed application enum. `PropertyType` is a directly company-owned master record with a stable code, display name, category, description, sort order, and active state. `Property` and `PropertyCandidate` reference this master with protected foreign keys. Requirements retain an array of stable type codes because one requirement can accept several types.

Default types are seeded for Real Estate companies during enrollment. Operators can add, edit, deactivate, and reactivate company-specific types from the Properties screen. Deactivation prevents new selection without invalidating existing inventory, candidates, requirements, imports, or audit history. The fallback `other` type cannot be deactivated.

Supported area units are `sqft`, `sqm`, `sqyd`, `acre`, and `hectare`. Numeric area values are always stored with their selected unit and are never silently converted or replaced.

### 5.1.2 Inventory provenance and tracking

The Real Estate inventory experience exposes four user-facing views:

- **Own Inventory:** verified properties owned by the company;
- **Authorized Inventory:** properties or requirements for which the company is authorized to buy, sell, or lease;
- **Floating Inventory:** provisional property information extracted from inbound requirements and offers;
- **Tracked Inventory:** records a user explicitly chooses to monitor from Own, Authorized, or Floating inventory.

The persistent source classification is:

```text
inventory_source_type: own | authorized | floating
is_tracked: true | false
```

Tracked is intentionally a separate flag rather than a fourth source value. This preserves whether a tracked record originated as Own, Authorized, or Floating inventory. The UI may present Tracked Inventory as a fourth filter or section.

Authorized is a loose inventory filter only. No separate purchase, sale, or lease authorization flags are required. The existing opportunity activity and listing type already identify whether the record concerns buying, selling, or leasing.

Floating inventory does not bypass the existing trust boundary. AI-extracted demand remains a `PropertyRequirement`, and AI-extracted supply remains a `PropertyCandidate` until reviewed. The unified inventory UI may project those records as Floating Inventory, but it must not silently promote them into verified `Property` or active `Listing` rows.

### 5.1.3 Property-type field definitions

Property types require different details. Plot-specific fields are not relevant to an apartment, while bedroom fields are not relevant to most warehouses. Follow the existing configurable-master pattern by adding company-owned, property-type field definitions and typed values instead of adding every possible field as a nullable column on `Property`.

The initial field definitions are system-seeded and are not user-configurable. User-managed field definitions can be considered later without changing the stored contract. Common, frequently filtered values such as location, bedrooms, bathrooms, area, budget, ownership eligibility, and tenure remain typed first-class fields.

For Plot, the initial schema includes:

- `area`: total plot size;
- `gross_floor_area`: total permitted floor area across all floors;
- `built_up_area`: actual constructed area, when applicable;
- `view`: road, sea, park, or another outlook;
- `master_developer`: developer responsible for the wider project;
- `use`: residential, commercial, industrial, or mixed use;
- `far`: floor area ratio, calculated as permitted gross floor area divided by plot area.

Conditional definitions must support rules such as requesting a district-cooling company only when the selected AC type is district cooling.

### 5.2 PropertyAddress

Store searchable location fields separately from descriptive property data:

- country;
- emirate/state/region;
- city;
- community/district;
- project/building;
- street;
- unit number;
- postal code;
- latitude and longitude;
- normalized location text.

The canonical hierarchy is:

```text
Country -> Emirate/Administrative Area -> City -> Locality/Community -> Project/Building
```

`Country`, `AdministrativeArea`, `City`, and `Locality` are shared platform reference data. `PropertyDevelopment` is directly company-owned and distinguishes projects from buildings; a building may reference a parent project. `PropertyAddress` stores nullable protected foreign keys to each level in addition to the raw fields above. Canonical mapping is additive: it never replaces imported text, coordinates, or normalized-location values.

### 5.3 PropertyMedia

`PropertyMedia` stores ordered images, video references, floor plans, brochures, and supporting documents. It must use existing company-scoped media storage and file-size/type validation.

### 5.4 Listing

`Listing` represents a sale or lease offer for a property. One property can have multiple historical listings, but conflicting active listings must be validated.

Recommended fields:

- `company` and `property`;
- `listing_type: sale | lease`;
- asking price and currency;
- lease payment frequency;
- deposit, commission, and payment terms;
- available-from date;
- listing status;
- assigned agent;
- source contact and source message;
- publication and expiry timestamps;
- verification status;
- created and updated timestamps.

Recommended statuses:

```text
draft | active | paused | expired | closed
```

### 5.5 RealEstateOpportunity

`RealEstateOpportunity` is the umbrella record for one inbound Buying, Selling, Leasing Inquiry, or Leasing Offer activity. Using “opportunity” here avoids incorrectly calling Selling and Leasing Offer records inquiries.

Recommended fields:

- `company`, WhatsApp account, contact, and company contact;
- source chat and source type;
- `activity_type` and `classification_status`;
- summary and original-message snapshot;
- status and assigned user;
- confidence and review state;
- pipeline and matching status;
- deduplication key;
- first-seen, closed, created, and updated timestamps.

Recommended statuses:

```text
new | qualified | matched | contacted | viewing | negotiation | won | lost | irrelevant
```

### 5.6 PropertyRequirement

`PropertyRequirement` stores structured criteria for a Buying or Leasing Inquiry opportunity:

- opportunity;
- one or more acceptable locations;
- acceptable property types;
- minimum and maximum bedrooms/bathrooms;
- minimum and maximum area;
- minimum and maximum budget;
- currency;
- furnishing preference;
- move-in or purchase timeframe;
- required and preferred amenities;
- free-form constraints;
- extraction confidence and review status.

Frequently filtered values must use typed fields or related tables. JSON should be limited to raw extraction payloads and genuinely variable secondary attributes.

### 5.7 PropertyCandidate

An inbound Selling or Leasing Offer message must create an unverified `PropertyCandidate`, not trusted inventory. A user must verify, merge, or promote it into `Property` and `Listing` records. This protects inventory quality from AI errors and incomplete advertisements.

### 5.8 OpportunityMessage

`OpportunityMessage` links all relevant WhatsApp messages to the opportunity. It supports follow-up context without changing the identity of the original opportunity.

### 5.9 PropertyMatch

`PropertyMatch` records a requirement-to-listing candidate and must include:

- opportunity and requirement;
- listing and property;
- deterministic compatibility result;
- embedding similarity;
- optional AI reranking score;
- combined score and explanation;
- attribute-level match details;
- accepted/rejected/review state;
- reviewer and review timestamp;
- snapshots of important listing values at match time.

Recommended statuses:

```text
suggested | reviewed | accepted | rejected
```

### 5.10 Operational pipeline models

Later workflow phases should add:

- `ViewingRequest` for scheduled viewings, attendees, reminders, and outcomes;
- `PropertyOffer` for proposed prices, terms, validity, and negotiation status;
- `RealEstateDeal` for won/lost transactions and agreed terms;
- `RealEstatePartyRole` for buyer, seller, landlord, tenant, owner, broker, and agent roles;
- `RealEstateParseLog` for complete AI and task auditing;
- `RealEstateSettings` for company-level behavior.

## 6. AI Instructions and Routing

### 6.1 Domain-owned instruction configuration

Follow the existing `trading.PromptConfig` architecture instead of introducing a new shared instruction framework during the Real Estate rollout. Add a company-owned `RealEstatePromptConfig` inside `apps/real_estate` with the same established behavior:

- non-nullable company ownership and a unique company/key constraint;
- workflow key and label;
- prompt body;
- direct `AIProviderConfig` or `KiwiRouter` selection;
- company ownership validation for the selected provider or router;
- `get_body`, `get_agent_config`, and `get_kiwi_router` accessors or equivalent domain service methods;
- updated timestamp and audit information consistent with existing models.

Real Estate code must not import `trading.PromptConfig`, and Trading prompt records must not be migrated or modified. A shared abstraction may be considered later only after both domains are stable and only if it preserves the existing API and behavior.

### 6.2 Real Estate workflow keys

Seed the following instructions for every company whose `industry_type` is `real_estate`, including the Control Account when it is configured as the initial Real Estate workspace:

- `real_estate_gate`;
- `real_estate_intent_extraction`;
- `real_estate_requirement_extraction`;
- `real_estate_listing_extraction`;
- `real_estate_match_decision`;
- `real_estate_summary`;
- `real_estate_campaign_format`.

Each instruction must independently select a direct agent or KiwiRouter.

### 6.3 GatePass

GatePass must support:

- `observational`: record the decision but continue processing;
- `enforced`: stop when the message is not a real-estate activity.

The gate should answer only what is necessary to reduce cost and latency. False positives can be discarded later; false negatives hide genuine opportunities and must be measured carefully.

### 6.4 Structured extraction

Extraction output must be validated against a versioned schema before domain records are written. Invalid outputs must retry according to task policy and remain visible in Task Operations and parse logs.

If a low-cost agent can return a reliable complete structured result, intent and property extraction may be combined. Matching should remain a separate operation and should run only when matching is required.

## 7. Durable Task Flow

The production flow must not use daemon threads. Real Estate business processing must use queues that are logically separate from Trading queues so Real Estate load, provider delays, retries, and failures cannot block Trading work.

### 7.1 Queue flow

```text
live_ingestion
  -> company industry dispatcher
  -> real_estate_gate: real_estate.gate_message
  -> real_estate_extract: real_estate.extract_message
  -> validate and persist opportunity/candidate/requirement
  -> real_estate_match: real_estate.match_opportunity when required
  -> project ClientPulse activity
```

Dedicated Real Estate queues:

- `real_estate_gate`;
- `real_estate_extract`;
- `real_estate_match`;
- `real_estate_maintenance`.

| Queue | Responsibilities | Isolation reason |
|---|---|---|
| `real_estate_gate` | Real Estate relevance gate and low-cost initial decision | Keeps fast gating available when extraction is slow |
| `real_estate_extract` | Four-activity classification, structured extraction, schema validation, and persistence | Isolates the main AI workload and its retries |
| `real_estate_match` | Deterministic filtering, embedding search, optional AI reranking, and match persistence | Prevents expensive matching from delaying new-message classification |
| `real_estate_maintenance` | Listing expiry, stale-data checks, repair tasks, and scheduled Real Estate jobs | Separates scheduled/bulk work from live processing |

### 7.2 Shared platform queues

The following remain shared because they perform industry-neutral platform work:

- `live_ingestion` persists live messages and dispatches them from `Company.industry_type`;
- `embeddings` remains shared while explicit registered task handlers select the Real Estate embedding service;
- `outbound` remains shared so all modules use the same WhatsApp preflight, policy, throttling, attachment, and delivery controls.

If monitoring later proves that Real Estate embedding volume delays other domains, a dedicated `real_estate_embeddings` queue may be introduced without changing domain contracts. It is not required for the initial implementation.

### 7.3 Queue granularity

Do not create separate queues for Buying, Selling, Leasing Inquiry, and Leasing Offer. The activity is unknown before extraction, and all four activities use the same validation and persistence pipeline. Splitting by activity would multiply worker and settings management without providing useful isolation.

Do not create a physical queue per company initially. Every task must carry `company_id`, and the handler must resolve all records within that company. Per-company queues should be considered only if measured tenant volume requires dedicated capacity or service-level isolation.

One worker process may subscribe to all four Real Estate queues during initial low-volume deployment. The queues must remain logically distinct so independent worker pools, concurrency, and timeout policies can be assigned later without changing task handlers.

The implementation must use the existing queue code pattern:

- create four `QueueDefinition` rows through a reversible `queue_management` data migration;
- register versioned task keys with `@task_handler` in `apps/real_estate/task_handlers.py`;
- add the Real Estate handler module to the existing `_ensure_task_handlers_registered()` import list;
- validate versioned payloads before enqueueing;
- include `company_id` in each payload and set `BackgroundTask.company` when calling `enqueue_task`;
- validate that payload company and task company match, following the existing ClientPulse handler pattern;
- use default queues declared by each task registration rather than hardcoding queue names at every call site;
- expose the queues automatically through the existing Task Operations and Task & Queues screens;
- run them with the existing `run_background_tasks --queue ...` worker command and service scripts.

### 7.4 Task execution rules

Task rules:

- every task has company ownership;
- every handler validates that the task company has `industry_type='real_estate'`;
- Real Estate handlers must not claim tasks from Trading queues, and Trading handlers must not claim Real Estate tasks;
- correlation ID remains `whatsapp-message:<message_id>` across the chain;
- each stage has a stable idempotency key;
- configured timeout, retry, and termination rules apply;
- one failure cannot leave a record indefinitely running;
- no historical backlog is processed when workers restart;
- enabling AI parsing establishes a new processing cutoff;
- duplicate message delivery cannot create duplicate opportunities;
- downstream stages cannot run until prerequisite records are complete.

## 8. Embeddings and Matching

### 8.1 Embedding task integration

Follow the current embedding implementation: register explicit versioned `@task_handler` functions on the existing `embeddings` queue and keep domain execution code in Real Estate services. Do not introduce a second embedding framework or require a generic registry refactor.

Add explicit task keys for:

- `embedding.real_estate_property`;
- `embedding.real_estate_listing`;
- `embedding.real_estate_requirement`;
- optionally `embedding.real_estate_location_alias`.

Each payload must use the existing versioned object identifier pattern, include `company_id`, and validate it against `BackgroundTask.company`. Existing Trading embedding task keys and service behavior remain unchanged.

### 8.2 Matching order

Matching must follow this order:

1. Apply hard deterministic exclusions.
2. Calculate structured compatibility.
3. Search embeddings among eligible candidates.
4. Optionally ask AI to rerank ambiguous candidates.
5. Persist all scores and reasons.

Activity compatibility must be expressed directly, without translating through alternate direction terminology:

| Source activity | Eligible opposite activity or record |
|---|---|
| Buying | Selling candidate or active sale listing |
| Selling | Buying requirement |
| Leasing Inquiry | Leasing Offer candidate or active lease listing |
| Leasing Offer | Leasing Inquiry requirement |

Hard exclusions include incompatible activity pairs, property type, mandatory location, availability, and clearly incompatible budget or bedroom constraints.

AI must never override a hard exclusion silently.

### 8.3 Matching observability

Track:

- deterministic candidates considered;
- candidates excluded and reasons;
- vector search duration;
- AI reranking duration;
- final score distribution;
- accepted and rejected suggestions;
- manual-match corrections;
- precision at configurable score thresholds.

## 9. Permissions

Add permission definitions:

```text
real_estate.dashboard.view
real_estate.properties.view
real_estate.properties.manage
real_estate.listings.view
real_estate.listings.manage
real_estate.opportunities.view
real_estate.opportunities.update
real_estate.matches.manage
real_estate.viewings.view
real_estate.viewings.manage
real_estate.offers.manage
real_estate.deals.manage
real_estate.automation.manage
real_estate.reports.view
real_estate.data.export
```

Owner and administrator roles receive all permissions. Manager, agent, viewer, and campaign roles receive explicit subsets. Record scopes should support company-wide and assigned-agent access where appropriate.

## 10. Frontend Information Architecture

For a company whose `industry_type` is `real_estate`, primary navigation should show:

- Real Estate Dashboard;
- Properties;
- Listings;
- Buying;
- Selling;
- Leasing Inquiries;
- Leasing Offers;
- Matches;
- Viewings;
- Deals;
- Real Estate Reports.

Shared modules remain visible according to permission:

- Inbox;
- ClientPulse;
- Campaigns;
- Automation;
- Reports;
- Directory;
- Settings;
- Operations and logs.

Trading navigation, product inventory, product matching, price updates, and trading-only settings must be hidden and blocked for Real Estate companies.

The Real Estate dashboard should use four operational lanes: Buying, Selling, Leasing Inquiries, and Leasing Offers. The UI must use those exact labels and must not collapse both leasing activities into one lane.

### 10.1 Prospect path interaction pattern

Do not introduce a separate step-by-step wizard. Follow the existing Trading interaction pattern:

- AI creates classified activity cards from incoming messages;
- users review and correct extracted values through the existing card, modal, and standard-form patterns;
- manual creation uses one structured form with conditional sections;
- the property-type selection controls which type-specific fields are shown;
- import review uses the same field components and validation rules;
- unknown or conflicting values remain reviewable instead of being guessed.

The shared fields and conditional sections must be reusable components, but their presentation must remain consistent with current Trading forms and review dialogs.

A physical `Property` is not itself Buying, Selling, Leasing Inquiry, or Leasing Offer. Activity belongs to a `RealEstateOpportunity`; sale or lease commercial terms belong to a `Listing`. This separation allows the same physical property to be offered for sale, offered for lease, or retained without an active listing at different times.

## 11. ClientPulse Integration

Real Estate opportunities should link to `CompanyContact` and ClientPulse profiles. ClientPulse should display:

- party roles;
- current Buying, Selling, Leasing Inquiry, or Leasing Offer activity;
- matched properties;
- viewings;
- offers and negotiations;
- last communication and last reply;
- next reminder/follow-up;
- won/lost deal history.

Real-estate roles must not overwrite the existing trading supplier/customer category. They should be stored as domain roles or ClientPulse tags with an explicit Real Estate namespace.

## 12. Campaign and Outbound Integration

Follow the existing direct/group Buying and Selling campaign page, model, API, attachment, audience, counter, and queue patterns. Create company-owned Real Estate campaign records inside the Real Estate domain where the content model differs. Reuse the existing industry-neutral outbound message service and `outbound` queue; do not move or rewrite working Trading campaign records as a prerequisite.

Real Estate campaigns should support:

- selected properties or listings;
- direct text;
- image and caption;
- contact and group audiences;
- company communication-account selection;
- exclusions;
- persisted attachments;
- per-destination counters and delivery status;
- existing/new-chat policy;
- group participation and announcement restrictions;
- per-contact and global account wait intervals;
- durable outbound queue delivery.

Domain-specific content formatters can render property and listing data while the existing outbound service continues to own preflight, throttling, attachments, queue delivery, and final status. Small neutral helpers may be extracted only when both domains need identical behavior and regression tests preserve current Trading behavior.

## 13. Settings

Add Real Estate settings for:

- GatePass disabled/observational/enforced mode;
- workflow agent or KiwiRouter selection;
- default currency;
- default area unit;
- default country and location hierarchy;
- match thresholds and structured-score weights;
- maximum location distance;
- candidate review requirements;
- stale-listing age;
- automatic listing expiry;
- allowed property types;
- deduplication window;
- campaign templates;
- notification and assignment defaults.

Queue concurrency, timeout, retries, backoff, pause, and enablement must remain in the existing `QueueDefinition` control plane and Task & Queues screen. Do not duplicate queue settings inside `RealEstateSettings`.

## 14. Reporting and Metrics

Operational reports should include:

- records by Buying, Selling, Leasing Inquiry, and Leasing Offer;
- opportunities by source account, contact, group, and assigned user;
- active inventory and listing age;
- requirements without matches;
- listings without interest;
- matching acceptance and rejection rates;
- viewings scheduled and completed;
- offer and deal conversion;
- response time and follow-up compliance;
- AI requests, input/output tokens, cost, latency, throughput, timeout, and failure rate;
- queue wait time, execution duration, throughput, timeout, retry, and failure rate for each Real Estate queue;
- GatePass precision, recall, and false-negative review results.

## 15. Implementation Phases

### Phase 1: Contract and platform preparation

- Finalize the four-value activity enum, classification statuses, status transitions, inventory provenance, ownership eligibility, tenure, property types, required fields, and AI schemas.
- Extend the existing classification dispatch boundary using `Company.industry_type` while preserving the current Trading branch.
- Register explicit Real Estate embedding task handlers through the existing task registry and a dedicated `real_estate_embeddings` queue.
- Add backend industry guards and frontend industry-aware navigation.
- Add permission definitions and role grants.
- Document non-regression requirements for trading.

### Phase 2: Real Estate application foundation

- Create the Django application and migrations.
- Use the Control Account as the owner of initial settings, instructions, and test records; set its existing `industry_type` to `real_estate` only when it is used for live Real Estate testing.
- Implement Property, Address, Media, Listing, Opportunity, Requirement, Candidate, Match, and Settings models.
- Add admin configuration, serializers, services, URLs, and company-scoped APIs.
- Add audit fields, indexes, uniqueness constraints, and archive behavior.

### Phase 3: Property inventory

- Implement property and listing CRUD.
- Add CSV import/export and validation preview.
- Add Own, Authorized, Floating, and Tracked inventory views while preserving source provenance and the existing candidate verification boundary.
- Map imported source labels to the owning company's canonical property types, for example `Flat` to `Apartment`, while retaining the original source value for audit and correction.
- Add system-seeded property-type field definitions and reusable conditional field rendering.
- Add image/document upload.
- Add duplicate detection and candidate merge workflows.
- Build reusable data-table views using the established component system.

### Phase 4: AI instruction and routing configuration

- Implement `RealEstatePromptConfig` by following the existing company-owned `trading.PromptConfig` pattern.
- Seed Real Estate defaults.
- Add direct-agent and KiwiRouter assignment.
- Add GatePass mode and matching settings.
- Add provider-call and parsing audit logs.

### Phase 5: Live classification

- Register `real_estate_gate`, `real_estate_extract`, `real_estate_match`, `real_estate_maintenance`, and `real_estate_embeddings` independently from Trading queues.
- Seed database-backed concurrency, timeout, retry, and backoff settings for each queue.
- Register Real Estate durable task handlers.
- Implement gate, extraction, validation, deduplication, and persistence.
- Add Task Operations queue visibility.
- Run GatePass observationally before enforcement.

### Phase 6: Matching

- Register property, listing, and requirement embeddings.
- Implement deterministic filtering and structured scoring.
- Add vector candidate search and optional AI reranking.
- Implement manual match, accept, reject, and correction workflows.

### Phase 7: Operational frontend

- Add dashboard and four activity lanes.
- Add opportunity detail and candidate verification dialogs.
- Extend the existing Trading-style cards, standard forms, and modals for prospect path review; do not add a separate wizard framework.
- Add listing and requirement matching views.
- Add agent assignment, statuses, filters, pagination, async loading, and saved view preferences.

### Phase 8: ClientPulse and workflow operations

- Project opportunities and status changes as ClientPulse activity.
- Implement viewings, reminders, linked reminder threads, offers, and deals.
- Add Inbox and ClientPulse navigation between contacts and opportunities.

### Phase 9: Campaigns and automation

- Implement Real Estate campaign models and pages using the established campaign patterns and existing outbound delivery core.
- Add listing and requirement campaigns.
- Add strict forwarding rules only after verified opportunity completion.
- Add stale-listing, expiry, reminder, and assignment automation.

### Phase 10: Reports and controlled rollout

- Build operational and AI performance reports.
- Run a labeled observational sample.
- Measure precision, recall, cost, latency, and queue throughput.
- Correct instructions and thresholds.
- Enable enforced GatePass only after meeting acceptance thresholds.

## 16. Testing Strategy

Required automated test categories:

- model constraints and lifecycle transitions;
- non-nullable direct company ownership on every Real Estate table from its initial migration;
- tenant and company isolation;
- non-Real-Estate industry API blocking;
- permissions and assigned-record scopes;
- industry dispatcher selection;
- task-to-queue routing and Trading/Real Estate queue isolation;
- company ownership enforcement inside every Real Estate handler;
- independent concurrency, timeout, retry, and backoff settings for each Real Estate queue;
- task idempotency, retry, timeout, and prerequisite handling;
- AI parsing schema validation;
- mutually exclusive activity classification;
- exact ownership eligibility and tenure contracts;
- Own, Authorized, and Floating provenance with independent tracking state;
- single Authorized inventory provenance without redundant action flags;
- property-type conditional field validation;
- ambiguous-activity review handling;
- no-backlog and AI-enable cutoff behavior;
- duplicate WhatsApp delivery;
- deterministic matching exclusions;
- embedding candidate selection;
- manual correction and audit history;
- property/listing duplicate detection;
- campaign sending restrictions;
- ClientPulse activity projection;
- frontend navigation and route guards;
- trading regression tests.

Production verification must include random manual accuracy sampling, not only aggregate success status.

## 17. Acceptance Criteria

The first production-capable release is complete when:

- a company sees only the navigation and routes appropriate to its `industry_type` and permissions;
- Real Estate live messages never enter the Trading classifier;
- Real Estate queue saturation or failure does not prevent Trading workers from claiming and completing Trading tasks;
- Buying, Selling, Leasing Inquiry, and Leasing Offer are mutually exclusive;
- ambiguous real-estate messages are held for review and never matched automatically;
- trusted properties and listings cannot be created silently from unverified AI output;
- Buying requirements are matched only to eligible sale listings, and Leasing Inquiry requirements only to eligible lease listings;
- all processing is durable, idempotent, company-owned, and observable;
- AI parsing starts at the enablement cutoff and does not process backlogs;
- users can manually verify, correct, accept, and reject parsed data and matches;
- ClientPulse shows linked communication and real-estate activity;
- outbound messaging respects every existing account and WhatsApp restriction;
- role permissions and assigned-agent scopes are enforced by the backend;
- AI accuracy, cost, tokens, latency, throughput, and queue performance are measurable;
- existing trading companies continue to operate without behavioral regression.

## 18. Principal Risks

- Collapsing Leasing Inquiry and Leasing Offer into one activity will create invalid matches.
- Conflating a physical property with its listing will make historical price and availability tracking unreliable.
- Automatically promoting AI-extracted offers into trusted inventory will pollute property data.
- Copying trading classifiers or campaign models will create two tightly coupled systems that are difficult to maintain.
- Frontend-only industry gating can expose or modify the wrong domain data.
- Free-form JSON for all property attributes will make filtering, matching, and reporting unreliable.
- Missing task idempotency can generate duplicate opportunities from WhatsApp retries.
- Geocoding and location aliases can create false matches unless normalized and reviewed.
- Stale listings will damage matching quality unless expiry and availability confirmation are built into operations.

## 19. Recommended Starting Scope

The first implementation should focus on:

1. industry-neutral dispatch and permissions;
2. property and listing inventory;
3. Buying, Selling, Leasing Inquiry, Leasing Offer, and not-real-estate classification;
4. structured requirements and verified property candidates;
5. deterministic plus embedding matching;
6. the operational dashboard and review UI;
7. ClientPulse linkage and reminders;
8. observable, durable task execution.

Viewings, offers, deals, campaign automation, and advanced analytics should follow after the classification and inventory contracts have been validated with production-like data.

## 20. Implementation Status

### Foundation completed on 10 October 2026

- Registered `apps.real_estate` without changing the Trading application.
- Added the canonical four-value `ActivityType` contract and six-value AI decision contract.
- Added a tested decision mapper that produces exactly one classification status and optional activity.
- Added company-owned `RealEstateOpportunity`, `RealEstateSettings`, and `RealEstatePromptConfig` models.
- Added database constraints for classification/activity consistency and company-level deduplication.
- Added cross-company validation for WhatsApp sources, contacts, assigned users, direct AI agents, and KiwiRouter targets.
- Added enrollment seeding and a data migration for Real Estate settings.
- Added Real Estate permission definitions and default role grants through the existing RBAC system.
- Added `real_estate_gate`, `real_estate_extract`, `real_estate_match`, and `real_estate_maintenance` through the existing `QueueDefinition` migration pattern. Their default timeout is 300 seconds and their concurrency remains database-configurable.
- Added Django admin visibility and focused model, contract, queue, and enrollment tests.

### Live classification completed on 10 October 2026

- Live ingestion now resolves the message-owning company's `industry_type` before domain classification.
- Trading companies retain the existing Trading log, version selection, task keys, and classifier behavior.
- Real Estate companies enqueue `real_estate.gate_message`; they never create Trading parsing records or enter a Trading classifier.
- General companies do not fall through to either domain classifier.
- GatePass supports disabled, observational, and enforced modes from `RealEstateSettings`.
- Disabled mode bypasses the gate and enqueues extraction. Observational mode records the gate decision and always continues. Enforced mode stops only a valid `not_real_estate` decision.
- Gate failures fail open to extraction and are retained in the Real Estate parse audit record, preventing a provider or response-format error from silently dropping a possible opportunity.
- Extraction accepts exactly the documented six decisions and persists one canonical `activity_type` or a review/non-real-estate outcome.
- AI-produced supply messages create opportunities only. They do not create trusted property or listing inventory.
- Real Estate provider calls reuse company-owned direct agents or KiwiRouter, durable-task deadlines, and the existing AI manager while writing a separate company-owned token, latency, provider, model, response, and error ledger.
- Both task handlers validate `BackgroundTask.company_id`, payload company, message ownership, active company industry, and current AI parsing controls before doing work.
- Both task keys participate in the existing worker-startup live-backlog discard policy and use message-based correlation and idempotency keys.
- Focused tests cover industry isolation, queue routing, disabled GatePass, enforced rejection, canonical extraction, and General-company non-fallthrough.

### Property and listing foundation completed on 11 October 2026

- Added directly company-owned `Property`, `PropertyAddress`, `PropertyMedia`, `Listing`, `PropertyRequirement`, and `PropertyCandidate` tables. None permits an unowned row.
- Kept physical properties separate from sale and lease listings so availability, pricing, and listing history remain reliable.
- Added database uniqueness for company reference codes, external source identities, one primary media item, and one active listing per property and transaction type.
- Added validation for cross-company relations, assigned company members, sale/lease payment frequency, verified active listings, numeric ranges, media size/type, and requirement ranges.
- Added company-scoped, paginated REST endpoints with existing RBAC permission codes and assigned-agent scope enforcement for opportunities, requirements, and candidates.
- Property and listing deletion uses archive/close behavior rather than destructive deletion.
- Extraction now deterministically projects Buying and Leasing Inquiry results into requirements and Selling and Leasing Offer results into unverified candidates.
- AI extraction never creates a trusted property or listing. Candidate promotion, merge, and rejection require explicit authorized actions and retain the reviewed source link.
- Promotion creates a verified draft listing by default, allowing an operator to validate it before activation.
- Added Django admin coverage and focused tests for ownership isolation, active-listing conflicts, projection behavior, explicit promotion, API scoping, archive behavior, and industry enforcement.

### Operational inventory UI completed on 11 October 2026

- Added industry-aware navigation and route guards. Real Estate companies see Real Estate inventory instead of Trading products, automation, campaigns, reports, instructions, and parsing logs.
- Added reusable, paginated Property, Listing, and Candidate Review screens using the existing shared UI controls and data table.
- Added property and address creation/editing, media upload/removal, listing creation/editing, archive actions, filters, ordering, and CSV export.
- Added a two-step CSV workflow: file validation and duplicate preview occur before an explicit import action.
- Duplicate detection covers existing company inventory and repeated rows within the same upload. Imports skip exact existing records and reject ambiguous in-file duplicates.
- Added explicit candidate promotion, merge, and rejection UI. Extracted candidates still cannot enter trusted inventory silently.
- Added focused API and navigation tests while preserving the existing Trading routes for Trading companies.

### Real Estate embedding foundation completed on 12 October 2026

- Added four separate, directly company-owned vector tables: `real_estate_property_embedding`, `real_estate_listing_embedding`, `real_estate_requirement_embedding`, and `real_estate_candidate_embedding`.
- Source values remain authoritative and unchanged. No property, listing, requirement, or candidate field is replaced by an embedding.
- Each vector row stores a 512-dimension vector, model, provider metadata, canonical-document version and SHA-256 hash, status, error, and timestamps.
- Property vectors contain searchable physical-property context and one canonical location phrase. Unit numbers, reference codes, coordinates, and other operational identifiers remain structured data and are not embedded.
- Listing vectors combine the physical property document with transaction, asking-price, payment, and availability context.
- Requirement vectors contain the inquiry activity, source wording, structured ranges, acceptable locations/types, amenities, timeframe, and constraints.
- Candidate vectors contain the offered-property wording, location, property attributes, price, furnishing, availability, and description.
- Added the dedicated `real_estate_embeddings` durable queue and four retry-safe task keys. Every handler validates task company, payload company, and target company before provider work.
- Property, address, media, listing, requirement, candidate, and relevant opportunity changes automatically enqueue only the affected vectors. Property context changes also refresh its listing vectors.
- Added company-scoped status and repair/backfill endpoints plus Properties-page feedback. Repair is blocked until that company has an active company-owned embedding provider.
- Added cosine IVFFlat indexes for later candidate retrieval. Matching still must apply authoritative structured eligibility filters before vector ranking.

### Property type master and expanded units completed on 12 October 2026

- Replaced fixed property-type choices with a directly company-owned `PropertyType` master referenced by verified properties and extracted candidates.
- Migrated every existing property and candidate type into the owning company's master before removing the legacy text fields.
- Preserved readable API and CSV contracts by continuing to accept and return stable type codes instead of exposing database IDs.
- Added company-scoped CRUD, safe deactivation/reactivation, enrollment defaults, dynamic inventory filters, and dynamic property/candidate selectors.
- Expanded area measurements from square feet and square metres to include square yards, acres, and hectares without modifying existing values.

### Prospect-path and inventory alignment completed on 13 October 2026

- Added the approved ownership eligibility values: `locals_only`, `gcc_only`, and `all`.
- Added only the approved tenure values: `freehold`, `long_lease`, and `lease_99_year`.
- Added Own, Authorized, and Floating as inventory source provenance, with Tracked implemented independently so tracking never destroys the original source.
- Kept Authorized as one loose inventory classification. No purchase, sale, or lease permission flags were introduced.
- Expanded the company-owned property taxonomy and retained imported or AI source labels separately from the canonical property type.
- Added company-owned, schema-driven type-field definitions and a reusable UI component shared by manual property editing, candidate review, and imported-row correction.
- Added market scope, ownership, tenure, inventory, tracking, and type-specific attributes to extraction and candidate promotion without allowing AI candidates to bypass review.
- Added grid filters and actions for inventory source and tracking, plus server-side validation after imported rows are corrected.
- Extended Real Estate embedding documents with the new readable context while keeping all original structured values authoritative.
- Added regression coverage for taxonomy aliases, type schemas, inventory provenance, independent tracking, filtered APIs, import audit retention, extraction, and promotion.

### Deployment and worker operation

Apply the database migrations before opening the Real Estate UI:

```powershell
python manage.py migrate
```

The normal `ChatLensTaskWorker` serves enabled queues except the Real Estate queues reserved for the dedicated worker. This keeps worker ownership disjoint and prevents one service from superseding the other:

```text
scripts\Start-RealEstateTaskWorkerService.bat
scripts\Stop-RealEstateTaskWorkerService.bat
```

The scripts install or reconfigure the NSSM service `ChatLensRealEstateTaskWorker` and serve only:

```text
real_estate_gate
real_estate_extract
real_estate_match
real_estate_maintenance
real_estate_embeddings
```

PowerShell variants accept `-ServiceName`, `-NssmPath`, and `-PythonPath` overrides. The stop script requests a graceful stop and waits for active work rather than force-killing it. Service output is written to:

```text
logs\services\real-estate-task-worker.out.log
logs\services\real-estate-task-worker.err.log
```

Queue concurrency, timeout, retry, and enablement remain database-owned and are managed through the existing Task & Queues settings. The generic worker is started with one `--exclude-queue` argument for each dedicated Real Estate queue. Worker queue sets must not overlap because startup supersession intentionally retires an older worker that owns any of the same queues.

### Current operator verification

For a company with `industry_type = real_estate`:

1. Switching to the company opens `/real-estate/properties`.
2. The sidebar shows Real Estate and hides Trading, Automation, Campaigns, Trading Reports, V2 settings, and Trading parsing logs.
3. Properties can be created, edited, archived, filtered, exported, and assigned address/media records.
4. Listings remain separate from physical properties and can be created, edited, verified, filtered, or closed.
5. CSV import requires preview before import, supports correction through the shared property editor, revalidates corrections server-side, and reports validation and duplicate problems.
6. Candidate Review shows AI-extracted supply candidates without treating them as trusted inventory.
7. Promotion creates a draft property/listing record; merge links to an existing listing; rejection preserves the audit trail.
8. Task Operations shows the five Real Estate queues and their task lifecycle events.
9. Properties shows the combined Real Estate embedding count. Repair queues missing, skipped, or failed property, listing, requirement, and candidate vectors.
10. Properties can be filtered as Own, Authorized, Floating, or Tracked; tracking does not change source provenance.
11. Property and candidate forms show only the system-defined fields configured for the selected company property type.

### Remaining phases

- Explainable property matching and operator match review.
- Real Estate workflow/settings UI for GatePass, prompts, direct agents, and KiwiRouter assignment.
- Real Estate operational dashboard for the four activity lanes.
- ClientPulse Real Estate activity projection and reminders.
- Real Estate outbound workflows and campaign controls.
- Accuracy, token, cost, latency, throughput, and queue performance reporting.

### Next implementation phase

Implement the matching foundation and review UI: deterministic eligibility filters, company-scoped embedding candidates, explainable scoring, explicit operator decisions, and separate Buying-to-Sale and Leasing-Inquiry-to-Lease matching. Automatic matching remains disabled until these contracts and operator feedback are verified.
