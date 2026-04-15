# 2026-04-16 — steamer-card-engine operator probe-session seed

## Why this slice landed

`--probe-json` created an external inlet, but there was still no first-class command for cron or operators to generate the canonical session-health snapshot.
That left the chain one step short of a formal probe lane.

## What is now executable

- `operator probe-session --auth-profile ... --trading-day-status ... --json`
- `operator probe-session --auth-profile ... --trading-day-status ... --output .state/session_probe.json --json`

The command emits the same canonical snapshot shape that `auth inspect-session --probe-json ...` and `operator preflight-smoke --probe-json ...` can consume.

## Why this matters

This makes the preflight lane composable:

1. `operator probe-session` generates or relays the canonical health snapshot
2. downstream preflight consumes that snapshot
3. a future cron can wire the two together without changing the contract again

## Boundary

- still seed/prepared-only
- still no vendor SDK attach inside the command
- external probe JSON can be passed through unchanged on the canonical surface

## Topology statement

- Runtime topology changed: no
- Scheduler topology changed: no
- Operator control surface changed: yes
