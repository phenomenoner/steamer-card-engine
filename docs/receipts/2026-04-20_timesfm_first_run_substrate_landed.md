# Receipt — TimesFM first-run substrate landed

- recorded: 2026-04-20
- scope: cut the smallest executable local substrate for the TimesFM first verifier run
- topology: unchanged

## What changed
- added bounded runner module:
  - `src/steamer_card_engine/timesfm_first_run.py`
- added package script entrypoint:
  - `steamer-card-engine-timesfm-first-run`
- added fixture coverage:
  - `tests/test_timesfm_first_run.py`
  - `tests/fixtures/timesfm_first_run_fixture.csv`
- added execution packet:
  - `ops/execution-packets/2026-04-20_steamer-card-engine_timesfm-first-runner.packet.md`

## What is now true
- the TimesFM line no longer lacks an executable local first-pass substrate
- a bounded CSV input contract now exists
- the runner emits both markdown and json receipts
- the runner computes fixed-universe, walk-forward, baseline, and friction-aware metrics without pretending runtime activation

## Verification
- `uv run pytest -q tests/test_timesfm_first_run.py`
- `uv run ruff check src/steamer_card_engine/timesfm_first_run.py tests/test_timesfm_first_run.py`
- fixture execution:
  - `uv run steamer-card-engine-timesfm-first-run tests/fixtures/timesfm_first_run_fixture.csv --top-k 1 --receipt-md docs/receipts/artifacts/2026-04-20_timesfm_first_run_fixture_receipt.md --receipt-json docs/receipts/artifacts/2026-04-20_timesfm_first_run_fixture_receipt.json --json`

## Fixture truth
- fixture verdict: `HOLD`
- this is expected and honest
- the fixture proves substrate execution, not strategic superiority

## What remains placeholder
- no real TimesFM production dataset wired yet
- no real first-run receipt on market data yet
- no promotion or activation claim