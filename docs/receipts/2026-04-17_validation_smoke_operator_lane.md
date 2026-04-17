# 2026-04-17 — validation smoke operator lane receipt

- status: done
- topology: unchanged
- scope: close Slice 7 on the validation smoke deck itself
- boundary: prepared-only / non-cash operator proof, no broker submission claim

## Verdict
The bounded operator lane is now green on the exact validation deck used for runtime-path proof.
We are no longer borrowing operator proof from `tw_cash_intraday.toml`.

## Artifacts
- preflight artifact: `docs/receipts/artifacts/2026-04-17_validation_smoke_operator_preflight.json`
- bounded smoke artifact: `docs/receipts/artifacts/2026-04-17_validation_smoke_operator_lane.json`
- focused tests: `tests/test_validation_smoke_operator_lane.py`
- emitted operator receipts:
  - `.state/validation_smoke/operator_receipts/20260417T032655Z_submit-order-smoke_op-d2b3b419992.json`
  - `.state/validation_smoke/operator_receipts/20260417T032655Z_arm-live_op-00c8e6ba524.json`
  - `.state/validation_smoke/operator_receipts/20260417T032655Z_submit-order-smoke_op-5a607359946.json`
  - `.state/validation_smoke/operator_receipts/20260417T032655Z_flatten_op-0af60f7644b.json`

## What is proven
- `operator preflight-smoke` is `ready` on `examples/decks/tw_cash_validation_smoke.toml`
- `operator live-smoke-readiness` is `pass` on that same deck
- the bounded sequence stays truthful:
  - preflight gate
  - disarmed baseline
  - refusal while disarmed
  - bounded arm-live
  - acceptance in smoke lane while armed
  - flatten
  - disarmed-after-flatten
- the validation deck can still be blocked when the auth profile is non-trading (`tw_cash_agent_assist.toml`)

## What this does not prove
- no broker-connected order lifecycle
- no fill semantics
- no real-money smoke

## Interpretation
This closes the operator-lane gap from the reassessment.
The validation-deck proof is now deck-specific, not inherited from a different deck surface.
