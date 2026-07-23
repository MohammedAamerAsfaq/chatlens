# Company Enrollment and Multi-Industry Strategy

> **Status:** Proposed architecture and onboarding document only — no code changes implemented yet.
> **Prepared:** 2026-07-22
> **Purpose:** Define the initial company-enrollment process and the strategy for supporting multiple industries without breaking the current trading implementation.
> **Related docs:** `Tenant Account Model Plan.md`, `Code Review Remediation Plan.md`, `Exception Handling and Failure Visibility Principle.md`

---

## 1. Goal

This document defines two things:

1. the **initial new-company enrollment process** for the tenant-based version of ChatLens, and
2. the **multi-industry strategy** for growing beyond the current trading-focused domain into industries such as real estate.

Both are designed with one non-negotiable constraint:

**None of these changes should break current ChatLens functionality.**

That means:

- current trading behavior remains valid,
- current WhatsApp ingestion and business flows remain intact,
- the new tenant and industry structures must wrap and extend the system rather than force a disruptive rewrite.

---

## 2. Initial Company Enrollment

## 2.1 First-version principle

The first enrollment flow should be deliberately minimal.

For the start, ChatLens only needs:

- company name
- first user email
- first user username
- first user password

That is enough to bootstrap a tenant cleanly without prematurely designing a large onboarding UI or a complex approval workflow.

## 2.2 Required enrollment inputs

### Company fields

- `company_name`

### First company super user fields

- `email`
- `username`
- `password`

That first user becomes the company’s initial **company-level super user**.

---

## 2.3 Enrollment result

When a new company is enrolled, the system should create:

1. a new `Company`
2. a new Django `User` if one does not already exist for the intended flow
3. a `CompanyMembership` linking that user to the company
4. default tenant/provider settings for supported channels
5. optional management linkage to the control company

Minimum expected result:

```text
Company
  └─ CompanyMembership(role='super_user')
       └─ User(email, username, password)
```

---

## 2.4 Enrollment should be a service, not scattered logic

This must not be implemented as ad hoc logic spread across views, serializers, and forms.

The correct shape is a dedicated service, for example:

```python
class CompanyEnrollmentService:
    def enroll_company(*, company_name, email, username, password, enrolled_by=None):
        ...
```

### Why

Because enrollment is a multi-object bootstrap operation:

- company creation
- user creation
- membership creation
- default provider assignment
- optional control-company management linkage

That should happen in one clear workflow with one source of truth.

## 2.5 Transaction rule

Enrollment should run inside a database transaction.

Reason:

- avoid half-created tenants
- avoid a company without a super user
- avoid a user without a membership
- avoid a tenant existing without the required default configuration

If any required part fails:

- the transaction rolls back,
- the enrollment fails explicitly,
- the exception is logged and reported per the project’s failure-visibility principle.

---

## 2.6 Default bootstrap behavior

When a company is created, the system should also apply sensible defaults automatically.

### Initial defaults

- company is active by default unless management policy says otherwise
- the enrolling user gets `role='super_user'`
- the default provider for each supported channel remains the system default
- no non-default provider override is assigned unless a control-company super user explicitly does so

### Control-company relationship

The new company may optionally be linked to the control company for:

- enrollment tracking
- validity management
- lifecycle supervision

This should be a business-level relationship, not a hack in permissions.

---

## 2.7 First-version flow

Recommended first implementation flow:

1. operator submits:
   - company name
   - email
   - username
   - password
2. system validates uniqueness and basic format
3. system creates the company
4. system creates the user
5. system creates the company membership with `role='super_user'`
6. system applies default provider/channel policy
7. system records the company as managed/enrolled under the control company if that policy is enabled
8. system returns a clear success result

### Failure rule

If any step fails:

- the enrollment is not partially accepted,
- the failure is logged with full context,
- the API/UI must not claim success.

---

## 2.8 Future expansion path

The enrollment flow can stay minimal now and grow later without redesign.

Future optional fields may include:

- company status
- validity start / end dates
- industry type
- approved channels
- approved provider overrides
- billing or subscription plan
- onboarding checklist state

These should be additive, not required for the first version.

---

## 3. Multi-Industry Strategy

## 3.1 Problem statement

The current business-domain implementation is centered on trading:

- products
- price lists
- inquiries
- supplier/customer categorization
- trading analytics

But ChatLens is intended to support different industries, including:

- trading
- real estate
- potentially others later

The key design question is:

**How do we support new industries without breaking or distorting the current trading system?**

---

## 3.2 Recommended strategy

The correct approach is:

### Keep the platform core industry-neutral

The following should remain shared and industry-agnostic:

- companies
- memberships
- providers
- communication accounts
- endpoints
- channel-local contacts
- company main contacts
- messages
- chats
- sync logs
- alerts
- unresolved/dropped records
- tenant permissions

### Keep business domains industry-specific

The following should remain in domain apps:

- trading-specific models stay in `apps/trading`
- future real-estate-specific models should live in a separate app, for example `apps/real_estate`

