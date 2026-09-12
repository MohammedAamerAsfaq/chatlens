# V2 Performance Baseline

Captured: 2026-09-10 18:12 Asia/Dubai (14:12 UTC)

Use this as the comparison point for the next V2 performance review. Query only
logs created after 2026-09-10 14:12 UTC so this incident window is not mixed
with the next sample.

## Previous 60 Minutes

- Total logs: 147
- Complete: 135 (91.8%)
- Error: 4 (2.7%)
- Non-terminal: 8
- Average pass 1 AI: 23.8 seconds
- Average candidate search: 42 milliseconds
- Average pass 2 AI: 16.4 seconds
- Average total: 36.4 seconds
- Slowest completed total: 182.6 seconds

## Recent 12 Minutes

- Total logs: 105
- Complete: 98
- Pass 1 done: 6
- Pass 2 started: 1
- Average pass 1 AI: 23.0 seconds
- Average pass 2 AI: 18.5 seconds
- Average total: 37.0 seconds
- Maximum total: 182.6 seconds

## Incident Context

- Four errors occurred around 17:37-17:40 Dubai time: two 180-second V2 AI
  timeouts, one PostgreSQL "too many clients" error, and one shutdown error.
- Seven recent logs were stranded at `pass1_done` after the old worker process
  was stopped. Their raw pass 2 background thread never began or completed.
- Recent stranded message IDs: 156047, 156085, 156093, 156094, 156165, 156168,
  and 156169.
- Pass 2 is not yet a durable queue task. The next engineering task is to make
  pass 2 durable and recover stale `pass1_done` records.
