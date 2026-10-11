# Behavior and timing

| State | Entry / behavior | Exit |
|---|---|---|
| IDLE | Local camera only; eyes rest downward | One target detected for 300 ms |
| WATCHING | Shared eyes follow target, no remote audio | Facing qualifies or visitor disappears |
| STALKING | Facing timer; yaw ≤25°, pitch ≤20° relative to calibration | 3 s facing → AWAKENING; looking away → WATCHING |
| AWAKENING | Exactly one authorized conversation worker | Metadata + audio ready → CONVERSING; failure/timeout → ENDING |
| CONVERSING | Microphone streaming, playback jaw envelope, independent eyes | idle, absence, goodbye, maximum, manual end, error |
| ENDING | Stop audio and connection, clear jaw, neutral motion | Worker reports closed → COOLDOWN |
| COOLDOWN | No autonomous repeat activation | Entire zone empty 5 s, or manual reset |

All application timers use monotonic seconds. Tests pass explicit fake times.
A ≤250 ms detection dropout preserves qualification; it counts toward the hold only
when detection subsequently returns. A longer dropout resets the hold. A visible
look-away always resets it. Switching geometric targets resets detection and facing
qualification. WATCHING may transition immediately into STALKING in the same tick
if orientation is already valid. This is pose approximation, not eye-gaze estimation.

Idle is 30 seconds since meaningful activity: visitor speech start/end, agent audio,
agent response, playback speech start/end. It does not expire while either party is
marked speaking. Microphone RMS is a conservative activity heuristic, not a semantic
voice detector; background noise and feedback may extend a session. The 180 second
hard maximum still bounds it. Original-target absence for 10 seconds ends a session,
even during speech. Camera stopped/unavailable counts as absence.

Maximum duration, absence, manual stop and shutdown currently cancel queued output
immediately; graceful final-response draining is not implemented. Whole-utterance
'goodbye', 'bye', 'end conversation' and 'stop talking' are recognized from final
user transcript events. Broader intent is deliberately left to future agent tooling.

Connection establishment has a 20 second authorization deadline, 10 second request/
connect timeout, and at most 3 pre-connection retries with 1/2 second backoff. Missing
configuration, invalid audio format, authentication failures and rate limiting are
not retried. After a session is connected, disconnect leads to cooldown; no automatic
new paid session is opened. Manual start may override cooldown but never duplicates
an active/ending session. Emergency Stop requires explicit Resume and autonomous enable.

Visitor identity is never inferred or stored. A newly arriving visitor while someone
remains in cooldown does not rearm automatically. Leave the zone empty for 5 seconds,
or use Reset cooldown to permit another activation intentionally.
