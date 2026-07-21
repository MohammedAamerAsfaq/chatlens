# Silent Message Drop Investigation

> **Status:** 🔴 Open — root cause narrowed as of 2026-07-21 to a WhatsApp-server-side per-device delivery gap (confirmed: the phone receives these messages, ChatLens's linked device does not). Not fixable from this codebase as currently understood. See "Update — 2026-07-21" below.
> **Started:** 2026-07-06
> **Scope:** Track this one specific bug (messages from a contact vanishing with zero trace in any log) until root-caused and fixed. Delete this file once resolved — it's a working log, not permanent architecture documentation (see `ChatLens Development Document.md` for that).

## Update — 2026-07-21

A third, independent occurrence of this exact failure shape — different contact, but now a confirmed *repeat* for that contact specifically (see below) — plus the one diagnostic this doc had been waiting on.

**Contact:** Action Link Trading Llc, `971544732206@s.whatsapp.net`, LID `16011805913098@lid`, contact id 8583, account 8 ("Aamer Ashfaq") — the same "Azan" contact from the Eighth-incident outbound `unresolvable_lid` pattern, but this occurrence is a *different* failure mode (inbound-shaped zero-trace, matching this doc's original mystery, not the now-fixed outbound LID gap).

Reported live: a message the user could see on their own phone was missing from ChatLens roughly 2 minutes after it arrived. Checked immediately, in the same session:
- **DB (`whatsapp_message`):** nothing for this contact since 15:45:41 UTC — over 30 minutes before the report.
- **Raw per-session capture log:** same — nothing since 15:45:41, while the same file was actively writing other contacts' messages up to seconds before the check.
- **`whatsapp_dropped_message`, `WorkerAlert`:** zero rows for this contact/account in the prior 10 minutes.
- **Baileys' internal decrypt-failure log:** no new entry — its most recent hit for this contact just matches the already-captured 15:45:41 message (a harmless duplicate-decrypt, same pattern documented in the Eighth incident).
- **Account health:** fully connected and actively ingesting — 47 messages across other chats in the same ~17-minute window, most recent literally seconds old. Not an account-wide or worker-health issue; specific to this one contact's chat.

**The load-bearing new fact:** asked the user to check whether the message was visible on the phone itself. **Confirmed yes** — the phone received it normally; only ChatLens's linked-device session did not. This is exactly the test this document's "Next steps" section (below) said would settle the question, and it comes back in favor of the theory already written there: WhatsApp's multi-device architecture delivers to each linked device (phone, personal Web, ChatLens's own linked device) independently, and this is an occasional gap in that per-device fan-out specifically for ChatLens's device — not a decrypt failure (would leave a trace), not a drop (would leave a trace), not an account-wide problem (everything else flows), and now confirmed not "the message never reached the account at all" either (the phone got it fine).

**Pattern confirmation:** this makes the third distinct day (2026-07-18, 2026-07-20, 2026-07-21) this specific contact has silently dropped messages while nothing else on the account is affected — always the same contact family (Action Link Trading / Azan), never a one-off. Per this document's own "if a real pattern is found" criterion (see below), that threshold is now met. No mitigation is designed yet — see "Open decision" below.

### Open decision

With the phone-side confirmation, continued code-level instrumentation (more logging, more taps) has nothing left to catch — nothing arrives at any layer this codebase can observe. Two directions from here, neither implemented:
1. **Accept as a known WhatsApp-multi-device limitation** for this contact and watch for whether it spreads to others (would suggest something linked-device-specific and possibly addressable — e.g. a stale device registration) vs. stays isolated to this one contact (would suggest something specific to their client/network, out of ChatLens's control entirely).
2. **Design a reconciliation mitigation** — periodically compare ChatLens's view of a chat against a second independent source (there isn't currently a second source available; WhatsApp doesn't expose a "fetch missed messages" API to Baileys) to detect and backfill gaps after the fact, rather than relying solely on live delivery. Not designed — would need research into whether Baileys/WhatsApp exposes anything usable for this at all before it's even feasible.

## Update — 2026-07-20

The instrumentation below (`DEBUG_WATCH_JIDS` tap, `debug-watch.ndjson`) has **not been empty since occurrence #3** — as of this update it holds 299 captured events, most recently 17:51:51 UTC on 2026-07-20. Cross-referencing those hits against `whatsapp_dropped_message` found a **different, real, currently-reproducing bug** for this same contact: 11 `unresolvable_lid` drops (2026-07-07 → 2026-07-20), 100% on outbound (`fromMe: true`) self-echoes. Root cause, proposed fix, and full evidence are in `docs/Contact Message Loss — LID Resolution Fix Proposal.md` (not yet implemented).

**This does not resolve occurrences #1-3 below.** Those were reported as *inbound* messages with zero trace at any layer, and the outbound LID-resolution mechanism found on 2026-07-20 doesn't touch the inbound path at all (inbound resolves live via `senderPn`, which is exactly why it never shows the same failure). The inbound mystery remains fully open. Also relevant: the same "vanishes both ways, zero trace" complaint recurred for a *different* contact (Azan / Action Link Trading) on 2026-07-20 — see `ChatLens Development Document.md` §17.2 "Sixth incident" and "Eighth incident" — reinforcing that this is a recurring, not one-off, class of problem.

---

## Problem

Messages from contact **971521962376** ("Al Thamam Ipad Almurar") are visible in WhatsApp Web but never appear in ChatLens — not as an ingested message, not as a dropped-message record, not anywhere. Reported as direct messages (1:1 chat), not group messages. "Advanced Chat Privacy" for this chat is confirmed **off**, so that's not the cause.

This is distinct from the normal drop-and-log behavior (`whatsapp_dropped_message`, see Development Document §9) — those cases always leave a DB row with a reason. This contact's messages leave **nothing**, at any layer.

## Contact details

| Field | Value |
|---|---|
| Phone | `971521962376` |
| WhatsApp contact row | `id=6275`, account_id=8 ("Aamer Ashfaq") |
| LID | `43190593786026@lid` |
| Display/push name | Al Thamam Ipad Almurar |
| Group memberships (per our DB) | 10 groups total — 6 under account 8, 4 under account 9 ("Expert Devices"): Gizmo tech al murar deira, AVO PURCHASE/SALE, (WTB). APPLE BBC PHONES, WTB/WTS +971506623260 |
| Live verification | Confirmed via a direct call to the worker's live group-metadata endpoint (`GET /sessions/9/groups/120363425330019689@g.us`) that this contact is a **current active participant** (out of 301 members) in "AVO PURCHASE/SALE" under the Expert Devices account — so the account genuinely shares context with this person, this isn't a wrong-account mix-up |

## Timeline of occurrences

| # | Time reported | Account | Message text | Result |
|---|---|---|---|---|
| 1 | 2026-07-06 ~20:48 AST | Expert Devices | "Wtb\n15 128 tra\nBlk\n\n16 256 tra\nBlk" | Not found anywhere in DB (any account), no drop record |
| 2 | 2026-07-06 ~20:59 AST | Expert Devices | "Wtb\n17 air 512 Arabic 🇦🇪\nBlue" | Not found anywhere in DB (any account), no drop record; confirmed via user this was a **direct message**, not a group post |
| 3 | 2026-07-06 ~21:51 AST | Expert Devices | "Wtb\n17 pro max 256 hk non🇭🇰\nSilver" | Not found anywhere in DB, no drop record, **and** neither `debug-watch.ndjson` nor `baileys-internal.log` gained any new entries — both taps were confirmed active (both accounts had reconnected at ~21:49 AST, ~2 min before this message) |

Exact message text for both was searched across **both** accounts' entire message history (`message_text__icontains`) — zero matches anywhere, under any identity. Not a matter of "wrong account filter" — the content never landed in the database at all.

## What's been ruled out

- **`unresolvable_lid`** — this contact's LID is already resolved/cached (contact row exists with `lid_jid` set); zero drop rows anywhere reference this LID or phone number, ever, across the whole table.
- **`no_message_content` / `forward_failed` / `build_error` / `protocolMessage` / `senderKeyDistributionMessage`** — checked every recent row in each category, none reference this contact.
- **Unhandled `messages.upsert` type** — found a genuine code gap (silent `debug`-level return for any `type` other than `notify`/`append`/`prepend`, invisible under `LOG_LEVEL=info`). Fixed to report as `unhandled_type:<type>` (see Fix Log below). Restarted, waited, zero `unhandled_type:*` rows appeared for either occurrence — ruled out.
- **Account-wide connectivity/sync issue** — both accounts are actively and correctly ingesting dozens to 100+ messages/hour from other senders throughout the investigation window, including in groups this same contact belongs to.
- **Wrong WhatsApp account entirely** — live group-metadata check confirms Expert Devices genuinely shares a group with this contact; this isn't a case of checking a WhatsApp Web session unrelated to the monitored numbers.

## Instrumentation currently deployed

Both require a worker restart to pick up (auth persists to disk, so reconnection is automatic — brief live disconnect only).

1. **`whatsapp-worker/src/session-manager.js`** — `DEBUG_WATCH_JIDS` / `_isDebugWatchTarget()` / `_debugWatchLog()` (search for `TEMPORARY` comments to find all of it). Runs at the very top of both `messages.upsert` and `messaging-history.set`, before any filtering, matching this contact's LID, phone JID, participant fields, or a push-name hint (`"thamam"`) — catches the event no matter what happens to it afterward, including an unrecognized shape or a rotated/unknown LID (as long as the group is a match or the name hint fires).
   - Writes to **`whatsapp-worker/message-logs/debug-watch.ndjson`** (durable file — the worker's console/pino output is not captured anywhere persistent, so this had to be file-based, not just logged).
   - Status as of occurrence #3: **file still does not exist** — the tap has not fired for any of the three reported occurrences, despite being confirmed active (worker reconnected ~2 min before occurrence #3).
   - **Superseded — see "Update — 2026-07-20" above.** The file now exists and holds 299 entries accumulated since. None of them are occurrences #1-3 (still zero matches for those specific reports), but the tap firing at all for *other* traffic from this contact is what surfaced the separate outbound `unresolvable_lid` pattern documented there.

2. **Baileys' own internal logger** — was `pino({ level: 'silent' })`, meaning any error Baileys hits *internally* while decoding/decrypting a message (i.e. before it ever gets far enough to emit `messages.upsert`) was completely invisible to us. Our own debug tap (#1) only sees messages Baileys has already successfully turned into a `WAMessage` object — if Baileys fails earlier than that, tap #1 can't see it either.
   - Changed to `pino({ level: 'warn' }, pino.destination(...))`, writing to **`whatsapp-worker/message-logs/baileys-internal.log`**.
   - Status as of occurrence #3: file exists but only contains two `"Timed Out" / "unexpected error in 'init queries'"` entries from the reconnect handshake itself (a generic Baileys startup-props fetch timeout, unrelated to any specific message) — **no new entry appeared for occurrence #3**.

## Possible lead: near-duplicate message from a different number

While searching for occurrence #3's exact text, found a **very similar** (not identical) message from a **different sender entirely**:

> `971502196592` (not `971521962376`) posted at **2026-07-06 15:39:46 UTC / 19:39 AST** (not ~21:51 AST) in a group under account 8:
> `"Wtb\n17 pro max 256 hk🇭🇰 non \n\nSilver  3 \n\n17 pro max 1 tb hk"`

Wording order differs slightly from what was reported for occurrence #3 ("256 hk🇭🇰 non" vs "256 hk non🇭🇰"), and the phone number is different — most likely two different resellers independently copy-pasting the same template stock list (extremely common in these wholesale groups), not the same message. But worth a sanity check: **please confirm the exact phone number WhatsApp shows for this contact's DM** next time, in case there's a mix-up between this contact and a similarly-numbered one, or in case they're messaging from more than one number.

## How to check for the next occurrence

```bash
cd whatsapp-worker
cat message-logs/debug-watch.ndjson       # our own tap — should show the raw msg if it reaches messages.upsert/messaging-history.set at all
cat message-logs/baileys-internal.log     # Baileys' own warnings/errors — should show if Baileys itself is failing before that point
```

Also re-run the DB checks (contact/message/dropped-message search by phone `971521962376` and LID `43190593786026`) in case it ingested successfully this time.

## Next steps if both logs are still empty

If a third occurrence produces nothing in either file, the failure is happening somewhere WhatsApp's own multi-device delivery never reaches this companion device for this specific sender at all — a layer neither our code nor Baileys' own logging can see. At that point the productive move shifts from code instrumentation to comparing WhatsApp's own "linked devices" behavior (e.g., does the primary phone itself show this message reaching all linked devices, or does even the phone miss it) rather than further ChatLens-side changes.

## Cleanup checklist (once root-caused)

- [ ] Revert Baileys internal logger back to `pino({ level: 'silent' })` in `session-manager.js`
- [ ] Remove `DEBUG_WATCH_JIDS`, `_isDebugWatchTarget()`, `_debugWatchLog()`, and both call sites (search `TEMPORARY`)
- [ ] Decide whether to keep the `unhandled_type:<type>` reporting fix permanently (recommended — it's a genuine improvement, not just debug scaffolding) or fold it into the Development Document's Drop Reasons table (§9) instead
- [ ] Delete or archive this file
