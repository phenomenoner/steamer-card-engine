# Execution packet — steamer-card-engine TimesFM first runner

- recorded: 2026-04-20
- status: landed
- topology: unchanged

## Verdict
The smallest honest TimesFM first-run substrate now exists locally.
It is a bounded daily cross-sectional runner, not a live or intraday engine.

## Surface
CLI entrypoint:
- `steamer-card-engine-timesfm-first-run`

Python module:
- `src/steamer_card_engine/timesfm_first_run.py`

## Input contract
CSV with:
- required: `date`, `symbol`, `close`
- one TimesFM field from: `timesfm_score`, `timesfm_pred_return`, `timesfm_pred_price`

## What it computes
- fixed-universe intersection across usable evaluation dates
- 3-slice walk-forward split by default
- baselines:
  - `last_return`
  - `momentum_5_20`
  - `simple_reversal`
  - `moving_average_slope`
  - `simple_volatility_proxy`
- TimesFM-vs-baseline receipt fields:
  - rank IC
  - top bucket hit rate
  - ordering rate
  - top-minus-bottom spread
  - friction-aware score
  - bounded verdict `PROMISING / HOLD / ITERATE / KILL`

## Output contract
- markdown receipt
- json receipt
- topology statement remains `unchanged`

## Guardrail
This runner does not grant:
- live-readiness
- intraday alpha claim
- active card/deck promotion

## Verification lane
- `uv run pytest -q tests/test_timesfm_first_run.py`
- `uv run ruff check src/steamer_card_engine/timesfm_first_run.py tests/test_timesfm_first_run.py`
- fixture execution receipt:
  - `docs/receipts/artifacts/2026-04-20_timesfm_first_run_fixture_receipt.md`
  - `docs/receipts/artifacts/2026-04-20_timesfm_first_run_fixture_receipt.json`

## Honest next move
Run this same substrate on a real fixed-universe daily dataset.
If that real receipt is weak, kill or hold the line honestly instead of widening scope.