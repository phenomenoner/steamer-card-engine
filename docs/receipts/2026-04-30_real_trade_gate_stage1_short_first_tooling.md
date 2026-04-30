# 2026-04-30 — real trade gate Stage 1 short-first tooling receipt

## Status
- status: implemented
- topology: unchanged
- boundary: plan/smoke tooling only; no broker login, live arm, or order submission executed

## What changed
Stage 1 is now implemented as a **sell-first / short-capability gate** instead of a buy-first convenience smoke.

Rationale from CK: if a symbol can be sold first, it is more likely to satisfy the day-trade capability we actually need; buy-first can accidentally pass on a symbol that can be bought but not day-traded/shorted, which would make the gate misleading.

## Added surfaces
- CLI: `steamer-card-engine operator plan-real-trade-gate`
- Strategy card manifests:
  - `examples/cards/real_trade_gate_short_first_entry.toml`
  - `examples/cards/real_trade_gate_short_first_cover.toml`
- Deck manifest:
  - `examples/decks/tw_cash_real_trade_gate_stage1_short_first.toml`
- Card factories:
  - `steamer_card_engine.cards.validation_smoke:short_first_entry_once`
  - `steamer_card_engine.cards.validation_smoke:short_first_cover_once`

## Gate behavior
`plan-real-trade-gate` is intentionally plan-only. It writes a receipt and refuses unsafe setup before any live arm/order path.

Hard refusals include:
- sell-first requested but symbol is not in explicit `--shortable-symbol` allowlist
- symbol not in deck scope
- non-positive quantity or exit delay
- profile lacks trade/account/marketdata capability
- operator posture is already armed

Accepted plan emits:
- entry leg: sell
- exit leg: buy
- max entry orders per run: 1
- max exit orders per run: 1
- max round trips per day: 1
- dispatch boundary: no broker submission executed

## Verifier receipts
Pytest:
- command: `uv run pytest tests/test_validation_smoke_cards.py tests/test_validation_smoke_operator_lane.py -q`
- result: `12 passed in 0.18s`

Counterfactual CLI artifacts:
- refusal without shortable allowlist: `docs/receipts/artifacts/2026-04-30_real_trade_gate_plan_refuse_no_shortable.json`
  - result: `plan_status=refused`
  - blocker: `short-capability-unproven`
- acceptance with shortable allowlist: `docs/receipts/artifacts/2026-04-30_real_trade_gate_plan_accept_shortable.json`
  - result: `plan_status=planned`
  - blockers: none

## Topology statement
Topology unchanged. This is repo-local CLI/card/deck tooling and docs only; no scheduler, runtime config, broker credential, or gateway topology changed.
