# Order intent compare report

## Verdict
PASS_ENTER_INTENT_SMOKE_INDEPENDENT_CANDIDATE

## Sources
- legacy_decisions: `/workspace/CC/StrategyExecuter_Steamer-Antigravity/.data/dt3/20260127/decisions.jsonl`
- candidate_decisions: `/root/.openclaw/workspace/steamer-card-engine/runs/legacy-equivalence/2026-05-11-latest-legacy-replay-20260127-resamplefix/latest_legacy_replay_decisions.jsonl`
- legacy_orders: `/workspace/CC/StrategyExecuter_Steamer-Antigravity/.data/dt3/20260127/orders.jsonl`

## Intent summaries

### legacy_enter
- count: 2
- actions: `{'enter': 2}`
- row_kinds: `{'enter_order_intent': 2}`
- symbols_top20: `{'1301': 1, '2337': 1}`

### candidate_enter
- count: 2
- actions: `{'enter': 2}`
- row_kinds: `{'enter_order_intent': 2}`
- symbols_top20: `{'1301': 1, '2337': 1}`

### actual_orders
- count: 4
- actions: `{'enter': 2, 'stop': 2}`
- row_kinds: `{'actual_order_submit': 4}`
- symbols_top20: `{'1301': 2, '2337': 2}`

## Comparisons

### legacy_enter_vs_candidate_enter
- match: True
- left_count: 2
- right_count: 2
- missing_from_right: `[]`
- extra_in_right: `[]`

### legacy_enter_vs_actual_order_submit
- match: True
- left_count: 2
- right_count: 2
- missing_from_right: `[]`
- extra_in_right: `[]`

### candidate_enter_vs_actual_order_submit
- match: True
- left_count: 2
- right_count: 2
- missing_from_right: `[]`
- extra_in_right: `[]`

## Timing comparisons

### candidate_enter_vs_actual_order_submit
- match: True
- tolerance_seconds: 2.0
- max_abs_delta_seconds: 0.04790399999910733
- problems: `[]`

## Scope / confidence
- scope: `entry-intent-smoke-only`
- independent_candidate: `True`
- live_replacement_confidence: `False`
- known_gaps: `['candidate trace may be same source as legacy unless independent_candidate=true', 'entry intents only; exits/stops/trailing are out of scope', 'multiset compare; sequence/timing parity is out of scope', 'broker/account/position/open-order snapshots are out of scope', 'REV_SHORT_AFTER_UP short-entry order shape is hardcoded in v1']`

## Notes
- v1 reconstructs entry order intent and actual order_submit intent. Exit/position-state parity is a later slice.
- A clean enter-intent smoke is necessary but not sufficient for live replacement.
