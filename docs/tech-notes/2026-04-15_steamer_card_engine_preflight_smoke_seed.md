# 2026-04-15 — steamer-card-engine preflight smoke seed

## Why this slice landed

`live-smoke-readiness` proves the bounded operator-control sequence, but it is not the same thing as broker-preflight readiness.
The product needed one explicit gate that says whether the next broker-preflight step is actually ready, or still blocked.

## What is now executable

- `steamer-card-engine operator preflight-smoke --deck ... --auth-profile ... --trading-day-status open|closed|unknown [--json]`

This command does **not** attach a real broker or market-data session.
Instead, it combines:
- logical session capability posture from `auth inspect-session`
- current operator baseline posture from `operator status`
- trading-day gate input

and returns a truthful `ready` vs `blocked` verdict.

## Current expected truth

In the current seed runtime, `preflight-smoke` should usually report `blocked`, because:
- `marketdata_connection=not-connected`
- `broker_connection=not-connected`

That is the correct behavior.
Blocking honestly is better than pretending the repo has crossed into broker-connected readiness.

## Why this matters

This gives the future trading-day cron a real, stable entrypoint:
1. run `preflight-smoke`
2. inspect blockers
3. stop if still seed-blocked
4. only continue when a later broker-connected slice replaces the health fields truthfully

## Topology statement

- Runtime topology changed: no
- Scheduler topology changed: no
- CLI/operator preflight surface changed: yes
