# Tenant Enrollment and Industry Migration Spec

> **Status:** Proposed implementation spec — no code changes applied from this document yet.
> **Prepared:** 2026-07-22
> **Purpose:** Define the concrete migration path from the current ChatLens model to the tenant-based, company-owned, provider-aware architecture already agreed in the design documents.
> **Primary constraint:** No existing ChatLens functionality may be broken during or after the migration.
> **Related docs:** `Tenant Account Model Plan.md`, `Company Enrollment and Multi-Industry Strategy.md`, `Code Review Remediation Plan.md`, `Exception Handling and Failure Visibility Principle.md`

---

## 1. Scope

This document turns the agreed architecture into an implementation sequence.

It covers:

- exact new tenancy models
- exact changes to current models
- company enrollment service contract
- control-company bootstrap
- Baileys provider seed/bootstrap
- company ownership backfill for current trading/WhatsApp data
- `industry_type` introduction
- compatibility strategy to avoid regressions
- migration order
- test requirements

It does **not** implement:

- full real-estate business models
- frontend redesign
- provider override UI
- a broad permission rewrite beyond what is required for compatibility and safe rollout

---

## 2. Non-Regression Rule

This migration must preserve all existing working behavior while introducing the new ownership model.

That means the following must continue to work throughout the rollout:

- WhatsApp session creation/reconnect
- message ingest
- contact sync
- group sync
- message logs / worker alerts / unresolved messages
- products and aliases
- inquiry flow
- AI parsing / embeddings / automation
- existing admin/operator UI behavior unless explicitly changed later

### Implementation consequence

The migration must be done in **compatibility phases**, not in a single destructive rewrite.

Specifically:

- add new ownership fields first
- backfill them
- switch code paths to read them
- only remove old fields after all dependent code is migrated and tested

---

## 3. New Models

All new platform-ownership models should live in a new Django app:

```text
apps/tenancy/
```

Recommended initial file structure:

```text
apps/tenancy/
  __init__.py
  apps.py
  admin.py
  models/
    __init__.py
    company.py
    membership.py
    connection_provider.py
    communication_account.py
    account_endpoint.py
    company_contact.py
    company_contact_identity.py
  services/
    __init__.py
    enrollment_service.py
    provider_service.py
```

## 3.1 Company

```python
class Company(models.Model):
    TYPE_CONTROL = 'control'
    TYPE_CUSTOMER = 'customer'
    TYPE_INTERNAL = 'internal'

    INDUSTRY_GENERAL = 'general'
    INDUSTRY_TRADING = 'trading'
    INDUSTRY_REAL_ESTATE = 'real_estate'

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    company_type = models.CharField(
        max_length=20,
        choices=[
            (TYPE_CONTROL, 'Control'),
            (TYPE_CUSTOMER, 'Customer Company'),
            (TYPE_INTERNAL, 'Internal'),
        ],
        default=TYPE_CUSTOMER,
    )

    industry_type = models.CharField(
        max_length=30,
        choices=[
            (INDUSTRY_GENERAL, 'General'),
            (INDUSTRY_TRADING, 'Trading'),
            (INDUSTRY_REAL_ESTATE, 'Real Estate'),
        ],
        default=INDUSTRY_GENERAL,
    )

    is_active = models.BooleanField(default=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)

    parent_company = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_companies',
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

## 3.2 CompanyMembership

```python
class CompanyMembership(models.Model):
    ROLE_SUPER_USER = 'super_user'
    ROLE_ADMIN = 'admin'
    ROLE_MANAGER = 'manager'
    ROLE_USER = 'user'
    ROLE_VIEWER = 'viewer'

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='company_memberships')
    role = models.CharField(max_length=20, choices=[...])
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'user'], name='unique_company_membership')
        ]
```

## 3.3 ConnectionProvider

```python
class ConnectionProvider(models.Model):
    key = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    channel = models.CharField(max_length=20, choices=[...])
    provider_type = models.CharField(max_length=50, blank=True)

    is_active = models.BooleanField(default=True)
    is_default_for_channel = models.BooleanField(default=False)

    capabilities = models.JSONField(default=list, blank=True)
    config_schema = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

## 3.4 CommunicationAccount

