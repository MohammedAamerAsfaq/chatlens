# WhatsApp Ingestion Queue Architecture

**Status:** History and live ingestion queues implemented.

## Purpose

Move WhatsApp persistence out of IIS while keeping historical and live-message
behavior explicitly separated.

## Queue Boundaries

```text
WhatsApp history
  -> Baileys filters and normalizes batches of <= 100
  -> SQLite outbox
  -> Django stores a task and returns HTTP 202
  -> history_ingestion / whatsapp.persist_history_batch
  -> history_embedding_dispatch / whatsapp.dispatch_history_embeddings
  -> embeddings

WhatsApp live message
  -> Baileys normalizes one message
  -> SQLite outbox
  -> Django stores a task and returns HTTP 202
  -> live_ingestion / whatsapp.persist_live_message
  -> embeddings, eligible AI classification, and matching automation rules
```

Historical messages never create classification or automation tasks. The history
dispatch stage is deliberately named and limited to embeddings.

## Persistence Boundary

A queue claim is transport behavior; its task handler owns persistence. Contact,
chat, and message writes remain in one handler because they form one consistency
boundary. Splitting those writes across tasks would introduce ordering failures
and partially persisted records.

PostgreSQL advisory transaction locks serialize writes for one WhatsApp account.
Different accounts can still run concurrently according to queue configuration.

## Live Routing

After a live message has been committed, existing downstream rules are applied:

- text messages are routed to embeddings;
- classification respects company, account, and chat AI settings;
- automation is independent of AI toggles and only runs for a matching active rule.

Downstream tasks retain their existing per-message idempotency and correlation
keys. A live-ingestion retry can therefore recreate missing work safely.

## Payloads

History tasks carry at most 100 normalized messages. Their embedding-dispatch
task contains only message IDs and the history sync-log ID. Live tasks carry one
normalized message. No additional PostgreSQL staging table is required.

## Idempotency

The SQLite event ID and creation timestamp form the transport key. Django combines
that key with the account ID. If an HTTP response is lost, the repeated request
returns the existing task instead of creating another one. The database unique
constraint on `(account, provider_message_id)` remains the final protection.

## Failure Semantics

- SQLite retains an event until Django confirms durable task acceptance.
- HTTP 202 means queued, not fully processed.
- History and live failures retry in their own queues.
- History embedding failure cannot replay message persistence.
- AI, embedding, and automation failures remain isolated.
- IIS performs authentication, validation, and task creation only.

## Operations

```powershell
python.exe manage.py migrate
python.exe manage.py run_background_tasks --queue history_ingestion --queue history_embedding_dispatch --queue live_ingestion --queue ai --queue embeddings --queue automation
```

The embedded SQLite dispatcher may remain enabled. A standalone dispatcher is
optional when the outbox should drain without the WhatsApp socket process:

```powershell
cd whatsapp-worker
npm run start:dispatcher
```

Do not run embedded and standalone dispatchers against the same SQLite database
unless multiple-consumer behavior has been intentionally tested.

## Remaining Work

- Complete the V2 pass-2, recovery, metadata, and reports task handlers.
- Add queue-age and payload-size alerts.
- Consider payload-table storage only if measured task-row size requires it.
