# 2026-04-12 — dashboard strategy-pipeline tab + state-driven gates

- status: done
- topology: unchanged
- scope: add a dedicated Strategy Pipeline tab and make the failed-auction-short focus-line status read a structured line-state receipt rather than relying only on filename presence

## What changed
- Added a dedicated dashboard API surface:
  - `/api/strategy-pipeline`
- Added a new browser tab:
  - `Strategy Pipeline / Autonomous Drivers`
- Added a shared line-state helper:
  - `src/steamer_card_engine/dashboard/strategy_line_state.py`
- Updated `strategy_powerhouse.py` so the failed-auction-short focus line / stage board now prefer the machine-readable line-state receipt
- Added a dedicated read-only pipeline view that shows:
  - canon flow
  - pipeline components
  - autonomous drivers
  - handoff gate truth
  - control-plane pointers

## Why this slice
The previous dashboard work made the line visible, but autonomous truth was still too filename-driven.
This slice turns the new line into a state-aware dashboard surface and gives operators a dedicated whole-pipeline tab instead of burying the explanation inside the strategy-history tab.

## Verification
- `python3 -m py_compile src/steamer_card_engine/dashboard/strategy_powerhouse.py src/steamer_card_engine/dashboard/strategy_pipeline.py src/steamer_card_engine/dashboard/strategy_line_state.py src/steamer_card_engine/dashboard/api.py`
- `uv run pytest -q tests/test_dashboard.py`
- `cd frontend && npm run build`

## Truth / boundary notes
- read-only only; no execution authority added
- no scheduler or runtime topology change
- failed-auction-short still remains `not-yet` for autonomous non-stop execution until the real verifier bridge exists and the handoff gate can pass honestly
