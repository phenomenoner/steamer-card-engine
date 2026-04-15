# 2026-04-16 — steamer-card-engine trading-day preflight seed runner

## Why this slice landed

`operator probe-session` made the canonical snapshot available, but a future cron still needed to know how to chain probe generation into preflight.
A formal repo-side runner is the smallest truthful bridge.

## What is now executable

`ops/scripts/trading_day_preflight_seed.sh`

It performs:
1. `operator probe-session --output <state-root>/session_probe.json`
2. `operator preflight-smoke --probe-json <state-root>/session_probe.json`

## Why this matters

This gives a future trading-day cron one stable repo entrypoint instead of reconstructing command chains in scheduler config.
It also keeps the source boundary clean:
- probe generation
- probe snapshot persistence
- preflight verdict

## Boundary

- still seed-only
- no actual cron activation in this slice
- no vendor SDK attach or broker session login in the runner

## Default state root

The runner defaults to:
- `/root/.openclaw/workspace/.state/steamer-card-engine`

Override with:
- `STEAMER_CARD_ENGINE_STATE_ROOT=/custom/path`

## Topology statement

- Runtime topology changed: no
- Scheduler topology changed: no
- Repo-side execution surface changed: yes
