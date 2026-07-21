# Contact Message Loss — LID Resolution Fix Proposal

> **Status:** 🟢 P0 implemented (message preservation + outbound persisted-LID lookup) — 🟡 Fix 1 (contacts/group update durable fallback) and Fix 3 (suppression-logging cleanup) designed but still **not implemented**, pending the separately-requested thorough examination. 🔴 The unrelated inbound zero-trace mystery remains fully open.
> **Opened:** 2026-07-20 · **P0 implemented:** 2026-07-21
> **Relationship to other docs:** `Silent Message Drop Investigation.md` tracks a *different, still-unsolved* zero-trace mystery for the same contact (Al Thamam, inbound messages, opened 2026-07-06). This document covers what that investigation's own instrumentation has since surfaced — a confirmed, reproducing **outbound** drop pattern — plus related reporting/suppression gaps found while auditing the worker's error handling for the same class of problem, prompted by a fresh complaint (Azan / Action Link Trading, account "Aamer Ashfaq") on 2026-07-20. See `ChatLens Development Document.md` §9 (Drop Reasons), §13 (LID Handling), §17.2 (incident history) for the surrounding architecture.

## P0 implementation summary (2026-07-21)

Two P0 reliability changes shipped in one pass, per an explicit spec: **(1) never permanently discard a message with real content merely because identity resolution failed**, and **(2) stop outbound LID resolution depending solely on the volatile in-memory cache**. Both are implemented, tested, and do not touch Fix 1 or Fix 3 below (those remain separately gated pending the thorough-examination request from 2026-07-20).

**What changed:**
- New model `WhatsAppUnresolvedMessage` (`apps/whatsapp_bridge/models/unresolved_message.py`, migration `0022_unresolved_message.py`) — durable storage for a message with genuine content whose chat-level LID couldn't be resolved. Full content preserved (raw key, raw message, text, type, media metadata, direction, timestamp) — not just `msg.key` — so recovery never needs WhatsApp to resend anything.
- `_buildPayload`'s LID resolution (`session-manager.js`) is now an explicit 3-source chain: (1) live `senderPn`/`participantPn`, (2) in-memory `session.lidToPhone`, (3) **new** — a persisted single-LID lookup against Django (`GET /api/internal/whatsapp/lid-mapping/:account_id/`). Only if all three miss is the message preserved as unresolved (`POST /api/internal/whatsapp/unresolved-message/`) instead of dropped. This applies to the same code path that previously hard-dropped unresolved LID individual-chat messages regardless of direction — inbound-without-senderPn now also benefits, not just outbound.
- Automatic recovery: `IngestionService.recover_unresolved_for_lid()`, triggered from `internal_contacts_update` whenever a contact's `lid_jid` becomes known, reprocesses pending rows for that LID through the exact same `_upsert_contact`/`_upsert_chat`/`_insert_message` path normal ingestion uses. Idempotent on `(account, provider_message_id)` — a message that resolved on its own via a Baileys retry before recovery ran gets linked, not duplicated.
- Observability: `UnresolvedMessageViewSet` (read-only, `/api/unresolved-messages/`, `.../counts/`) and a new **Unresolved Messages** page in the frontend nav (Logs dropdown), mirroring the existing Stuck Receipts page.
- No hidden local-file fallback was added for the two new endpoints (deliberately, per the spec) — a Django persistence failure on either path produces an explicit `WorkerAlert(unresolved_message_failed)`, never a silent "probably fine."