```python
class CommunicationAccount(models.Model):
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='communication_accounts')
    provider = models.ForeignKey('tenancy.ConnectionProvider', on_delete=models.PROTECT, related_name='communication_accounts')

    channel = models.CharField(max_length=20, choices=[...])
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    external_account_id = models.CharField(max_length=255, blank=True)
    config = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Validation rule

`communication_account.channel` must equal `communication_account.provider.channel`.

## 3.5 AccountEndpoint

```python
class AccountEndpoint(models.Model):
    communication_account = models.ForeignKey(
        'tenancy.CommunicationAccount',
        on_delete=models.CASCADE,
        related_name='endpoints',
    )

    endpoint_type = models.CharField(max_length=20, choices=[...])
    value = models.CharField(max_length=255)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

## 3.6 CompanyContact

```python
class CompanyContact(models.Model):
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='contacts')

    display_name = models.CharField(max_length=255, blank=True)
    legal_name = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=20, choices=[...], blank=True)

    is_company = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

## 3.7 CompanyContactIdentity

```python
class CompanyContactIdentity(models.Model):
    contact = models.ForeignKey('tenancy.CompanyContact', on_delete=models.CASCADE, related_name='identities')
    identity_type = models.CharField(max_length=30, choices=[...])
    value = models.CharField(max_length=255)
    is_primary = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['contact', 'identity_type', 'value'],
                name='unique_company_contact_identity',
            )
        ]
```

## 3.8 Optional Phase-1 Deferral

`CompanyChannelProviderPolicy` is optional and should be deferred unless explicit override auditability is needed immediately.

For the first implementation:

- store effective provider directly on `CommunicationAccount`
- enforce override policy in service/admin logic

---

## 4. Changes to Existing Models

These changes must be additive first.

## 4.1 `apps/whatsapp_bridge/models/whatsapp_account.py`

### Add first

```python
communication_account = models.OneToOneField(
    'tenancy.CommunicationAccount',
    null=True, blank=True,
    on_delete=models.CASCADE,
    related_name='whatsapp_account',
)

primary_endpoint = models.ForeignKey(
    'tenancy.AccountEndpoint',
    null=True, blank=True,
    on_delete=models.SET_NULL,
    related_name='+',
)
```

### Keep temporarily

- existing `owner` field

### Final state later

- `owner` removed after compatibility migration is complete

## 4.2 `apps/whatsapp_bridge/models/whatsapp_contact.py`

### Add first

```python
company_contact = models.ForeignKey(
    'tenancy.CompanyContact',
    null=True, blank=True,
    on_delete=models.SET_NULL,
    related_name='whatsapp_contacts',
)
```

### Ownership

Keep `account` as the operational/raw ownership path.

## 4.3 `apps/trading/models/product.py`

### Add

```python
company = models.ForeignKey(
    'tenancy.Company',
    null=True, blank=True,
    on_delete=models.CASCADE,
    related_name='products',
)
```

### Migration shape

- nullable first
- backfill to control company
- then make non-null

## 4.4 `apps/trading/models/inquiry.py`

### Add

```python
company = models.ForeignKey(
    'tenancy.Company',
    null=True, blank=True,
    on_delete=models.CASCADE,
    related_name='inquiries',
)
```

### Backfill rule

- derive from `account -> communication_account -> company` after those relations exist
- initially all current rows backfill to control company

## 4.5 Recommended direct tenant FK additions later

For performance and authorization clarity, later add `company` to other major operational/business tables where useful:

- `WhatsAppMessage`
- `WhatsAppChat`
- `SyncLog`
- `DroppedMessage`
- `WorkerAlert`
- `StuckReceipt`
- `WhatsAppUnresolvedMessage`

These should be a **later phase**, not required for the first ownership bootstrap.

---

## 5. Control Company Bootstrap

## 5.1 Data migration seed

Create one control-company row:

```text
name: "Control Account"
slug: "control-account"
company_type: "control"
industry_type: "trading"
is_active: true
```

`industry_type='trading'` is the correct initial value because the current business domain is the trading module.

## 5.2 Membership seed

Find the current primary superuser and create:

```text
CompanyMembership:
  company = control_company
  user = superuser
  role = super_user
  is_active = true
