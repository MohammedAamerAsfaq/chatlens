# KiwiRouter Implementation Design

## Status

Proposed implementation.

## Objective

Introduce a database-configured AI routing layer named `KiwiRouter`. A router
selects one configured AI agent for each request from an ordered member list.
It provides bounded capacity, failover, routing auditability, and a path toward
cost and performance-based selection without coupling business workflows to a
specific provider or model.

KiwiRouter is used by inquiry-processing passes independently. A pass can use
one direct AI agent, preserving current behavior, or a KiwiRouter instance.

## Terminology

- **AI agent**: an existing `AIProviderConfig` record. It defines a provider,
  model, credential, endpoint, and capability.
- **KiwiRouter**: a named routing policy with one or more AI-agent members.
- **Router member**: one enabled AI agent, its preference order, capacity data,
  and optional cost/performance data.
- **Routing decision**: an immutable record of why one member was selected,
  delayed, skipped, failed over, or rejected.
- **Pass**: one durable stage in inquiry classification.

## Provider Metadata Requirement

Rule or policy-based routing is only valid when the provider exposes reliable,
model-specific data to the client. Before enabling a member for any rule other
than ordered routing, the configuration must contain verified values for:

- request limit per minute (RPM),
- token limit per minute (TPM),
- maximum concurrent requests, when published,
- input cost per million tokens,
- output cost per million tokens,
- request timeout or provider SLA, when published,
- model identifier and provider capability.

If the provider does not expose these values, or the values cannot be verified
for the configured account/tier/model, KiwiRouter must mark the member as
`metadata_incomplete`. It may participate only in `ordered_capacity_fill`.
Cost-, latency-, throughput-, and policy-based rules must skip it. Operator
entered values are allowed, but must be marked `operator_supplied` with a
review date; they are not equivalent to provider-published data.

The router must never infer cost, RPM, or TPM from one previous call and treat
that inference as an enforceable provider limit.

## Initial Routing Strategy

### Ordered Capacity Fill

This is the first production strategy and is valid even with incomplete cost
or performance metadata.

Each request is routed to the lowest `priority` enabled member with an atomic
available reservation. If that member is full, selection continues to the next
member. For members ordered DeepSeek, Gemini, Nemotron with RPM limits 3, 5,
and 2, ten requests in one minute are reserved as:

```text
DeepSeek: 3
Gemini:   5
Nemotron: 2
```

When no member has capacity, the router returns a durable deferral result. It
does not sleep inside a task worker. The task is moved to `retrying` with an
`available_at` time equal to the earliest expected capacity window.

### Future Strategies

- `lowest_estimated_cost`: select the eligible member with lowest estimated
  input/output cost.
- `lowest_latency`: select the healthy eligible member with lowest rolling
  latency percentile.
- `highest_throughput`: select the member with most available RPM/TPM and
  concurrency capacity.
- `weighted_distribution`: distribute across eligible members by configured
  weights.
- `policy_score`: calculate a documented score from cost, latency, health,
  capacity, and pass-specific policy weights.

All future strategies require provider-published or explicitly reviewed
metadata for every attribute used in the decision.

## Data Model

### KiwiRouter

```text
id
company_id nullable             # null means control-plane/global router
name unique within company
description
capability                      # agent, chat, embedding
strategy                        # ordered_capacity_fill initially
is_active
default_request_timeout_seconds
created_at, updated_at
```

### KiwiRouterMember

```text
id
router_id
provider_config_id              # FK to AIProviderConfig
priority                        # unique per router, lower is preferred
is_enabled
rpm_limit nullable
tpm_limit nullable
max_concurrency nullable
input_cost_per_million nullable
output_cost_per_million nullable
metadata_source                 # provider_published, operator_supplied, incomplete
metadata_verified_at nullable
metadata_review_due_at nullable
request_timeout_seconds nullable
created_at, updated_at
```

Capacity/cost fields belong on the router member, not only on the provider
config. The same model may have different limits and pricing under different
accounts, tiers, regions, or router policies.

### KiwiRouterReservation

```text
id
router_member_id
correlation_id
task_id nullable
estimated_input_tokens
estimated_output_tokens
reserved_at
expires_at
released_at nullable
outcome                         # reserved, dispatched, succeeded, failed, expired
```

Reservations make rate-limit decisions atomic across concurrent task workers.
They are short-lived and must expire if a worker dies before dispatch.

### KiwiRoutingDecision

```text
id
router_id nullable
router_member_id nullable
provider_config_id nullable
task_id nullable
correlation_id
workflow_key                    # inquiry_pass1, inquiry_pass2, inquiry_pass3
strategy
decision                        # selected, deferred, skipped, failed_over, rejected
reason
estimated_input_tokens
estimated_output_tokens
actual_input_tokens nullable
actual_output_tokens nullable
estimated_cost nullable
actual_cost nullable
queue_wait_ms nullable
provider_latency_ms nullable
created_at
```

