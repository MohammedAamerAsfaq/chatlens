# Tenant Account Model Plan

> **Status:** Proposed architecture document only — no schema changes implemented yet.
> **Prepared:** 2026-07-22
> **Purpose:** Define the concrete tenant/account model ChatLens should adopt before implementation.
> **Scope:** Company tenancy, user membership, communication-account structure, connection providers, control-company migration path, and product/contact ownership.

---

## 1. Goal

Restructure ChatLens from a user-owned WhatsApp application into a **tenant-based company platform** where:

- a **company** is the main tenant boundary,
- users belong to companies with roles,
- companies can own multiple communication accounts across multiple channels,
- products and the main contact list belong to the company,
- each communication account can still maintain its own account-local contacts/messages,
- each communication account can be backed by an explicit connection provider implementation,
- existing system data is preserved by assigning it to a **control company**.

This document defines the target model first, so the actual implementation can follow a stable design instead of incremental ad hoc changes.

---

## 2. Required Business Model

The target model for ChatLens is:

1. ChatLens is a **tenant-based app**.
2. A **company account** is the top-level business entity and main ownership boundary.
3. Each company can have multiple **users** with different roles such as super user / admin / normal user.
4. Each company can have multiple **social media accounts** such as WhatsApp, Telegram, Signal, Discord, etc.
5. Each company can also have multiple **email accounts** such as Gmail, Exchange, IMAP-backed mailboxes, etc.
6. Under each social or email account there may be multiple **enrolled identities**:
   - phone numbers / device sessions for social channels
   - email addresses / mailbox identities for email channels
7. Existing ChatLens data should be migrated under a **control company**, and the current superuser should be attached to that company.
8. Product list and customer/contact list should belong to the **company**; current records should initially belong to the control company.
9. For now, each company has **one product list** and **one main company contact list** shared across all of its channels/accounts.
10. Each communication account may still maintain its **own account-local contact list** as required by the current ingestion design, but those account-local contacts may also be linked to the company’s main contact list.
11. Each communication account should explicitly reference a **connection provider** (for example, WhatsApp via Baileys), because different channels and even the same channel may later use different provider implementations.

---

## 3. Current State vs Target State

## 3.1 Current state

Today the application is effectively centered on channel-specific records:

- `WhatsAppAccount.owner -> django.contrib.auth.User`
- WhatsApp contacts belong directly to `WhatsAppAccount`
- inquiries belong directly to `WhatsAppAccount`
- products are global, not tenant-owned
- there is no company tenant entity
- there is no multi-channel abstraction above WhatsApp

This is a single-channel, mostly single-tenant shape.

## 3.2 Target state

The new model should become:

```text
Company
  ├─ CompanyMembership (users + roles)
  ├─ CommunicationAccount
  │    ├─ ConnectionProvider
  │    ├─ AccountEndpoint / EnrolledIdentity
  │    ├─ ChannelLocalContact
  │    ├─ ChannelChats / Messages / Sync records
  │    └─ linked CompanyContact records
  ├─ CompanyContact
  ├─ Product
  └─ other company-owned business data
```

The key change is that **company becomes the ownership root**.

---

## 4. Core Domain Model

## 4.1 Company

This is the top-level tenant model.

### Purpose

- primary ownership boundary
- billing / subscription / validity boundary
- product-list boundary
- main contact-list boundary
- parent of all communication accounts

### Proposed fields

