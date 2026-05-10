# Order intent compare report

## Verdict
PASS_ENTER_INTENT_SMOKE_INDEPENDENT_CANDIDATE

## Sources
- legacy_decisions: `/workspace/CC/StrategyExecuter_Steamer-Antigravity/.data/dt3/20260129/decisions.jsonl`
- candidate_decisions: `/root/.openclaw/workspace/steamer-card-engine/runs/legacy-equivalence/2026-05-10-latest-legacy-replay-20260129-pre930/latest_legacy_replay_decisions.jsonl`
- legacy_orders: `None`

## Intent summaries

### legacy_enter
- count: 0
- actions: `{}`
- row_kinds: `{}`
- symbols_top20: `{}`

### candidate_enter
- count: 0
- actions: `{}`
- row_kinds: `{}`
- symbols_top20: `{}`

### actual_orders
- count: 0
- actions: `{}`
- row_kinds: `{}`
- symbols_top20: `{}`

## Comparisons

### legacy_enter_vs_candidate_enter
- match: True
- left_count: 0
- right_count: 0
- missing_from_right: `[]`
- extra_in_right: `[]`

## Scope / confidence
- scope: `entry-intent-smoke-only`
- independent_candidate: `True`
- live_replacement_confidence: `False`
- known_gaps: `['candidate trace may be same source as legacy unless independent_candidate=true', 'entry intents only; exits/stops/trailing are out of scope', 'multiset compare; sequence/timing parity is out of scope', 'broker/account/position/open-order snapshots are out of scope', 'REV_SHORT_AFTER_UP short-entry order shape is hardcoded in v1']`

## Notes
- v1 reconstructs entry order intent and actual order_submit intent. Exit/position-state parity is a later slice.
- A clean enter-intent smoke is necessary but not sufficient for live replacement.
