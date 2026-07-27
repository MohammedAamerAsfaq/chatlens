# Task and Queue Management Design

> **Status:** Future design proposal only. Do not implement as part of the current remediation patch.
> **Prepared:** 2026-07-25
> **Purpose:** Define a mature, reusable background execution architecture for ChatLens that preserves current behavior until explicitly migrated.

---

## 1. Goal

Create two independent reusable modules:

- **Task Management**
- **Queue Management**

These modules should support any background work in the application, including message classification, embeddings, unresolved-message recovery, price-list automation, metadata replay, report generation, and future tenant operations.

The design must allow:

- current development behavior to continue while the system is introduced,
- DB-backed durable task persistence,
- a continuous management-command executor outside IIS on Windows Server,
- future Celery integration in production,
- clear logging, retries, failures, and debugging,
- gradual migration of existing raw-thread call sites one at a time.

---

## 2. Design Principles

1. **No silent fallback behavior.**
   A task failure must be recorded with status, error details, attempt count, and timestamps.

2. **Task creation and task execution are separate concerns.**
   Application code should enqueue work. Workers should execute work.

3. **Queue transport must be replaceable.**
   The application should not care whether work is stored in the database, Celery/Redis, or another broker later.

4. **Tasks must be idempotent where possible.**
   Retried tasks should not duplicate messages, inquiries, embeddings, or side effects.

5. **Current functionality must not break during migration.**
   Existing raw-thread paths remain until each path is explicitly migrated and verified.

6. **Production execution must not depend on IIS request lifecycle.**
   Queue consumers should run outside IIS as a separate process/service.

---

## 3. Module 1 - Task Management

Task Management owns the definition, registration, validation, and execution of task types.

### Responsibilities

- Register task handlers by stable task key.
- Validate task payloads.
- Execute a task handler.
- Enforce idempotency keys where required.
- Record task result metadata.
- Normalize exceptions into structured failure details.
- Provide reusable task APIs for any app.

### Proposed app structure

```text
apps/
  task_management/
    models.py
    registry.py
    services.py
    handlers.py
    admin.py
    management/
      commands/
        run_background_tasks.py
```

### Core task model

```python
class BackgroundTask(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_RETRYING = 'retrying'
    STATUS_CANCELLED = 'cancelled'

    PRIORITY_LOW = 10
    PRIORITY_NORMAL = 50
    PRIORITY_HIGH = 90

    task_key = models.CharField(max_length=150, db_index=True)
    queue_name = models.CharField(max_length=100, default='default', db_index=True)

    status = models.CharField(max_length=20, db_index=True)
    priority = models.IntegerField(default=PRIORITY_NORMAL, db_index=True)

    payload = models.JSONField(default=dict)
    result = models.JSONField(default=dict, blank=True)

    idempotency_key = models.CharField(max_length=255, blank=True, db_index=True)
    correlation_id = models.CharField(max_length=255, blank=True, db_index=True)

    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)

    available_at = models.DateTimeField(db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.CharField(max_length=255, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    last_error = models.TextField(blank=True)
    last_traceback = models.TextField(blank=True)

    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    company = models.ForeignKey('tenancy.Company', null=True, blank=True, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Supporting models

```python
class BackgroundTaskEvent(models.Model):
    task = models.ForeignKey(BackgroundTask, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=50)
    message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

Optional later:

```python
class BackgroundTaskSchedule(models.Model):
    task_key = models.CharField(max_length=150)
    queue_name = models.CharField(max_length=100, default='default')
    payload = models.JSONField(default=dict)
    cron_expression = models.CharField(max_length=100, blank=True)
    interval_seconds = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_enqueued_at = models.DateTimeField(null=True, blank=True)
```

---

## 4. Module 2 - Queue Management

Queue Management owns enqueueing, claiming, retrying, scheduling, and backend transport.

### Responsibilities

- Enqueue tasks.
- Claim available tasks safely.
- Prevent duplicate active tasks where idempotency requires it.
- Apply retry policy.
- Release stale locks.
- Provide queue metrics.
- Support multiple backend implementations.

### Proposed app structure

```text
apps/
  queue_management/
    backends/
      base.py
      database.py
      celery.py
    services.py
    settings.py
    metrics.py
```

### Queue backend interface

```python
class QueueBackend:
    def enqueue(self, task_key, payload, **options):
        raise NotImplementedError

    def claim(self, queue_name, worker_id, limit):
        raise NotImplementedError

    def mark_succeeded(self, task, result=None):
        raise NotImplementedError

    def mark_failed(self, task, error, traceback_text=''):
        raise NotImplementedError

    def retry_or_fail(self, task, error, traceback_text=''):
        raise NotImplementedError

    def release_stale_locks(self):
        raise NotImplementedError
```

### Initial backend

The first backend should be **database-backed**.

Reason:

- Works in development without Redis.
- Works on Windows Server without extra services.
- Gives immediate visibility and auditability.
- Allows safe staged migration from current raw threads.

### Future backend

Add a Celery backend later:

- DB remains the system-of-record for task observability if desired.
- Celery/Redis can become the execution transport.
- The same Task Management handlers remain reusable.

---

## 5. Execution Modes

## 5.1 Development

Current development setup can continue unchanged until migration starts.

When testing the queue design:

Terminal 1:

```powershell
python manage.py runserver
```

Terminal 2:

```powershell
python manage.py run_background_tasks --interval 1
```

