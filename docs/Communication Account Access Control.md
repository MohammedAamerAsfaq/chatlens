# Communication Account Access Control

## Purpose

ChatLens separates authorization into two independent decisions:

1. A role permission decides which action a user may perform.
2. A communication-account assignment decides which account data the user may access.

This contract applies across industry types. Trading inquiries, real-estate opportunities,
Inbox conversations, contacts, groups, outbound messages, and account-derived campaigns
must not bypass it.

## Access Scopes

The `conversations.accounts.view` permission is the source of account scope:

- `all`: every active communication account in the selected company.
- `assigned`: accounts explicitly assigned to the active company membership.
- `own`: accounts assigned with the `owner` access level.
- no grant: no communication-account data.

Company owners, administrators, and managers receive `all` by default. Standard users,
viewers, and campaign operators receive `assigned` by default. A custom role can change
this scope without changing account assignments.

## Assignment Model

`CommunicationAccountAssignment` links one company membership to one company-owned
communication account. It records the access level, active state, assigning user, and
timestamps. Validation rejects cross-company links.

When a WhatsApp account is created through ChatLens, its creator receives an owner
assignment. The migration backfills owner assignments for existing linked WhatsApp
accounts where the owner has an active membership in the same company.

## Administration

The company Users page allows an authorized administrator to select the communication
accounts assigned to each member. Owner assignments cannot be removed through this UI.
Users with `all` account scope do not require individual assignments.

Changing assignments increments the membership authorization version and writes an
authorization audit event.

## Enforcement

The shared `visible_accounts_queryset()` resolver is the only account visibility source.
APIs must scope records through it rather than trusting a client-supplied account ID.

Covered data includes:

- WhatsApp accounts, Inbox chats, messages, contacts, and groups.
- Outbound message history, cancellation, and retry operations.
- Trading inquiries, inquiry products, board statistics, reports, and forwarding targets.
- Direct and group campaigns derived from visible recipient accounts.
- Real-estate opportunities and extracted child records linked to source accounts.
- ClientPulse linked communication accounts, conversation history, contact conversion,
  profile payloads, and manual follow-up sending.
- Message semantic search, embedding status, and embedding backfill operations.

For real estate, account-linked records follow communication-account visibility.
Accountless manual opportunities use their workflow `assigned_to` value when the role
scope is `assigned`. The workflow assignee does not override account access.

## Security Rules

- Supplying an inaccessible account ID returns no data or a not-found response.
- An opportunity assigned to a user remains hidden when its source account is not assigned.
- An opportunity from an assigned account remains visible even when another user owns the
  workflow assignment.
- Platform and company boundaries remain enforced before account scope is evaluated.
- Internal WhatsApp worker ingestion endpoints continue to authenticate as services and do
  not use interactive user assignments.
- Client-supplied account identifiers are validated against the same resolver before any
  search, backfill, conversion, or send operation starts.

## Deployment

1. Deploy backend and frontend together.
2. Run `python manage.py migrate`.
3. Restart the Django application and background task workers.
4. Open Settings > Users and assign communication accounts to non-admin members.
5. Verify each member with a separate login before enabling production use.

No environment variables are required for communication-account assignments.