```

If more than one global Django superuser exists, either:

- add all of them to the control company as `super_user`, or
- explicitly pick one primary and document the policy

Recommended initial behavior:

- add all current global superusers

---

## 6. Connection Provider Seed

## 6.1 Initial provider record

Create one provider row:

```text
key: "baileys"
name: "Baileys WhatsApp Worker"
channel: "whatsapp"
provider_type: "node_worker"
is_active: true
is_default_for_channel: true
capabilities:
  - receive_messages
  - history_sync
  - contacts_sync
  - group_sync
  - session_qr_link
```

## 6.2 Provider policy

For the first implementation:

- every new WhatsApp communication account gets `provider=baileys` by default
- non-default provider assignment is allowed only via control-company super-user controlled logic

That policy should live in service/admin logic initially, not in an elaborate schema.

---

## 7. Bridging Existing WhatsApp Accounts

For every existing `WhatsAppAccount` row:

1. create a `CommunicationAccount`
2. assign:
   - `company = control_company`
   - `channel = 'whatsapp'`
   - `provider = baileys`
   - `name = display_name or phone_number or f'WhatsApp Account #{pk}'`
3. link the existing `WhatsAppAccount.communication_account`
4. create `AccountEndpoint` rows where possible
5. set `primary_endpoint` when the primary phone/session identity is known

### Endpoint seed examples

If `phone_number` exists:

```text
AccountEndpoint:
  endpoint_type = "phone"
  value = phone_number
  is_primary = true
```

If a worker session identity needs explicit tracking later, add a second endpoint or store it in metadata.

---

## 8. Product Ownership Backfill

All existing `Product` rows should be backfilled to the control company.

Migration sequence:

1. add nullable `company`
2. populate all current rows with `control_company`
3. validate no nulls remain
4. make `company` non-null in a later migration

### Alias ownership

`ProductAlias` does not need its own `company` field if ownership remains through `product`.

That is sufficient for the first phase.

---

## 9. Inquiry Ownership Backfill

All existing `Inquiry` rows should be backfilled to the control company.

Migration sequence:

1. add nullable `company`
2. backfill all current rows with `control_company`
3. later switch application code to derive company from `account.communication_account.company`
4. make `company` non-null after validation

### Why direct company field stays

- simpler tenant filtering
- easier authorization
- future cross-channel reporting support

---

## 10. Company Enrollment Service Contract

The initial enrollment flow must be implemented as one service.

## 10.1 Proposed interface

```python
class CompanyEnrollmentService:
    @transaction.atomic
    def enroll_company(
        self,
        *,
        company_name: str,
        email: str,
        username: str,
        password: str,
        enrolled_by_user_id: int | None = None,
        industry_type: str = Company.INDUSTRY_GENERAL,
    ) -> EnrollmentResult:
        ...
```

## 10.2 First-version behavior

The service should:

1. validate company name
2. validate username/email uniqueness per policy
3. create company
4. create user
5. set password securely
6. create membership with `role='super_user'`
7. attach optional management relationship to control company if required
8. return a structured result

## 10.3 Suggested result object

```python
@dataclass
class EnrollmentResult:
    company_id: int
    user_id: int
    membership_id: int
