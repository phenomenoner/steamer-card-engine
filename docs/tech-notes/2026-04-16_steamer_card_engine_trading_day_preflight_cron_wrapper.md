# 2026-04-16 — steamer-card-engine trading-day preflight cron wrapper

## Why this slice landed

A scheduler job should not emit raw JSON on every green run.
The repo already had the probe/preflight chain, but it still needed a cron-safe wrapper with explicit green/red output rules.

## What is now executable

- `python3 tools/steamer_card_engine_trading_day_preflight_cron.py`

Behavior:
- green path: prints `NO_REPLY`
- red path: prints one concise `BLOCKED ...` line with gate/probe/blocker summary
- execution failure: prints one concise `BLOCKED ... exitCode=...` line

## Why this matters

This is the scheduler-facing surface that can be bound safely:
- no noisy JSON on success
- red path remains explicit
- downstream scheduler delivery/failure-alert policy can stay thin

## Boundary

- still no broker/session attach in the wrapper itself
- if no real probe source is provided, the line will truthfully remain blocked
- that means first scheduler provisioning should be staged/disabled until a real probe source exists

## Topology statement

- Runtime topology changed: no
- Scheduler topology changed: not yet
- Repo-side scheduler interface changed: yes
