# WhatsApp Worker Session Reliability Notes

## 2026-07-31 - Restored Session Pre-QR Misclassification Fix

### Problem

Authenticated WhatsApp sessions restored from disk could be incorrectly marked as pre-QR failures after a Baileys stream error.

Observed worker log pattern:

```text
Stream Errored (ack)
code=500
Pre-QR connection closed - not reconnecting automatically
```

This was wrong for already-linked accounts because the current worker process may not have generated the original QR, so `qrEverGenerated=false` does not mean the session has no credentials.

### Root Cause

The worker used this condition to identify a pre-QR close:

```js
if (!loggedOut && !session.qrEverGenerated) {
  // mark error and prevent reconnect
}
```

For restored sessions, `qrEverGenerated` is often false even though `sessions/<id>/creds.json` exists and the session is authenticated. A normal authenticated stream error was therefore treated as a QR-generation failure.

### Fix

The worker now tracks whether the session has credentials:

```js
hasCredentials: fs.existsSync(credsFile)
```

`hasCredentials` is also set to `true` after:

- `creds.update`
- successful `connection.update` with `connection === 'open'`

The pre-QR failure branch is now restricted to sessions with no credentials:

```js
if (!loggedOut && !session.qrEverGenerated && !session.hasCredentials) {
  // true pre-QR failure
}
```

### Expected Behavior

- Fresh sessions that fail before QR/credentials still become `error`.
- Restored authenticated sessions that hit `Stream Errored (ack)` are allowed to follow normal reconnect behavior.
- The worker should not suppress reconnect for an authenticated account solely because this process did not generate the original QR.

## 2026-08-03 - Baileys Event Log and Dropped Message UI Cleanup

### Baileys Event Index Stability

The `BaileysEvent` model indexes now use explicit index names. This prevents Django from generating unnecessary index rename migrations when the model is inspected on different environments.

The change is schema-definition hygiene only. It does not alter event persistence behavior, event payloads, API responses, or the worker-to-Django event flow.

### Dropped Messages Vue Warning

The Dropped Messages page rendered the main page wrapper and a sibling `Teleport`, which made the component root a fragment. Because `RouterView` passes `class="h-full"` to route components, Vue logged this warning:

```text
Extraneous non-props attributes (class) were passed to component but could not be automatically inherited
```

The clear-confirm `Teleport` remains functionally unchanged, but it is now placed inside the page wrapper so `DroppedMessagesView` has one root node. This removes the warning without changing the log page behavior.