```python
class Company(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    company_type = models.CharField(
        max_length=20,
        choices=[
            ('control', 'Control'),
            ('customer', 'Customer Company'),
            ('internal', 'Internal'),
        ],
        default='customer',
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

### Notes

- `company_type='control'` is for the system-level management company.
- `parent_company` allows the control company to act as the managing/enrolling company for other tenants if needed.
- validity dates support the future “enrollment / validity / management” requirement without redesign.

---

## 4.2 Company Membership

Users should not own WhatsApp accounts directly. Users belong to companies through membership.

### Purpose

- attach users to companies
- define company-level permissions
- allow one user to belong to multiple companies if needed later

### Proposed fields

```python
class CompanyMembership(models.Model):
    ROLE_CHOICES = [
        ('super_user', 'Super User'),
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('user', 'User'),
        ('viewer', 'Viewer'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='company_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'user'], name='unique_company_membership')
        ]
```

### Role meaning

- `super_user`: highest authority within that company
- `admin`: company administration, setup, account management
- `manager`: operational/business manager
- `user`: normal operator
- `viewer`: read-only access

### Policy note

This is **company-level super user**, not a replacement for Django’s global `is_superuser`.

---

## 4.3 CommunicationAccount

This is the abstraction above WhatsApp/email/etc. It represents a communication integration owned by a company.

### Purpose

- unify WhatsApp, Telegram, Signal, Discord, Gmail, Exchange, etc.
- keep company ownership independent of channel implementation

### Proposed fields

```python
class CommunicationAccount(models.Model):
    CHANNEL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('telegram', 'Telegram'),
        ('signal', 'Signal'),
        ('discord', 'Discord'),
        ('gmail', 'Gmail'),
        ('exchange', 'Exchange'),
        ('imap', 'IMAP'),
        ('other', 'Other'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='communication_accounts')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)

    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    external_account_id = models.CharField(max_length=255, blank=True)
    config = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Examples

- “Aamer Ashfaq WhatsApp Desk”
- “Sales Gmail”
- “Dubai Telegram Trading”

### Important distinction

This is **not** yet the per-device or per-phone entity. It is the company-owned channel account container.

---

## 4.4 ConnectionProvider

Communication accounts must not implicitly assume one hardcoded integration implementation. The provider used to connect a channel should be represented explicitly in the data model.

### Purpose

- separate **business/channel ownership** from **technical connector implementation**
- allow more than one provider implementation per channel over time
- make the current WhatsApp/Baileys integration an explicit default rather than an invisible assumption
- support future email/social connectors without redesign

### Examples

- WhatsApp via `baileys`
- Telegram via `telethon` or a bot-based integration later
- Gmail via Google API
- Exchange via Microsoft Graph
- IMAP via a generic IMAP connector

### Proposed fields

```python
class ConnectionProvider(models.Model):
    CHANNEL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('telegram', 'Telegram'),
        ('signal', 'Signal'),
        ('discord', 'Discord'),
        ('gmail', 'Gmail'),
        ('exchange', 'Exchange'),
        ('imap', 'IMAP'),
        ('other', 'Other'),
    ]

    key = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)

    provider_type = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    is_default_for_channel = models.BooleanField(default=False)

    capabilities = models.JSONField(default=list, blank=True)
    config_schema = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Meaning of key fields

- `key`
  Stable internal identifier such as `baileys`, `gmail_api`, `exchange_graph`.
- `channel`
  The communication family this provider belongs to.
- `provider_type`
  Optional connector/runtime family such as `node_worker`, `oauth_api`, `imap_client`.
- `is_default_for_channel`
  Marks the default provider to use when a new communication account is created for that channel and no override is chosen.
- `capabilities`
  Example values:
  - `["receive_messages", "history_sync", "contacts_sync", "group_sync"]`
  - `["receive_email", "send_email_metadata", "mailbox_sync"]`

### Important rule

`ConnectionProvider` should be treated as a **tenant-usable provider catalog with tenant-level selection**, not as a hardwired global choice on every account.

Meaning:

- provider records themselves are seeded/managed centrally,
- every tenant can use the default provider for a channel automatically,
- a tenant can be assigned a different provider for a channel when explicitly approved,
- changing a tenant away from the default should be controlled by the **control-company super user**.

Reason:

- the provider implementation is platform infrastructure, but provider choice has tenant-level operational impact,
- many companies may use the same default provider,
- some companies may later need a different provider for the same channel,
- that override must remain a controlled administrative action, not an arbitrary tenant-side setting.

### Initial provider seed

The first provider record should be:

```text
ConnectionProvider:
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

This directly matches the current production integration:

- Node.js worker
- `@whiskeysockets/baileys`
- QR-linked WhatsApp session management

### Provider selection policy

For each channel:

- there may be one **system default provider**
- every new tenant/account on that channel uses that default unless explicitly overridden
- an override to a different provider is a **tenant-level administrative decision**
- that override may only be made by the **control-company super user**

In other words:

- provider records are centrally managed,
- provider **selection** is tenant-level,
- tenant-level provider overrides are centrally governed.

### Relationship to AI providers

This is a different concern from `apps/ai_providers`.

- `AIProviderConfig` controls outbound AI services such as Voyage/OpenAI.
- `ConnectionProvider` controls inbound/outbound communication connector implementations such as Baileys/Gmail API/Graph/IMAP.

They should remain separate models.

---

## 4.5 CommunicationAccount Provider Binding

Every communication account should explicitly reference the provider used to operate it.

### Updated target shape

```python
class CommunicationAccount(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='communication_accounts')
    provider = models.ForeignKey(
        ConnectionProvider,
        on_delete=models.PROTECT,
        related_name='communication_accounts',
    )
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)

    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    external_account_id = models.CharField(max_length=255, blank=True)
    config = models.JSONField(null=True, blank=True)
    ...
```

### Validation rule

`communication_account.channel` must match `provider.channel`.

For example:

- valid: WhatsApp account + Baileys provider
- invalid: WhatsApp account + Gmail API provider

This should be enforced in model validation and serializer/service layers.

### Tenant-level default vs override behavior

The provider stored on each `CommunicationAccount` is the tenant-level effective choice for that account.

Creation rule:

1. when a company creates a communication account for a channel,
2. ChatLens auto-selects the current default provider for that channel,
3. unless a control-company super user explicitly assigns a different provider.

This means the default is global in origin, but tenant-specific in effect once the account is created.

### Why keep both `channel` and `provider`

- `channel` is business/reporting taxonomy
- `provider` is technical implementation choice

This avoids deriving business meaning from connector names.

### Administrative control rule

Normal company users, admins, and even company-level super users should **not** freely switch provider implementations unless that ability is explicitly granted later by policy.

For the initial design:

- provider override authority belongs only to the **control-company super user**
- normal tenant operation uses the default provider automatically

This keeps connector changes under central governance, which is important because provider changes can affect:

- ingestion behavior
- session/auth mechanics
- data shape and sync semantics
- operational support burden

---

## 4.6 AccountEndpoint / EnrolledIdentity

One communication account may contain multiple enrolled identities.

### Purpose

- represent phone numbers, linked devices, email addresses, mailbox aliases, etc.
- support your requirement that one social/email account can have multiple phone/email enrolled

### Proposed fields

