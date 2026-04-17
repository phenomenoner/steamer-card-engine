# 2026-04-17 — steamer-card-engine minimal real-money smoke packet

## Status
- plan-only
- unexecuted
- topology: unchanged

## Whole-picture promise
Close the final production-facing gate that non-cash proof cannot close:
prove one bounded real broker submission path can enter the market, emit truthful lifecycle/fill receipts, and return to flat without expanding authority beyond the smallest necessary smoke window.

## Hard boundary
- this packet does **not** authorize execution by itself
- one symbol only
- one bounded live window only
- one bounded operator-armed posture only
- flatten-first if behavior diverges from the planned path
- success here upgrades proof quality, not risk appetite

## Preconditions
All must be true before execution:
1. `tests/test_dashboard.py` green for current runtime truth
2. non-cash compare surface receipt exists and is acknowledged as still non-entry-bearing
3. non-cash path-traversal receipt exists and is green
4. `operator preflight-smoke` reports `ready` against fresh `steamer-cron-health`
5. `operator live-smoke-readiness` remains pass on the same truthful probe surface
6. operator agrees the selected account/instrument is the smallest acceptable real-money exposure lane
7. explicit human go for this packet on the intended trading day

## Recommended bounded shape
- instrument: one highly liquid TWSE name already acceptable to the operator lane
- quantity: decide and record the exact broker-supported / policy-supported minimum before arming, do not improvise live
- side: decide and record the exact side before arming, prefer the side with the clearest immediate flatten path under current posture
- window: continuous session only, not pre-open, not opening-auction, not into the close; prefer a calm mid-morning window
- posture TTL: shortest practical TTL that still covers submit -> observe -> flatten
- probe freshness: all probe/preflight receipts must be captured within 5 minutes before arming
- wall-clock abort: define a hard abort timestamp for the attempt independent of TTL; if lifecycle evidence is incomplete by then, flatten / disarm / stop

## Execution sequence
1. record the exact instrument / quantity / side / abort timestamp in the operator note before arming
2. capture fresh `auth inspect-session --json`
3. capture fresh `operator probe-session --json`
4. capture fresh `operator preflight-smoke --json`
5. capture pre-smoke account / open-position baseline
6. arm bounded live posture with explicit TTL
7. submit one minimal real-money smoke order
8. capture broker acknowledgement / order-id / lifecycle events
9. capture fill, partial-fill, or explicit no-fill terminal state
10. flatten back to flat using the bounded operator path
11. confirm final disarmed posture and flat state
12. write the smoke receipt bundle before calling the gate closed

## Required receipts
- session inspection JSON
- probe-session JSON
- preflight-smoke JSON
- pre-smoke account / open-position baseline
- operator arm receipt
- broker submission receipt with stable order identifier
- lifecycle trail covering submit / ack / working / cancel-or-fill / flatten
- fill receipt, partial-fill receipt, or explicit no-fill terminal receipt
- final flat-state receipt
- final disarm receipt
- one compact operator summary with timestamps and outcome

## Success criteria
A truthful PASS requires all of these:
- real broker submission happened
- the order can be traced through a real lifecycle surface
- final posture returns to disarmed
- final position returns to flat
- receipts are complete enough that a third party can reconstruct what happened

## Failure criteria
Any of these is a FAIL or ABORT:
- submission never leaves the seed/stub surface
- lifecycle cannot be traced with stable identifiers
- posture remains armed after the attempt
- flatten path is ambiguous or incomplete
- flat-state cannot be proven

## Operator callouts
- do not mix strategy validation with this smoke; this is execution-path proof first
- if the order does not fill cleanly, preserve the no-fill truth instead of forcing narrative closure
- if the order partially fills, record the partial-fill branch explicitly and treat completion quality conservatively
- if the path needs broker-interface code changes, stop and reopen as engineering work rather than improvising live

## Closure statement
Until this packet is executed successfully, `steamer-card-engine` should still be described as:
- prepared-only with strong non-cash proof
- not yet production live-ready
