# 2026-04-16 — steamer-card-engine preflight test scheduler lane

## Verdict

Before real probe wiring exists, the correct scheduler-opening move is not to enable the real preflight sentinel.
It is to open a separate fixture-backed test lane that proves scheduler wiring without pretending production readiness.

## What changed

Added a fixture-backed wrapper:
- `tools/steamer_card_engine_trading_day_preflight_test_cron.py`

It delegates to the canonical preflight cron wrapper while forcing the example connected probe fixture path.

Provisioned one bounded OpenClaw scheduler row:
- job id: `37d89e3b-4dab-4bbb-ba38-b9f7719e9ff8`
- name: `steamer: card-engine trading-day preflight TEST oneshot`
- target: isolated `steamer-cron`
- posture: enabled one-shot with `deleteAfterRun=true`

## Why this is the truthful move

- The real sentinel should stay disabled until a real probe source exists.
- Scheduler plumbing still deserves an end-to-end green-path test.
- A fixture-backed one-shot lane proves the scheduler path without lying about broker/session readiness.

## Validation receipts

- `python3 tools/steamer_card_engine_trading_day_preflight_test_cron.py` -> `NO_REPLY`
- `uv run pytest -q tests/test_cli.py` -> `23 passed`
- manual cron debug run for job `37d89e3b-4dab-4bbb-ba38-b9f7719e9ff8` finished `ok`

## Remaining hard gate

Still unchanged:
- real broker/session probe wiring is required before enabling the real preflight sentinel row `26d37fdc-5475-4a50-9d10-4cecb970f230`

## Topology statement

- Runtime topology changed: no
- Scheduler topology changed: yes, one temporary enabled test row added
- Live authority changed: no
