# 2026-04-16 — steamer-card-engine trading-day preflight scheduler enablement

## Verdict

The real preflight sentinel is no longer supposed to stay disabled.
The truthful upstream source now exists, the wrapper resolves it by default, and the staged row has been promoted to live scheduling.

## What changed

Enabled existing OpenClaw cron row:
- job id: `26d37fdc-5475-4a50-9d10-4cecb970f230`
- name: `steamer: card-engine trading-day preflight sentinel (08:55)`

Also updated the row description so it no longer claims the source is still missing.

Repo-side wrapper behavior now defaults to:
- `STEAMER_CARD_ENGINE_PROBE_SOURCE=steamer-cron-health`

That means the scheduler continues to run the same single wrapper entrypoint:
- `python3 /root/.openclaw/workspace/steamer-card-engine/tools/steamer_card_engine_trading_day_preflight_cron.py`

## Validation

- `python3 tools/steamer_card_engine_trading_day_preflight_cron.py` -> `NO_REPLY`
- forced cron run for `26d37fdc-5475-4a50-9d10-4cecb970f230` finished `ok`
- next scheduled run remains `08:55 Asia/Taipei`

## Why this is now truthful

Before this slice, the row could only consume seed or fixture truth, so live enablement would have been fake readiness.
After the `steamer-cron-health` bridge landed, the same row now consumes a real upstream readiness signal without changing the cron command contract.

## Boundary

- still prepared-only
- still no live trading or broker mutation in the scheduler row
- this is a read-only gate that tells us whether the next live-adjacent step is blocked or ready

## Topology statement

- Runtime topology changed: no further runtime edge beyond the repo-side bridge
- Scheduler topology changed: yes, the staged disabled row is now enabled
- Live authority changed: no
