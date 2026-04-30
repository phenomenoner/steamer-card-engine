# 2026-04-30 — real trade gate Stage 1 short-first tooling receipt

## Status
- status: tightened after QA
- topology: unchanged
- boundary: plan/smoke tooling only; no broker login, live arm, or order submission executed

## What changed
Stage 1 is now implemented as a **strict sell-first / short-capability gate** instead of a buy-first convenience smoke.

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
- unrelated deck/card contract mismatch
- missing or mismatched `[policy.real_trade_gate]`
- buy-first request (`stage1-requires-sell-first`)
- sell-first requested but symbol is not in explicit `--shortable-symbol` allowlist
- symbol not in deck scope
- non-positive quantity or exit delay
- profile lacks trade/account/marketdata capability
- operator posture is already armed

Accepted plan emits:
- entry leg: `sell`
- exit leg: canonical `cover`
- broker order side mapping for cover: `buy`
- max entry orders per run: 1
- max exit orders per run: 1
- max round trips per day: 1
- dispatch boundary: no broker submission executed

## Verifier receipts
Pytest / lint:
- command: `uv run ruff check src/steamer_card_engine/operator_control.py tests/test_validation_smoke_operator_lane.py tests/test_manifests.py && uv run pytest tests/test_validation_smoke_cards.py tests/test_validation_smoke_operator_lane.py tests/test_manifests.py -q`
- result: `All checks passed`; `24 passed in 0.25s`

Counterfactual CLI artifacts:
- accepted strict stage1 plan: `docs/receipts/artifacts/2026-04-30_real_trade_gate_tighten_accept.json`
  - result: `plan_status=planned`
  - blockers: none
  - exit leg: `cover`
- unrelated deck refusal: `docs/receipts/artifacts/2026-04-30_real_trade_gate_tighten_unrelated_deck.json`
  - result: `plan_status=refused`
  - blockers: `stage1-deck-card-contract-mismatch`, `real-trade-gate-policy-missing`
- buy-first refusal: `docs/receipts/artifacts/2026-04-30_real_trade_gate_tighten_buy_first.json`
  - result: `plan_status=refused`
  - blocker: `stage1-requires-sell-first`
- non-trade profile refusal: `docs/receipts/artifacts/2026-04-30_real_trade_gate_tighten_non_trade.json`
  - result: `plan_status=refused`
  - blocker: `trade-disabled`

## QA follow-up resolved
- Stage-1 planner now enforces expected short-first cards and policy fields.
- Buy-first no longer gets a soft warning; it is blocked for this Stage 1 gate.
- Exit semantics now preserve canonical `cover` while exposing `broker_order_side=buy`.
- Normal planner refusal paths emit JSON + receipt + CLI contract.
- Tests now cover unrelated deck, non-trade profile, already-armed posture, invalid quantity/delay, buy-first rejection, receipt schema, CLI contract, and new manifest validation.

## Deferred note
Malformed deck manifest JSON-envelope handling is improved for this planner through caught `ManifestValidationError` after deck resolution, but broader CLI-wide manifest error JSON standardization remains a separate CLI contract hardening line.

## Topology statement
Topology unchanged. This is repo-local CLI/card/deck tooling, docs, and receipt artifacts only; no scheduler, runtime config, broker credential, or gateway topology changed.
