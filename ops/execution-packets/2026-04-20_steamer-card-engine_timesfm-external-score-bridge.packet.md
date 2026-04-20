# Execution packet — steamer-card-engine TimesFM external score bridge

- recorded: 2026-04-20
- status: landed
- topology: unchanged

## Verdict
The missing glue between an external TimesFM scoring lane and the bounded first-run runner now exists locally.

## Whole-picture promise
Do not turn `steamer-card-engine` into a model-hosting battlefield.
Keep model inference external if needed, but make the import contract strict enough that a real receipt can be produced honestly once score rows exist.

## Bounded slice
Add a narrow adapter that merges:
- close-history CSV (`date,symbol,close`)
- external score CSV (`date,symbol` + one TimesFM score column)
- optional watchlist CSV (`run_date/date,symbol`)

into the already-landed first-run runner contract.

## Contract
### Inputs
- close-history CSV with `date,symbol,close`
- score CSV with `date,symbol` plus one of:
  - `timesfm_score`
  - `timesfm_pred_return`
  - `timesfm_pred_price`
- optional watchlist CSV with `run_date` or `date` and `symbol`

### Output
- merged runner-ready CSV for `steamer-card-engine-timesfm-first-run`
- optional JSON merge summary

### Error conditions
- missing required columns
- no accepted score column
- no bridged rows after merge/filter

## Surface
CLI entrypoint:
- `steamer-card-engine-timesfm-build-input`

Python module:
- `src/steamer_card_engine/timesfm_input_bridge.py`

## Verification
- focused tests:
  - `tests/test_timesfm_input_bridge.py`
- fixture bridge artifact:
  - `docs/receipts/artifacts/2026-04-20_timesfm_bridge_fixture_input.csv`
  - `docs/receipts/artifacts/2026-04-20_timesfm_bridge_fixture_summary.json`
- chained first-run artifact:
  - `docs/receipts/artifacts/2026-04-20_timesfm_bridge_fixture_receipt.md`
  - `docs/receipts/artifacts/2026-04-20_timesfm_bridge_fixture_receipt.json`

## Honest boundary
This bridge still does not create TimesFM scores.
It only makes external score import strict, testable, and receipt-ready.