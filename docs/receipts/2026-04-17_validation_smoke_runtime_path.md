# 2026-04-17 — validation smoke runtime path receipt

- status: done
- topology: unchanged
- scope: close Slice 5 and Slice 6 for the validation smoke deck
- boundary: deterministic runtime-path proof only, no broker submission

## Verdict
The validation smoke deck now proves a real manifest -> runtime -> intent path.
This is no longer two green islands.
The TOML deck resolves through the repo runtime loader into real card factories, and deterministic scenarios reconstruct entry, blocked-exit, exit-after-position-open, and no-trade behavior.

## Artifacts
- runtime artifact: `docs/receipts/artifacts/2026-04-17_validation_smoke_runtime_path.json`
- pytest artifact: `docs/receipts/artifacts/2026-04-17_validation_smoke_pytest.txt`
- bridge test: `tests/test_validation_smoke_runtime_bridge.py`
- runtime helper: `src/steamer_card_engine/validation_runtime.py`

## What is proven
- `examples/decks/tw_cash_validation_smoke.toml` resolves all three smoke cards through the repo runtime bridge
- resolved runtime cards match the manifest contract exactly:
  - `smoke-entry-once-v1`
  - `smoke-exit-once-v1`
  - `smoke-no-trade-guard-v1`
- the validation deck remains explicitly non-production (`live_mode = false`, smoke cards remain `replay-only`)
- deterministic runtime scenarios pass:
  - `entry-once`
  - `exit-blocked-without-position-open`
  - `exit-once-after-position-open`
  - `no-trade-guard`

## Verifier result
- command: `uv run pytest -q tests/test_validation_smoke_runtime_bridge.py tests/test_validation_smoke_operator_lane.py tests/test_validation_smoke_cards.py tests/test_manifests.py tests/test_cli.py`
- result: `45 passed in 0.40s`

## What this does not prove
- no broker adapter submission
- no real-money smoke
- no strategy-alpha quality claim

## Interpretation
This closes the exact gap the reassessment called out:
manifest-tested TOMLs and unit-tested factories are now bound by one verifier-backed runtime path.