This table is append-only. It is the source for router performance, spend,
capacity, and failover reporting.

## Atomic Capacity Reservation

1. The task estimates input tokens from the final prompt and reserves a
   configured output-token budget.
2. KiwiRouter locks the candidate member/reservation state transactionally.
3. It counts valid reservations in the rolling RPM and TPM windows and active
   dispatches for concurrency.
4. It inserts one reservation only if all configured limits allow it.
5. The task dispatches the provider request with a request timeout no greater
   than both the member timeout and the remaining durable task deadline.
6. The router records actual usage/cost where supplied by the provider and
   closes the reservation.
7. On provider timeout, 429, connection failure, or malformed response, the
   router records the failure and may attempt the next eligible member only if
   the task is idempotent and the provider response was not accepted.

No worker thread waits in a rate-limiter loop. A capacity shortage schedules a
durable retry. This is required to protect worker throughput and make shutdown
safe.

## Health and Circuit Breaking

Each member has derived runtime health:

- `healthy`: eligible for selection.
- `throttled`: provider returned 429 or reservation capacity is exhausted.
- `degraded`: rolling error/latency thresholds are exceeded.
- `open_circuit`: repeated failures; excluded until cooldown expires.
- `metadata_incomplete`: ordered routing only.
- `disabled`: operator disabled.

Authentication errors disable selection until an operator changes the
credential/configuration. Timeouts and server errors use a limited cooldown.
Health transitions are recorded as routing decisions or member events.

## Inquiry Classification Workflow

### Pass 1: Inquiry Gate

Purpose: decide whether a message is a real WTB/WTS inquiry.

Input: message text and only minimal required context.

Output: strict JSON or enum containing `YES`/`NO`; no product extraction,
inventory lookup, or matching.

If `NO`, persist a classification with no inquiry and terminate the workflow.
If `YES`, enqueue pass 2 with the same `whatsapp-message:<message_id>`
correlation ID.

### Pass 2: Extraction and Inquiry Creation

Purpose: retain the current V2 extraction/classification behavior for messages
approved by pass 1.

It creates the inquiry and extracted inquiry products. It must be a durable
task and record the KiwiRouter decision used for this pass.

### Pass 3: Candidate Matching

Purpose: retain the current V2 candidate retrieval and AI match decision.

Pass 3 must become a separate durable task. It must not be started from a raw
background thread. Its idempotency key is scoped to the classification/inquiry
version, and stale work is recoverable from its durable task state.

## Per-Pass Configuration

Add a workflow settings record for each pass:

```text
workflow_key
execution_mode                  # direct_agent or kiwi_router
direct_provider_config_id null
kiwi_router_id null
task_queue_name
task_timeout_seconds
max_attempts
is_enabled
```

Exactly one target is required when enabled. `direct_agent` preserves current
behavior. `kiwi_router` invokes KiwiRouter. Validation rejects configurations
with both or neither target selected.

## Service Boundaries

```text
business pass handler
  -> AIExecutionService
     -> DirectAgentExecutor OR KiwiRouterService
        -> AIProviderManager
           -> provider HTTP client
```

- Business services must not call a provider directly.
- `AIExecutionService` estimates tokens, carries correlation/task context, and
  records usage.
- `KiwiRouterService` only selects/reserves/fails over; it does not parse
  inquiry responses.
- Provider clients enforce the actual HTTP timeout and return provider usage
  headers/body when available.
- Durable queue tasks own retries. Router capacity deferrals set `available_at`
  rather than blocking a worker.

## Rollout Plan

1. Add database models, migrations, admin/API, and router configuration UI.
2. Add usage and routing-decision logging without changing direct-agent calls.
3. Implement `ordered_capacity_fill` and reservations with one non-critical
   workflow in shadow/observe mode.
4. Route Pass 1 through KiwiRouter with direct-agent fallback disabled only
   after capacity and audit verification.
5. Implement durable Pass 3 and stale-pass recovery.
6. Migrate Pass 2 and Pass 3 independently.
7. Enable policy strategies only for members with verified required metadata.

## Acceptance Criteria

- Ten concurrent requests respect the ordered 3/5/2 RPM example exactly.
- No provider receives more requests/tokens/concurrency than its reservations.
- Capacity exhaustion defers tasks without sleeping or creating raw threads.
- A worker restart leaves no pass stranded without a recoverable task.
- Every provider call has router/direct-agent identity, correlation ID, cost,
  latency, usage, and outcome recorded where data is available.
- Incomplete provider metadata cannot enable cost/latency/throughput policies.
- A failed member fails over only under safe, documented error conditions.
- Pass 1 false-positive and false-negative rates are measurable before it is
  made mandatory for all inquiry creation.