This means:

- the tenant/core layer is generic,
- the business layer is modular by industry.

---

## 3.3 Do not over-generalize `Product` right now

The current `Product` model is trading-specific. That is acceptable.

It should **not** be forcibly turned into a universal object for every industry in the first redesign phase.

### Why not

Because that creates a weak, confusing abstraction:

- a phone trading product is not the same business object as a real-estate property or listing
- forcing both into one generic table too early usually produces a bloated schema and confusing logic
- it increases migration complexity and breakage risk for the current trading system

### Better approach

Keep:

- `Product` as a trading-domain model

Add later:

- real-estate-domain models such as `Property`, `Listing`, `Lead`, `ViewingRequest`, etc.

This keeps the current design stable while allowing future specialization.

---

## 3.4 Add industry type at the company level

The tenant should declare its industry orientation.

### Proposed field

```python
class Company(models.Model):
    industry_type = models.CharField(
        max_length=30,
        choices=[
            ('general', 'General'),
            ('trading', 'Trading'),
            ('real_estate', 'Real Estate'),
        ],
        default='general',
    )
```

### Meaning

- `general`
  no specialized business module assumed yet
- `trading`
  current trading module is the primary business domain
- `real_estate`
  future real-estate module is the primary business domain

This field is useful for:

- UI enablement
- navigation
- module activation rules
- reporting scope
- future onboarding defaults

---

## 3.5 Business-module architecture

Recommended app structure:

```text
apps/
  tenancy/          tenant/company/core ownership
  whatsapp_bridge/  WhatsApp operational integration
  trading/          trading-specific business logic
  real_estate/      future real-estate-specific business logic
```

### Responsibilities

#### `tenancy`

- companies
- memberships
- provider selection
- communication accounts
- endpoints
- company contact list

#### `whatsapp_bridge`

- WhatsApp-specific operational models and ingestion
- local contacts, chats, messages, alerts, worker sync

#### `trading`

- products
- aliases
- inquiries
- price workflows
- trading analytics

#### `real_estate` later

- properties
- listings
- leads
- inquiries
- scheduling/engagement workflows

This keeps future growth clean and minimizes risk to current code.

---

## 3.6 Shared communication layer, separate business meaning

The same underlying message stream can power different industries.

Example:

- all industries use messages and contacts
- only trading uses products and price updates
- real estate may use property listings and lead qualification instead

That means:

- communication ingestion is shared,
- business interpretation is industry-specific.

This is the correct separation point.

---

## 3.7 Company-level product/contact ownership still works

Even in a multi-industry future, the current rule remains valid:

- a company can have one main contact list
- a trading company can have one product catalog shared across its communication accounts

For non-trading industries:

- the company still has the main contact list
- but it may use a different business catalog or domain model instead of `Product`

So the generalized principle is:

- **shared company contact list across channels**
- **industry-specific business data model above that**

---

## 3.8 Recommended rollout path

### Phase 1

Implement tenancy and company enrollment.

### Phase 2

Keep the existing trading module intact, but make it company-owned.

### Phase 3

Add `company.industry_type`.

### Phase 4

Introduce module gating in the UI/API:

- trading companies see trading features
- real-estate companies later see real-estate features

### Phase 5

Add new industry apps without forcing schema distortion into trading models.

---

## 4. Proposed First-Version Implementation Rules

## 4.1 Enrollment rules

For the first version:

- only collect company name, email, username, password
- create the company and first company super user
- assign default provider rules automatically
- do not build complex billing or approval logic yet

## 4.2 Industry rules

For the first version:

- treat trading as the existing active business domain
- do not redesign `Product` into a generic cross-industry table
- add company-level `industry_type`
- keep future industries in separate business apps

## 4.3 Non-regression rule

The tenant and industry changes must not alter current trading behavior unexpectedly.

That means:

- current trading products keep working
- current inquiry flow keeps working
- current WhatsApp ingestion keeps working
- current AI classification paths keep working
- no forced real-estate abstraction is pushed into trading models yet

---

## 5. Recommended New Document After This

After this document, the next useful spec should be:

**Tenant Enrollment and Industry Migration Spec**

It should define:

- exact model additions
- exact changes to `Company`
- enrollment service contract
- transaction boundaries
- default provider bootstrap
- migration of existing trading data to company ownership
- how `industry_type` will gate future modules

---

## 6. Summary

The agreed direction is:

- company enrollment starts minimal:
  - company name
  - email
  - username
  - password
- the first user becomes the company super user
- enrollment should be implemented as one transactional bootstrap service
- the platform core remains industry-neutral
- `trading` remains a domain-specific module
- future industries such as real estate should be added as separate domain apps
- `Product` should remain trading-specific for now
- add `Company.industry_type` rather than forcing a universal business-object abstraction too early

This gives ChatLens a safe path to multi-tenant and multi-industry growth without breaking the current trading implementation.

---

*Prepared for ChatLens on 2026-07-22 as the initial design for company enrollment and multi-industry support.*