**Tests:** `apps/whatsapp_bridge/tests.py` (17 Django tests: preservation idempotency, recovery + duplicate-safety, endpoint auth/validation, contacts-update recovery trigger) and `whatsapp-worker/test/session-manager.test.js` (11 tests via Node's built-in `node:test`, `npm test` in `whatsapp-worker/`: all three resolution sources, the preserve-on-miss path, lookup-failure and persistence-failure handling, history-sync preservation, and the pre-existing `_forwardMessage` build-error safety net). All 28 pass; full `python manage.py test` suite and `vite build` both clean.

**Not changed by this pass** — still exactly as designed below, not yet applied: Fix 1 (durable fallback recording for `sendContactsUpdate`/`sendGroupUpdate`/`sendGroupParticipantsUpdate`) and Fix 3 (the four silent-suppression findings). Fix 2's original Option A/B framing is superseded — see the note in that section. The inbound zero-trace mystery (Azan, Al Thamam occurrences #1-3) is untouched and still fully open.

---

## Problem statement

Some contacts' messages don't appear in ChatLens — both directions have been reported: messages received from a contact, and messages the user sends to a contact from their phone. Reported repeatedly since day one; this document addresses the mechanisms found to genuinely and silently cause this, out of a full audit of the worker's error handling, plus a follow-up audit specifically for fallback/suppression code that could mask this exact bug class.

Three distinct patterns were found. Two have designed fixes; the third (the still-open zero-trace mystery) does not.

## What was ruled out

The worker has a process-wide safety net (`process.on('uncaughtException'/'unhandledRejection', ...)`, `index.js:80-81`) that durably records *any* uncaught JS exception anywhere in the process, worker-wide, to `process-errors.ndjson` plus a `WorkerAlert(uncaught_exception)`. Checked both — **zero hits, ever**. So this is not "an unguarded throw silently killed a batch of messages" — every exception that has ever fully escaped our own try/catch coverage would have shown up here, and none have. The bug is narrower than that.

## Confirmed pattern 1 — outbound LID resolution has no fallback

**Where:** `_buildPayload`, `whatsapp-worker/src/session-manager.js:999-1009`

```js
if (isLidJid) {
  const rawLidJid = jidNormalizedUser(rawJid);
  if (!fromMe && senderPn) {
    // inbound: Baileys supplies senderPn — the real phone JID — directly, in real time.
    const phoneJid = jidNormalizedUser(senderPn);
    session.lidToPhone[rawLidJid] = phoneJid;
    resolvedChatJid = phoneJid;
  } else if (session.lidToPhone[rawLidJid]) {
    // outbound (or inbound with a stale/missing senderPn): only source is the cache.
    resolvedChatJid = session.lidToPhone[rawLidJid];
  } else {
    return _skip('unresolvable_lid');   // <-- dropped, no other source tried
  }
}
```

For contacts whose individual chat WhatsApp presents as a LID (not a plain phone JID), **inbound** messages self-heal the `lidToPhone` cache via `senderPn`, supplied live by Baileys on every inbound message. **Outbound** self-echoes (`fromMe: true`) never get a `senderPn` — WhatsApp doesn't include it for your own messages — so outbound resolution depends *entirely* on `session.lidToPhone` already having the entry from an earlier `contacts.set`/`contacts.upsert` event or a prior inbound message. When it doesn't, the message is dropped with reason `unresolvable_lid`, and the drop record only preserves `msg.key` — not `msg.message` — so the actual text is unrecoverable even from the admin Dropped Messages view.

### Evidence this is live, not theoretical

The `DEBUG_WATCH_JIDS` tap from `Silent Message Drop Investigation.md` (still active, targeting Al Thamam / `43190593786026@lid` / `971521962376`) has been capturing hits continuously since 2026-07-07, including as recently as **2026-07-20 17:51:51 UTC** (during this investigation). Cross-referencing its 299 captured events against `whatsapp_dropped_message`:

| | |
|---|---|
| Drops for this contact's LID | 11, spanning 2026-07-07 → 2026-07-20 (today) |
| Direction | **100% `from_me: True`** (outbound) |
| Reason | 9 of 11 `unresolvable_lid`, 2 `no_message_content` |
| Messages that *did* get through | 14 outbound + 12 inbound (so intermittent — a cache-miss window, not total failure) |

This exactly matches the shape of the bug above: only outbound is ever dropped for this contact, never inbound, and it's been recurring for two weeks.

### Two ways the cache goes cold

1. **After every worker restart/reconnect**, `session.lidToPhone` starts from whatever `getLidMappings(sessionId)` returns from Django's persisted `lid_jid` column (`session-manager.js:298-302`), not from a live re-fetch of WhatsApp's contact list. If Django never persisted that mapping (see Pattern 2 below), the cache is cold again on every single reconnect until a fresh inbound message or a new `contacts.set`/`upsert` batch repopulates it — and this worker reconnects roughly every 50 minutes on a bad day (see the handshake-timeout family of incidents), so this window recurs often.
2. **A LID contact WhatsApp never included a `.lid` field for at connect time** — `contacts.set` doesn't guarantee every contact's LID mapping is present in one shot. Until an inbound message arrives from that LID (supplying `senderPn`), any outbound message sent first has nothing to resolve against.

## Confirmed pattern 2 — three update paths fail with no durable trace at all

**Where:** `whatsapp-worker/src/django-client.js`

`sendDroppedMessage`, `sendWorkerAlert`, and `sendStuckReceipt` all call `_writeFallback()` on failure (`django-client.js:27-36`) — a durable local-file record (`failed-reports.ndjson`, confirmed non-empty: 22 entries) so a Django outage during exactly the moment something goes wrong isn't a second silent hole on top of the first.

Three other methods don't have this:

- `sendContactsUpdate` (`:138-152`)
- `sendGroupUpdate` (`:154-166`)
- `sendGroupParticipantsUpdate` (`:168-182`)

Each wraps its POST in try/catch, but the catch only does `this.logger.warn(...)` — no fallback file, no DroppedMessage, no WorkerAlert. If a `contacts.upsert` POST fails while it happens to be carrying a new LID→phone mapping, that mapping is lost **with only a line on the worker's own stdout**, which the worker's own code elsewhere already documents as "not captured anywhere persistent" (see the `DEBUG_WATCH_JIDS` comment block).

This directly feeds Pattern 1: a silently-lost `contacts.upsert` POST means Django's `lid_jid` for that contact never gets set, which means the *next* restart's `getLidMappings()` seed is cold for that contact, which reopens the outbound-drop window from Pattern 1 — indefinitely, until an inbound message happens to arrive first each time.

## Confirmed pattern 3 — fallback/suppression code that can mask this exact bug class

Follow-up audit specifically for fallback mechanisms anywhere in the message/contact/LID pipeline that catch a failure and quietly substitute a default or a no-op instead of surfacing it — since a swallowed failure in the *diagnostic* path looks identical to "the message never arrived" and would mislead any future investigation like this one. Four found, most direct first.

**3a. `whatsapp-worker/src/session-manager.js:786-800`, inside `_sendNamedContacts`** — the loop that populates `session.lidToPhone`, the exact cache Pattern 1 depends on:

```js
for (const c of contacts || []) {
  if (!c.id?.endsWith('@s.whatsapp.net')) continue;
  try {
    const phoneJid = jidNormalizedUser(c.id);
    if (c.lid) {
      const lidJid = jidNormalizedUser(c.lid);
      phoneToLid[phoneJid] = lidJid;
      if (sess) sess.lidToPhone[lidJid] = phoneJid;   // <-- the exact cache Pattern 1 depends on
    }
    ...
  } catch { /* skip malformed entry */ }   // <-- no log, no alert, nothing
}
```

If `jidNormalizedUser()` throws for any contact here, that contact's LID mapping silently never enters the cache — **zero trace anywhere, not even a log line**. The near-identical loop 25 lines below it (`:825-827`, the one that builds the Django-bound contact batch) catches the same failure class and does log a warning. This one doesn't. This is the single most on-point finding: a fallback that can silently reproduce the exact symptom under investigation, and would be undetectable even by someone reading the logs looking for it.

**3b. `whatsapp-worker/src/message-logger.js:20`, `write()`** — the append to `messages-N.ndjson`, the raw per-session capture log used throughout this whole investigation to tell "genuinely never arrived" apart from "arrived but something downstream ate it":

```js
write(sessionId, entry) {
  try {
    fs.appendFileSync(this._filePath(sessionId), JSON.stringify(entry) + '\n', 'utf8');
  } catch { /* swallow */ }
}
```

Deliberate — a log-write failure must not block ingestion — but it means a chronic failure here (disk full, permissions, bad path) has no signal anywhere. Every future "check the raw log" step would come back empty and could be misread as "never arrived" when it actually means "arrived and ingested fine, only our own diagnostic copy silently broke."

**3c. `whatsapp-worker/src/session-manager.js:117`, `_debugWatchLog()`** — same swallow-on-write pattern as 3b, but for the `DEBUG_WATCH_JIDS` tap specifically (the mechanism `Silent Message Drop Investigation.md` built to catch this exact bug class). If this write breaks, the one piece of instrumentation purpose-built for "vanishing contact" investigations goes dark with no indication.

**3d. `apps/whatsapp_bridge/views.py:201-207`, `internal_contacts_update`** — a contact whose `wa_contact_id` is a LID (should never happen per the strict LID rule, but this is the backstop for if it does) is silently `continue`'d out of the batch:

```python
if wa_contact_id.endswith('@lid'):
    logger.error('internal_contacts_update: rejected LID primary %s ...', wa_contact_id)
    continue
```

The endpoint still returns `{'status': 'ok', 'updated': N}` — an undifferentiated success. The worker has no way to know one specific contact's update was rejected, so it can't retry or alert on it. Same shape as the rest: a partial failure that looks, from the caller's side, identical to full success.

## What this does *not* explain

The complaint that prompted this audit (Azan / Action Link Trading, `971544732206@s.whatsapp.net`) resolves as a **plain phone JID**, not a LID — Pattern 1's code path isn't reached for it at all. That chat shows genuinely zero trace anywhere (DB, DroppedMessage, WorkerAlert, `baileys-internal.log`, the raw per-session capture log), matching the still-open mystery in `Silent Message Drop Investigation.md`. This document's fixes won't resolve that case. See that file's "Next steps" section — the live Baileys logger level (currently `warn`, `session-manager.js:134`) is the next diagnostic lever, since anything Baileys swallows internally below that level, or catches and doesn't log at all, is invisible to every layer we control.

---

## Proposed implementation

### Fix 1 — durable fallback recording for contacts/group update failures

Give `sendContactsUpdate`, `sendGroupUpdate`, and `sendGroupParticipantsUpdate` the same treatment as `sendDroppedMessage`/`sendWorkerAlert`/`sendStuckReceipt`:

```js
async sendContactsUpdate(sessionId, contacts) {
  if (!contacts.length) return;
  try {
    await this.http.post('/api/internal/whatsapp/contacts-update/', {
      worker_session_id: sessionId,
      contacts,
    });
    this.logger.info({ sessionId, count: contacts.length }, 'Contacts update sent to Django');
  } catch (err) {
    this.logger.warn({ sessionId, error: err.message }, 'Failed to send contacts update to Django — falling back to local file');
    this._writeFallback('contacts_update', { worker_session_id: sessionId, contacts });
  }
}
```

Same pattern for `sendGroupUpdate` and `sendGroupParticipantsUpdate`. This alone doesn't re-deliver the mapping to Django, but it makes the failure durable and inspectable instead of vanishing — closing the literal "silently failing without recording" gap — and gives us a concrete file to check the next time a LID mapping goes missing, instead of having no way to confirm whether this ever happened.

**Follow-up worth doing at the same time:** a small startup/periodic reconciliation job that replays `failed-reports.ndjson` entries of kind `contacts_update`/`group_update`/`group_participants_update` against Django once connectivity is confirmed healthy, so these aren't just recorded-and-forgotten. Scoping that as a fast-follow rather than bundling into the same change, since it needs its own retry/idempotency design (Django's `contacts-update` endpoint should already be safe to replay — it's an upsert — but this needs verifying before relying on it).

### Fix 2 — give outbound LID resolution a second source before dropping

**Implemented 2026-07-21 — superseding the original Option A/B framing below.** Rather than either original option, a third, simpler path was used: a narrowly-scoped Django lookup endpoint (`GET /api/internal/whatsapp/lid-mapping/:account_id/?lid_jid=...`, resolution source 3) queried on cache miss, backed by the same persisted `whatsapp_contact.lid_jid` that already exists for exactly this purpose. This avoids Option A's risk (undocumented, version-fragile Baileys internals) and Option B's complexity (in-memory hold/retry state and timers), and — combined with the new preserve-on-total-miss path (§3/§4 below) — means even a cache-miss-and-lookup-miss no longer loses the message; it's parked pending instead. See the P0 implementation summary at the top of this document.

The original two options are kept below for the record, in case source 3 ever proves insufficient (e.g. a persisted mapping that itself hasn't been learned yet — see "Two ways the cache goes cold" above, item 2):

**Option A (not pursued):** check whether Baileys' own socket exposes a live LID→phone lookup we can call synchronously when the cache misses — Baileys must already resolve this internally to have encrypted/decrypted the message in the first place, so the mapping likely exists somewhere in its own signal-repository/auth-state even when our own `contacts.set`-derived cache doesn't have it yet. Not pursued because it isn't part of Baileys' documented public API and could be version-fragile; the persisted-DB lookup achieves the same practical effect without that risk.

**Option B (not pursued):** on a cache miss for an outbound LID message, hold the message in-memory for a short window and re-attempt resolution if a `contacts.upsert` event or an inbound message from the same LID arrives in that window. Superseded by the unresolved-message preservation path, which achieves the same goal (don't lose the message on a transient miss) durably and without an in-memory timer/state machine — recovery can happen minutes or days later, not just within a short window.

### Fix 3 — stop swallowing cache-population and diagnostic-log failures silently

All four are small, mechanical, and low-risk — each just adds a log line or a differentiated response where one is currently missing; none change control flow.

- **3a** — add a `this.logger.warn({ sessionId, contactId: c.id, err: err.message }, 'Skipping malformed LID/username cache entry')` to the catch block at `session-manager.js:800`, matching the sibling loop's existing pattern at `:825-827`. Highest priority of the four — this is the one that can directly reproduce Pattern 1 with no trace at all.
- **3b** — add a rate-limited `this.logger.error(...)` (not per-line — would be log-spam under a sustained disk failure) to `MessageLogger.write()`'s catch, e.g. only log if the previous write also failed within the last N seconds, or track a consecutive-failure counter and alert once past a threshold.
- **3c** — same treatment for `_debugWatchLog()`'s file write.
- **3d** — change `internal_contacts_update`'s response to include a `rejected: [...]` list (contact id + reason) alongside `updated`, and have the worker's `sendContactsUpdate` log a warning (and ideally a `WorkerAlert`) if `rejected.length > 0` in the response.

### Explicitly not proposed here

- No change to the `unresolvable_lid` strict-drop policy itself for cases where resolution genuinely never becomes possible — creating a LID-keyed contact instead remains the wrong tradeoff (see `ChatLens Development Document.md` §13).
- No attempt to fix the Azan-class zero-trace case in this document — that needs the Baileys-logger-level diagnostic from `Silent Message Drop Investigation.md` run first; there's nothing to implement yet because the mechanism isn't identified.

## Rollout notes

Fix 2 (as actually implemented, see summary at top) and the new message-preservation mechanism are live: `whatsapp-worker/src/session-manager.js`, `whatsapp-worker/src/django-client.js`, `apps/whatsapp_bridge/models/unresolved_message.py` + migration `0022_unresolved_message.py`, `apps/whatsapp_bridge/services/ingestion_service.py`, `apps/whatsapp_bridge/views.py`/`urls.py`, `apps/api/serializers.py`/`views.py`/`urls.py`, and the frontend (`api/index.js`, `router/index.ts`, `views/UnresolvedMessagesView.vue`, `App.vue` nav).

Fix 1 and Fix 3 remain worker-side (Fix 3d also touches the same Django view), additive, low-risk, and **still not implemented** — per explicit instruction, held for thorough review before any further changes.

## Cleanup checklist

- [x] Implement message preservation (`WhatsAppUnresolvedMessage` + endpoints + recovery) — 2026-07-21
- [x] Implement Fix 2 via persisted-LID lookup (resolution source 3) — 2026-07-21
- [x] Tests: Django (`apps/whatsapp_bridge/tests.py`) + worker (`whatsapp-worker/test/session-manager.test.js`) — 2026-07-21, all passing
- [x] Observability: `/unresolved-messages` API + frontend page — 2026-07-21
- [ ] Thoroughly examine Fix 1 and Fix 3 before applying (separate, still-pending request)
- [ ] Implement Fix 1 (`_writeFallback` for `sendContactsUpdate`/`sendGroupUpdate`/`sendGroupParticipantsUpdate`)
- [ ] Implement Fix 3a-3d (suppression logging / differentiated response)
- [ ] Watch `WhatsAppUnresolvedMessage` / `debug-watch.ndjson` for the Al Thamam LID over the next few restart cycles to confirm rows now get created (and recovered) instead of only ever showing up as `unresolvable_lid` drops
- [x] Fold the shipped LID-resolution behavior into `ChatLens Development Document.md` §9/§13 — done 2026-07-21, see §6.7.3 (new), §20 Phase 22, and the updated §9/§10/§13/§16 notes
- [ ] Update `Silent Message Drop Investigation.md` if/when Fix 1 or Fix 3 land, or if the Al Thamam LID stops producing `unresolvable_lid` drops entirely — its own inbound zero-trace mystery remains open regardless