```python
class AccountEndpoint(models.Model):
    ENDPOINT_TYPE_CHOICES = [
        ('phone', 'Phone'),
        ('email', 'Email'),
        ('handle', 'Handle / Username'),
        ('device', 'Device Session'),
    ]

    communication_account = models.ForeignKey(
        CommunicationAccount,
        on_delete=models.CASCADE,
        related_name='endpoints',
    )

    endpoint_type = models.CharField(max_length=20, choices=ENDPOINT_TYPE_CHOICES)
    value = models.CharField(max_length=255)   # phone number / email / handle / session ref
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Channel mapping examples

- WhatsApp:
  - phone `9715...`
  - worker session id / linked-device identity
- Gmail:
  - primary mailbox `sales@company.com`
  - alias mailbox `trading@company.com`
- Exchange:
  - mailbox identities under one tenant-backed integration

### Why separate this from `CommunicationAccount`

Because a company may conceptually have one account/integration but several enrolled identities under it.

---

## 4.7 Channel-Specific Account Models

The current app already has a rich `WhatsAppAccount` model with worker/session fields. That should remain as a **channel-specific operational model**, but no longer be tenant-owned through `owner`.

### Proposed direction

Refactor `WhatsAppAccount` so it points to `CommunicationAccount`, not directly to `User`.

Target shape:

```python
class WhatsAppAccount(models.Model):
    communication_account = models.OneToOneField(
        'tenancy.CommunicationAccount',
        on_delete=models.CASCADE,
        related_name='whatsapp_account',
    )
    primary_endpoint = models.ForeignKey(
        'tenancy.AccountEndpoint',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    display_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    ...
```

### Ownership after refactor

- `company = whatsapp_account.communication_account.company`
- user access comes through company membership
- operational WhatsApp logic stays in the current app

### Same pattern later

Future channel apps may follow the same pattern:

- `TelegramAccount`
- `EmailAccount`
- `DiscordAccount`

All company-owned through `CommunicationAccount`.

---

## 4.8 CompanyContact

This is the company’s **main contact list** shared conceptually across its channels.

### Purpose

- one master customer/supplier/contact list per company
- unify contact identity across WhatsApp/email/etc.
- support linking channel-local contacts to a company-level main contact

### Proposed fields

```python
class CompanyContact(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='contacts')

    display_name = models.CharField(max_length=255, blank=True)
    legal_name = models.CharField(max_length=255, blank=True)

    category = models.CharField(
        max_length=20,
        choices=[
            ('supplier', 'Supplier'),
            ('customer', 'Customer'),
            ('both', 'Both'),
            ('other', 'Other'),
        ],
        blank=True,
    )

    is_company = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Related identity records

Because one main contact may have many phones/emails/handles:

```python
class CompanyContactIdentity(models.Model):
    IDENTITY_TYPE_CHOICES = [
        ('phone', 'Phone'),
        ('email', 'Email'),
        ('whatsapp_jid', 'WhatsApp JID'),
        ('telegram_handle', 'Telegram Handle'),
        ('discord_handle', 'Discord Handle'),
        ('other', 'Other'),
    ]

    contact = models.ForeignKey(CompanyContact, on_delete=models.CASCADE, related_name='identities')
    identity_type = models.CharField(max_length=30, choices=IDENTITY_TYPE_CHOICES)
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

### Important rule

For now:

- one **main company contact list** per company
- channel-local contacts may exist separately
- channel-local contacts may optionally link to one `CompanyContact`

---

## 4.9 ChannelLocalContact

The current design requires channel-specific/local contact records such as `WhatsAppContact`. That is still valid.

### Proposed direction

Keep `WhatsAppContact` as the operational/local contact record, but add:

- indirect company ownership through account -> communication_account -> company
- optional link to `CompanyContact`

Target shape:

```python
class WhatsAppContact(models.Model):
    account = models.ForeignKey('whatsapp_bridge.WhatsAppAccount', ...)
    company_contact = models.ForeignKey(
        'tenancy.CompanyContact',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='whatsapp_contacts',
    )
    ...
```

### Meaning

- `WhatsAppContact` remains the raw/local/contact-sync record from WhatsApp
- `CompanyContact` is the company’s curated main contact record
- one company contact may map to many local contact rows across multiple accounts/channels

This matches your requirement:

- separate contact list per social/email account can remain
- they can also be linked to the company main contact list

---

## 4.10 Product Ownership

Products should be company-owned, not global.

### Proposed direction

Add `company` to:

- `Product`
- derived product-related models where needed through direct or indirect ownership

Target shape:

```python
class Product(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(...)
    ...
```

### Rule for now

Each company has:

- one product catalog
- shared across all of its communication accounts

That matches your requirement exactly.

### Existing data

All current products should be assigned initially to the **control company**.

---

## 4.11 Inquiry and Business Data Ownership

Business records such as inquiries should also become company-owned.

### Proposed direction

Add a direct `company` foreign key to business records even if they can be derived via account.

Example:

```python
class Inquiry(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='inquiries')
    account = models.ForeignKey(WhatsAppAccount, on_delete=models.CASCADE, related_name='inquiries')
    ...
```

### Why keep both company and account

- `account` tells us which exact communication account generated the inquiry
- `company` gives fast tenant scoping and future-proofs cross-channel reporting

The same pattern is recommended for:

- channel messages
- sync logs
- dropped messages
- worker alerts
- unresolved messages

Even where ownership is derivable, direct tenant FK is operationally useful.

---

## 5. Control Company

## 5.1 Purpose

The control company is the bootstrap tenant for the current system state.

It will:

- own all current products initially
- own all current WhatsApp accounts initially
- own all current communication accounts created around those WhatsApp accounts
- own all current contacts/inquiries/messages initially through those accounts
- contain the current Django superuser as a company super user
- optionally manage enrollment/validity of other companies later

## 5.2 Proposed seed record

```text
Company:
  name: "Control Account"
  slug: "control-account"
  company_type: "control"
  is_active: true
```

## 5.3 Membership

The current global Django superuser should receive:

```text
CompanyMembership:
  company = Control Account
  user = current superuser
  role = super_user
```

## 5.4 Management role

The control company may act as:

- internal operator tenant
- onboarding/management tenant
- validity-management parent for other companies

This should be a business capability, not a schema hack.

## 5.5 Existing WhatsApp bootstrap with Baileys

For the current application state, the initial seeded ownership/provider chain should be:

```text
Control Company
  └─ CommunicationAccount
       channel: "whatsapp"
       provider: "baileys"
       └─ WhatsAppAccount (existing operational record)
```

For each existing `WhatsAppAccount` row:

1. create or reuse the seeded `ConnectionProvider(key="baileys")`
2. create a `CommunicationAccount` under the control company with:
   - `channel="whatsapp"`
   - `provider=baileys`
   - `name` derived from current display name / phone number
3. relink the existing `WhatsAppAccount` to that `CommunicationAccount`
4. create the relevant `AccountEndpoint` rows for current phone/session identity

This preserves the current system behavior while making the provider explicit.

For newly onboarded tenants in the same initial phase:

- WhatsApp communication accounts should default to the seeded `baileys` provider
- no tenant-specific override should exist unless a control-company super user sets one

---

## 6. Concrete Ownership Rules

The ownership rules should be:

### Company owns

- communication accounts
- company memberships
- company main contacts
- products
- inquiries
- all channel data logically associated with that company

### Communication account owns

- its chosen provider binding
- its enrolled identities/endpoints
- its local contacts
- its chats, messages, sync logs, alerts, unresolved/dropped records

### Local contact may link to main company contact

- optional, not mandatory at ingestion time
- operator or matching logic can link them later

### User access

- granted through company membership
- not by direct ownership of a WhatsApp account

---

## 7. Recommended Django App Structure

Introduce a first-class tenancy app, for example:

```text
apps/
  tenancy/
    models/
      company.py
      membership.py
      connection_provider.py
      provider_policy.py
      communication_account.py
      account_endpoint.py
      company_contact.py
    services/
      company_service.py
      membership_service.py
```

### Why a separate app

- keeps tenant/business ownership separate from channel implementation
- avoids turning `whatsapp_bridge` into the global ownership app for all future channels
- makes multi-channel expansion cleaner

### Optional supporting model

If provider policy needs to be made explicit rather than implicit, add a small tenant/provider policy model:

```python
class CompanyChannelProviderPolicy(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='provider_policies')
    channel = models.CharField(max_length=20, choices=ConnectionProvider.CHANNEL_CHOICES)
    provider = models.ForeignKey(ConnectionProvider, on_delete=models.PROTECT, related_name='company_policies')
    is_override = models.BooleanField(default=False)
    assigned_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'channel'], name='unique_company_channel_provider_policy')
        ]
