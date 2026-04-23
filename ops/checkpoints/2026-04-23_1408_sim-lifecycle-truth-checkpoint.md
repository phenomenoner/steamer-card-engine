# Checkpoint — 2026-04-23 14:08 Asia/Taipei — sim lifecycle truth landed

## Line
`steamer-card-engine` observer sim-first lifecycle

## Current verdict
Proceed.
The sim artifact generator now emits truthful minimal lifecycle state for at least the regular-session entry slice, which is enough to move the observer line from candles/health-only toward lifecycle-backed projection on the sim lane.

## What now stands
- sim normalize-baseline no longer stops at execution request + placeholder order state only
- regular-session simulated entry now emits:
  - execution request with non-zero quantity
  - `order-lifecycle.jsonl` placeholder `new`
  - `order-lifecycle.jsonl` filled transition
  - `fills.jsonl` row
  - `positions.jsonl` open-position row
- pnl summary now reflects simulated filled-entry counts instead of forced zero-only placeholders for this slice
- forced-exit placeholder path still passes and remains bounded

## Files changed
- `src/steamer_card_engine/sim_compare.py`
- `tests/test_sim_compare.py`

## Verifier state
- targeted sim tests: pass
- `uv run pytest tests/test_sim_compare.py tests/test_dashboard.py tests/test_observer_bridge.py -q` → `35 passed`
- `uv run ruff check src/steamer_card_engine/sim_compare.py tests/test_sim_compare.py` → pass
- `npm --prefix frontend run build` → pass

## Boundary that still holds
- this is simulated lifecycle truth, not broker-backed lifecycle truth
- live/broker lifecycle remains deferred to the next phase
- observer public-safe lane still must not mislabel notes/requests as real broker fills

## Next recommended move
- map these simulated lifecycle artifacts into observer bundle events:
  - `order_submitted`
  - `order_acknowledged` / lifecycle transition
  - `fill_received`
  - `position_updated`
- prove one sim-backed observer session renders lifecycle and reconnects correctly

## Topology statement
Unchanged.
