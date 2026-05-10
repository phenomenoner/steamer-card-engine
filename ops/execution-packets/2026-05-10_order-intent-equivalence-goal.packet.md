# Order intent equivalence goal — legacy vs steamer-card-engine

## Goal

Build enough evidence that `steamer-card-engine` order intent matches the legacy bot with high confidence before any real-money replacement test.

Primary equivalence target:

```text
Given the same market events, effective symbol universe, strategy config, broker/account snapshot, and position/open-order state,
legacy bot and steamer-card-engine emit the same final order intent.
```

## Non-goals

- Do not run both bots as real-money writers on the same account.
- Do not enable AWS shadow cron in this slice until existing AWS sim lifecycle is inspected and a dry-run/non-conflict plan exists.
- Do not change gateway/model routing.
- Do not push remote.

## Invariants

- Local-only repo commits are allowed.
- Live broker writes are not allowed.
- AWS instance lifecycle must not be double-started or double-stopped by a new lane.
- Shadow comparison artifacts must explain mismatches, not just log more rows.

## Phase 1 — replay order intent reconstruction

Inputs:

```text
legacy ticks.jsonl
legacy decisions.jsonl
legacy orders/fills if present
latest-legacy replay trace
card-engine replay/candidate trace
```

Outputs:

```text
scenario_spec.json
order_intents_legacy.jsonl
order_intents_candidate.jsonl
intent_diff.jsonl
intent_compare_summary.json
intent_compare_report.md
```

Intent schema v1:

```text
intent_id
source
row_kind: gate_block | enter_order | risk_block | order_block | exit_order | unknown
symbol
side
action: block | enter | exit | cancel | modify | none
quantity
price_basis: market | bid | ask | matched | limit_up | limit_down | unknown
order_type
order_time_in_force
reason
source_line_no
state_hash
```

Mismatch classes:

```text
universe_diff
feature_diff
gate_diff
risk_sizing_diff
order_lifecycle_diff
clock_alignment_diff
schema_gap
unknown
```

Verifier:

```bash
uv run pytest tests/test_order_intent.py tests/test_triangle_compare.py tests/test_legacy_replay.py -q
uv run python -m steamer_card_engine.order_intent_compare --help
uv run python -m steamer_card_engine.order_intent_compare --output-dir runs/legacy-equivalence/2026-05-10-order-intent-20260129-pre930 --legacy-decisions /workspace/CC/StrategyExecuter_Steamer-Antigravity/.data/dt3/20260129/decisions.jsonl --candidate-decisions runs/legacy-equivalence/2026-05-10-latest-legacy-replay-20260129-pre930/latest_legacy_replay_decisions.jsonl --gate REV_SHORT_AFTER_UP --end-local 09:30:00
```

Expected smoke:

```text
enter_order mismatches = 0 for pre-09:30 slice
all non-entry differences categorized as gate_block/reason distribution, not order-intent divergence
```

## Phase 2 — AWS shadow comparison lane design

Inspect existing AWS sim cron and lifecycle first. New lane must piggyback on the existing machine/session window, not own start/stop.

Initial design rule:

```text
shadow comparison lane is a consumer/observer of the existing AWS daily sim lifecycle.
It must not call start-instances or stop-instances unless explicitly promoted later.
```

Required shadow artifacts per run:

```text
scenario_spec.json
active_universe.json
broker_state_snapshots.jsonl
legacy_order_intents.jsonl
card_shadow_order_intents.jsonl
intent_diff.jsonl
summary.md
```

## Rollback

Revert local commits. If a cron is later proposed, keep it disabled/dry-run until CK confirms enable.

## Topology impact for this packet

Unchanged unless a future explicit cron install occurs. This packet itself is planning + local replay verifier implementation.