```

Use this only if you want the override/default decision recorded at the company+channel level outside the communication account rows themselves.

If you want the smaller first implementation, keep provider selection directly on `CommunicationAccount` and enforce the same policy in services/admin logic.

---

## 8. Migration Strategy

Implementation should be phased.

## Phase 1 — Introduce tenancy models

Create:

- `Company`
- `CompanyMembership`
- `ConnectionProvider`
- `CommunicationAccount`
- `AccountEndpoint`
- `CompanyContact`
- `CompanyContactIdentity`

Optionally also create:

- `CompanyChannelProviderPolicy`

No existing ownership fields removed yet.

## Phase 2 — Seed control company

Data migration:

- create control company
- create membership for current superuser
- create default provider record:
  - `key="baileys"`
  - `channel="whatsapp"`
  - `is_default_for_channel=True`

Documented policy:

- this provider is the default WhatsApp provider for all tenants
- only a control-company super user may assign a different provider

## Phase 3 — Bridge current WhatsApp accounts into company ownership

For each existing `WhatsAppAccount`:

- create `CommunicationAccount(company=control_company, channel='whatsapp', provider=baileys)`
- link `WhatsAppAccount` to it
- create `AccountEndpoint` from current phone/session identity where appropriate

Keep existing `owner` field temporarily during transition.

## Phase 4 — Company-own products and business records

Add `company` to:

- `Product`
- `Inquiry`
- any other business table where direct tenant scoping is required

Backfill all current rows to control company.

## Phase 5 — Link local contacts to company contacts

Add `company_contact` FK to `WhatsAppContact`.

Initially:

- nullable
- no forced backfill needed for every row immediately

Optional later matching/backfill can connect local contacts to curated main company contacts.

## Phase 6 — Remove direct user ownership from WhatsAppAccount

Once all APIs and permissions are migrated:

- remove `WhatsAppAccount.owner`
- use company membership and communication-account ownership everywhere

---

## 9. Permission Model Implications

This tenant model implies the API should move to:

- request user -> memberships -> visible companies
- visible companies -> visible communication accounts
- visible communication accounts/company-owned objects -> visible data

That means future access checks should be based on:

- `company`
- membership role
- optional control-company elevated rights

This is the correct direction for the earlier code-review finding about global `IsAuthenticated` access.

---

## 10. Important Design Decisions

## 10.1 Company is the tenant, not communication account

Correct because:

- one company may operate many channels
- one product list spans those channels
- one main contact list spans those channels

## 10.2 Channel-local contact list remains valid

Correct because:

- synced/raw contact identities differ by platform
- operational ingestion still needs local channel records
- linking them to a company master contact should be optional and gradual

## 10.3 Provider implementation must be explicit, not implied

Correct because:

- WhatsApp currently uses Baileys, but that is an implementation choice, not the business identity of the account
- future channels will need different connector implementations
- the same channel may later support multiple providers
- bootstrapping current data into tenancy should preserve the technical runtime currently in use

## 10.4 Provider choice is tenant-level, but override authority is centralized

Correct because:

- different tenants may eventually need different providers
- the default provider should still make onboarding simple
- provider switching is an infrastructure-sensitive action and should not be uncontrolled
- the control-company super user is the right initial authority for non-default provider assignment

## 10.5 Products should be company-owned immediately in the new model

Correct because:

- product catalog is business data, not system-global metadata
- current global product table is not tenant-safe

## 10.6 Keep a direct company FK on major business records

Even where derivable, this is recommended for:

- simpler tenant queries
- cleaner authorization
- easier future reporting

## 10.7 Control company is real business data, not a temporary fake row

It should remain a valid tenant for:

- internal operations
- management dashboards
- onboarding and subscription supervision

---

## 11. Initial Target Mapping for Current Models

### Current `WhatsAppAccount`

Current:

- owned by `User`
- implicitly tied to Baileys in code, not in data

Target:

- owned by `CommunicationAccount`
- `CommunicationAccount.provider = ConnectionProvider(key='baileys')`
- therefore owned by `Company`

### Current `WhatsAppContact`

Current:

- belongs to `WhatsAppAccount`

Target:

- still belongs to `WhatsAppAccount`
- optionally links to `CompanyContact`

### Current `Product`

Current:

- global

Target:

- belongs to `Company`

### Current `Inquiry`

Current:

- belongs to `WhatsAppAccount`

Target:

- belongs to `Company`
- also belongs to `WhatsAppAccount`

---

## 12. Recommended Next Implementation Step

Before writing code, approve this target structure:

1. create `Company` as the tenant root
2. create `CompanyMembership`
3. create `ConnectionProvider`
4. create `CommunicationAccount`
5. create `AccountEndpoint`
6. create `CompanyContact`
7. move product ownership to company
8. make WhatsApp operational records company-owned through communication account
9. seed Baileys as the default WhatsApp provider
10. bootstrap all current data into a control company

Once approved, the first implementation document after this should be a **phase-by-phase migration spec** with exact model diffs, migrations, and API permission changes.

---

*Prepared for ChatLens tenant/account redesign on 2026-07-22.*
