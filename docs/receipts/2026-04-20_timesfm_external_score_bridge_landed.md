# Receipt — TimesFM external score bridge landed

- recorded: 2026-04-20
- topology: unchanged

## What changed
- added bridge module:
  - `src/steamer_card_engine/timesfm_input_bridge.py`
- added CLI entrypoint:
  - `steamer-card-engine-timesfm-build-input`
- added focused tests and fixtures:
  - `tests/test_timesfm_input_bridge.py`
  - `tests/fixtures/timesfm_bridge_close_history.csv`
  - `tests/fixtures/timesfm_bridge_scores.csv`
  - `tests/fixtures/timesfm_bridge_watchlist.csv`
- added execution packet:
  - `ops/execution-packets/2026-04-20_steamer-card-engine_timesfm-external-score-bridge.packet.md`

## What is now true
- an external TimesFM scoring lane can now hand off into the local bounded runner contract without manual CSV surgery
- the bridge can optionally filter rows to a daily watchlist universe
- the bridge emits a machine-readable merge summary
- the bridge can be chained directly into `steamer-card-engine-timesfm-first-run`

## Verification
- `uv run pytest -q tests/test_timesfm_input_bridge.py tests/test_timesfm_first_run.py`
- `uv run ruff check src/steamer_card_engine/timesfm_input_bridge.py tests/test_timesfm_input_bridge.py src/steamer_card_engine/timesfm_first_run.py tests/test_timesfm_first_run.py`
- fixture bridge run:
  - `docs/receipts/artifacts/2026-04-20_timesfm_bridge_fixture_input.csv`
  - `docs/receipts/artifacts/2026-04-20_timesfm_bridge_fixture_summary.json`
- chained fixture receipt:
  - `docs/receipts/artifacts/2026-04-20_timesfm_bridge_fixture_receipt.md`
  - `docs/receipts/artifacts/2026-04-20_timesfm_bridge_fixture_receipt.json`

## Honest boundary
- this still does not solve missing real TimesFM model output
- it does remove the glue-code blocker once those outputs exist