Debug one batch:

```powershell
python manage.py run_background_tasks --once --limit 10
```

Rules:

- Do not auto-start the worker inside `runserver`.
- Do not rely on Django autoreloader to manage workers.
- Use `--once` for deterministic debugging and tests.

## 5.2 Production - IIS + Windows Server

IIS should continue serving HTTP only.

The background worker should run outside IIS:

```powershell
python manage.py run_background_tasks --interval 2 --queue default
```

Recommended hosting options:

- Windows Service via NSSM or WinSW.
- Dedicated scheduled task for periodic one-shot execution.
- Dedicated supervised console process.

Recommended production behavior:

- One or more worker processes per queue.
- Conservative polling interval, for example 2-5 seconds.
- Stale lock cleanup.
- Explicit logs for task failure and queue saturation.
- No background work should depend on an active web request after enqueue.

## 5.3 Celery Production Mode

Later, production can use Celery:

```text
Django request -> Queue Management enqueue -> Celery broker -> Celery worker -> Task Management handler
```

The application should not call Celery directly from feature code. It should call Queue Management, which chooses the active backend.

---

## 6. Configuration

Initial configuration can live in Django settings/env:

```python
BACKGROUND_TASK_BACKEND = 'database'
BACKGROUND_TASK_DEFAULT_QUEUE = 'default'
BACKGROUND_TASK_POLL_INTERVAL_SECONDS = 2
BACKGROUND_TASK_BATCH_SIZE = 10
BACKGROUND_TASK_LOCK_TIMEOUT_SECONDS = 300
BACKGROUND_TASK_MAX_ATTEMPTS = 3
```

Later, expose selected values through the control-company/admin UI:

- poll interval
- enabled queues
- default retry attempts
- queue pause/resume
- max concurrent workers per queue

---

## 7. Task Types To Migrate Gradually

Do not migrate all background work in one patch.

Recommended order:

1. Message classification.
2. Message embedding.
3. Unresolved LID recovery.
4. Price-list automation.
5. Metadata fallback replay.
6. Heavy reports or exports.

Why start with classification:

- It directly affects inquiries.
- It already has logs and idempotency checks.
- It is currently one of the most visible background outcomes.

---

## 8. Example Task Registration

```python
@task_registry.register('whatsapp.classify_message')
def classify_message_task(payload):
    message_id = payload['message_id']
    message = WhatsAppMessage.objects.get(pk=message_id)
    classify_message(message)
    return {'message_id': message_id}
```

Enqueue:

```python
queue.enqueue(
    task_key='whatsapp.classify_message',
    payload={'message_id': message.pk},
    queue_name='ai',
    company=company_for_message(message),
    idempotency_key=f'classify-message:{message.pk}',
)
```

---

## 9. Idempotency Rules

Each task type should define its idempotency policy.

Examples:

- `whatsapp.classify_message`
  - key: `classify-message:{message_id}`
  - safe because `MessageClassification` is one-to-one with message.

- `whatsapp.embed_message`
  - key: `embed-message:{message_id}:{embedding_model}`
  - safe because embeddings should be unique by message/model.

- `whatsapp.recover_unresolved_lid`
  - key: `recover-lid:{account_id}:{lid_jid}:{phone_jid}`
  - safe because resolved messages are protected by provider message IDs.

---

## 10. Failure Handling

Task failures should always be explicit.

On exception:

- increment `attempts`
- store `last_error`
- store traceback
- add `BackgroundTaskEvent`
- if attempts remain, set `status='retrying'` and `available_at` based on backoff
- if exhausted, set `status='failed'`

No task should silently fall back to alternate behavior that hides the failure.

---

## 11. Observability

Minimum required views/API later:

- pending tasks by queue
- running tasks by worker
- failed tasks
- retry count
- oldest pending task age
- average runtime
- last error
- task detail with payload/result/events

This should eventually replace debugging by raw logs alone.

---

## 12. Migration Strategy

### Step 1 - Add modules only

- Create Task Management and Queue Management models/services.
- No production call sites changed.
- Current behavior remains untouched.

### Step 2 - Add management command

- Implement `run_background_tasks`.
- Validate with `--once`.
- No production call sites changed.

### Step 3 - Migrate one task type behind a setting

Example:

```python
BACKGROUND_CLASSIFICATION_MODE = 'thread'  # thread | db_queue
```

Default remains current behavior until verified.

### Step 4 - Switch development manually

Run the worker in a second terminal and validate behavior.

### Step 5 - Switch production intentionally

Deploy worker outside IIS.

### Step 6 - Remove old raw-thread path only after confidence

Do not remove the existing path until the DB queue path has been stable.

---

## 13. Non-Goals For First Implementation

Do not implement these in the first pass:

- Celery integration.
- UI dashboard.
- recurring schedules.
- distributed locking beyond database row claims.
- every existing background task migration.

Those can follow after the core queue is proven.

---

## 14. Recommended Next Decision

Before implementation, decide:

1. Should the first task type be `whatsapp.classify_message`?
2. Should the initial backend be database-only?
3. What is the default dev mode: current raw threads or DB queue behind a setting?
4. What production worker host will be used on Windows Server: NSSM, WinSW, Scheduled Task, or manual supervised console?

Recommended answer:

- first task: `whatsapp.classify_message`
- initial backend: database
- default dev mode: current raw threads until explicitly switched
- production host: Windows Service via NSSM or WinSW

