# 2026-04-17 — non-cash dispatch path traversal receipt

- status: done
- topology: unchanged
- scope: strengthen non-cash dispatch proof without broker mutation
- boundary: still prepared-only; no real broker submission executed

## Verdict
The bounded non-cash operator lane now has a verifier-backed path-traversal receipt, not just a textual `stub-only` label.

## Source bundle
- JSON bundle: `/root/.openclaw/workspace/steamer-card-engine/docs/receipts/artifacts/2026-04-17_live_smoke_readiness_non_cash_bundle.json`
- preflight status: `ready`
- smoke status: `pass`
- boundary: `seed smoke/control surface only; no broker submission executed`

## Verified path
- `preflight-smoke-gate` -> ok=True exit_code=0
- `status-disarmed-baseline` -> ok=True exit_code=0
- `submit-refused-while-disarmed` -> ok=True exit_code=4
- `arm-live-bounded-scope` -> ok=True exit_code=0
- `submit-accepted-while-armed` -> ok=True exit_code=0
- `flatten-and-close-armed-window` -> ok=True exit_code=0
- `status-disarmed-after-flatten` -> ok=True exit_code=0

## What this closes
- proves the operator-control path traverses real bounded state transitions under a fresh truthful upstream probe
- proves the lane is not limited to a single static stub string; it enforces disarmed refusal, bounded arming, acceptance-in-smoke-lane, flatten, and disarm recovery
- keeps the non-cash boundary explicit so this cannot be misread as broker execution proof

## What this does not close
- no broker adapter submission
- no real order lifecycle / fill / flatten semantics on a broker-attached path
- no real-money smoke

## Receipt paths emitted by the bounded run
- `.state/operator_receipts/20260417T020456Z_submit-order-smoke_op-dff33a4cc82.json`
- `.state/operator_receipts/20260417T020456Z_arm-live_op-723bbb20590.json`
- `.state/operator_receipts/20260417T020456Z_submit-order-smoke_op-437c832333f.json`
- `.state/operator_receipts/20260417T020456Z_flatten_op-5f1e4488dbe.json`

## Interpretation
- This is stronger than the prior proof surface because it captures the full bounded control-path contract under current truthful preflight conditions.
- It is still intentionally below the real-money smoke line.
