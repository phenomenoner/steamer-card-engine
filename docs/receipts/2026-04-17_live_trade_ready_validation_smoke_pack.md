# 2026-04-17 — live-trade-ready validation smoke pack receipt

- status: partial-pass
- topology: unchanged
- scope: land the first deterministic validation-only smoke pack for `steamer-card-engine`
- boundary: non-real-money only, no broker-connected execution claim

## Verdict
Slice 1 is landed, Slice 2 manifest/CLI family is landed, and Slice 3 now has a first deterministic runtime-intent cut.
A minimal validation-only smoke card/deck pack now exists, and the smoke cards now map to a real deterministic runtime module covered by tests.

## What landed
New validation-only authoring artifacts:
- `examples/cards/smoke_entry_once.toml`
- `examples/cards/smoke_exit_once.toml`
- `examples/cards/smoke_no_trade_guard.toml`
- `examples/decks/tw_cash_validation_smoke.toml`

New runtime validation module:
- `src/steamer_card_engine/cards/validation_smoke.py`

New verifier coverage:
- `tests/test_manifests.py`
- `tests/test_cli.py`
- `tests/test_validation_smoke_cards.py`

## What is now proven
- validation-only smoke cards load under the existing card manifest contract
- the validation smoke deck loads under the existing deck manifest contract
- CLI `validate-card` succeeds on the new smoke pack
- CLI `inspect-deck --json` resolves the smoke deck and merged feature requirements truthfully
- the smoke cards map to a real deterministic runtime module instead of manifest-only placeholders
- deterministic entry, exit, and no-trade runtime branches now have focused unit coverage
- the validation artifacts are clearly separated from production strategy quality claims

## Verifier result
- command: `uv run pytest -q tests/test_manifests.py tests/test_cli.py tests/test_validation_smoke_cards.py`
- result: `40 passed in 0.37s`

## What remains open
- deterministic fixture injection into replay/live-sim is not yet defined
- operator preflight/live-smoke rerun for this specific validation pack is not yet attached
- risk/gating and lifecycle packaging families still need fresh closure receipts
- real-money smoke remains unexecuted and still the final production-facing gate

## Interpretation
This closes the authoring/manifest side of the validation-smoke plan and lands the first deterministic runtime-intent module for entry/exit/no-trade proof.
It still does **not** prove replay/live-sim entry/exit behavior end-to-end.
