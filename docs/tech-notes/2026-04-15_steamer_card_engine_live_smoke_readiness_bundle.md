# 2026-04-15 — steamer-card-engine live smoke readiness bundle

## Why this slice landed

The repo already had seed operator posture controls, but the operator still had to manually stitch together the bounded live-capability sequence.
That left too much room for fake progress and uneven smoke discipline.

This slice adds one truthful command that runs the whole bounded smoke sequence and emits a pass/fail bundle.

## What is now executable

- `steamer-card-engine operator live-smoke-readiness --deck ... --auth-profile ... [--json]`

The command runs these steps in order:
1. confirm baseline disarmed posture
2. prove explicit refusal while disarmed
3. arm bounded live posture with TTL
4. prove smoke acceptance while armed
5. flatten and close the armed window
6. confirm final disarmed posture again

## Output / receipts

The command returns:
- top-level `ok` + `smoke_status`
- explicit `activation=prepared-only`
- per-step payloads and pass/fail results
- collected receipt paths from the refusal / arm / acceptance / flatten steps

## Boundary statement

- still **not** broker-connected
- still **not** live activation
- still a bounded smoke/control surface
- useful because it proves the operator-control contract as a repeatable bundle instead of an ad-hoc manual ritual

## Follow-up hardening

After final review, the smoke sequence was hardened so that any mid-sequence failure after `arm-live` now forces cleanup disarm before returning failure. A focused regression test proves the state file does not leak `armed_live=true` on abort.

## Topology statement

- Runtime topology changed: no
- Scheduler topology changed: no
- CLI/operator smoke surface changed: yes