```

## 10.4 Failure rule

If enrollment fails at any point:

- transaction rolls back
- error is logged with company/user context
- caller receives failure, not partial success

This must follow the project’s failure-visibility principle exactly.

---

## 11. Industry Strategy Implementation

## 11.1 Add `industry_type` to `Company`

This is part of the first tenancy-model rollout.

Allowed initial values:

- `general`
- `trading`
- `real_estate`

## 11.2 Initial assignment rules

- control company: `trading`
- newly enrolled companies: default `general` unless explicitly set

If the first enrollment UI is intentionally minimal, industry selection can be deferred from the public form and set internally/admin-side at first.

## 11.3 Preserve trading domain

Do **not** generalize `Product` into a universal cross-industry table now.

Instead:

- keep `apps/trading` intact
- make it company-owned
- add future industry modules separately

## 11.4 Future real-estate path

When real-estate support begins, create a separate business app, for example:

```text
apps/real_estate/
```

Potential later models:

- `Property`
- `Listing`
- `Lead`
- `ViewingRequest`
- `DealPipeline`

These should reuse:

- company
- communication accounts
- company contacts
- messages

without forcing real-estate concepts into `Product`.

---

## 12. Compatibility Rollout Phases

## Phase 1 — Add tenancy app and seed data

Implement:

- `tenancy` app
- models
- migrations
- control company seed
- superuser memberships
- Baileys provider seed

No existing behavior changed yet.

## Phase 2 — Add bridging fields to current models

Implement:

- `WhatsAppAccount.communication_account`
- `WhatsAppAccount.primary_endpoint`
- `WhatsAppContact.company_contact`
- `Product.company`
- `Inquiry.company`

Fields nullable first.

## Phase 3 — Backfill current data

Implement data migrations to:

- create `CommunicationAccount` rows for all existing WhatsApp accounts
- create `AccountEndpoint` rows where possible
- backfill `Product.company = control_company`
- backfill `Inquiry.company = control_company`

## Phase 4 — Switch code paths to new ownership model

Update services/views/query helpers to prefer:

- `account.communication_account.company`
- `product.company`
- `inquiry.company`

But keep compatibility with old fields during the transition.

## Phase 5 — Add enrollment service

Implement:

- `CompanyEnrollmentService`
- first internal/admin enrollment entry point

No public self-service onboarding required yet.

## Phase 6 — Company-scoped permissions

Update access logic to use:

- company memberships
- company ownership
- control-company super-user override policy where applicable

This phase should be coordinated with the access-control remediation plan.

## Phase 7 — Remove obsolete ownership fields

Only after code/test verification:

- remove `WhatsAppAccount.owner`
- remove compatibility reads that depend on it

This must be the last cleanup step, not an early migration.

---

## 13. Test Requirements

## 13.1 Migration tests

Verify:

- control company is created
- Baileys provider is created
- existing WhatsApp accounts get bridged correctly
- products and inquiries backfill to control company

## 13.2 Enrollment tests

Verify:

- company + user + membership are created atomically
- duplicate username/email/company validations behave correctly
- failures roll back fully

## 13.3 Non-regression tests

Verify existing behavior still works after tenancy fields are added:

- WhatsApp account start session
- contact sync
- message ingest
- inquiry creation
- product CRUD
- unresolved message preserve/recover paths

## 13.4 Authorization tests

After membership-based scoping is introduced, verify:

- only visible company data is returned
- control-company super-user override policy behaves as designed

---

## 14. Logging and Failure Handling Requirements

Implementation of these migrations must follow the exception-handling principle already documented:

- no silent bootstrap failure
- no hidden fallback that masks company/provider migration failure
- no partial enrollment success
- all important migration/enrollment failures logged with structured context

Minimum identifiers in logs where relevant:

- company id/name
- user id/username
- communication account id
- provider key
- WhatsApp account id
- migration step name

---

## 15. Recommended Immediate Implementation Order

The next coding pass should proceed in this order:

1. scaffold `apps/tenancy`
2. add `Company`, `CompanyMembership`, `ConnectionProvider`, `CommunicationAccount`, `AccountEndpoint`, `CompanyContact`, `CompanyContactIdentity`
3. add seed migration for control company + Baileys provider + current superuser memberships
4. add bridging fields to `WhatsAppAccount`, `WhatsAppContact`, `Product`, `Inquiry`
5. backfill current rows
6. implement `CompanyEnrollmentService`
7. then start the company-scoped permission rewrite

This keeps risk low and preserves working functionality throughout the transition.

---

## 16. Summary

The agreed implementation path is:

- add a new `tenancy` app
- introduce company-based ownership
- seed a control company
- seed Baileys as the default WhatsApp provider
- wrap all current WhatsApp accounts under company-owned communication accounts
- make products and inquiries company-owned
- add `industry_type` at the company level
- implement enrollment as one transactional service
- preserve the trading domain as-is while making it tenant-owned
- defer true multi-industry business expansion into separate future apps

This is the safest path to a tenant-based, provider-aware, multi-industry-ready ChatLens without breaking the current system.

---

*Prepared for ChatLens on 2026-07-22 as the concrete migration specification for tenancy, enrollment, providers, and industry support.*
