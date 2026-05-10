# AWS shadow comparison P0 closure — 2026-05-11

## Verdict

The non-waitable P0 items are closed to dry-run/local-verifier level.

Important truth label:

```text
order shape parity: PASS on independent replay actual-entry days
clock/timing parity: NOT PASS; timing deltas remain classified as clock_alignment_diff
live_replacement_confidence: false
```

## Completed P0 items

### 1. Independent replay enter-order comparison

Candidate source is no longer legacy `decisions.jsonl`.

Candidate path:

```text
legacy ticks.jsonl -> latest replay decision trace with minimal one-enter-per-symbol order layer -> order intent
```

Artifacts:

```text
runs/legacy-equivalence/2026-05-11-latest-legacy-replay-20260123-orderlayer/
runs/legacy-equivalence/2026-05-11-latest-legacy-replay-20260127-orderlayer/
runs/legacy-equivalence/2026-05-11-order-intent-independent-20260123/
runs/legacy-equivalence/2026-05-11-order-intent-independent-20260127/
```

Results:

```text
20260123: PASS_ENTER_INTENT_SMOKE_INDEPENDENT_CANDIDATE
  candidate_enter_vs_actual_order_submit: match=true, count=2 vs 2
  timing: match=false, max_abs_delta_seconds=684.645048

20260127: PASS_ENTER_INTENT_SMOKE_INDEPENDENT_CANDIDATE
  candidate_enter_vs_actual_order_submit: match=true, count=2 vs 2
  timing: match=false, max_abs_delta_seconds=8.797583
```

Interpretation:

- Candidate emits the same entry-order symbols and order shape on actual-entry days.
- Candidate timing does not fully align; this is now explicit machine-readable `clock_alignment_diff` evidence.
- 20260123 timing is especially far early and needs feature/clock/replay substrate investigation before live confidence.

### 2. Post-09:30 actual-entry windows

Covered by the two actual-entry days:

```text
20260123 entries: 2367 at 09:39:41.330, 3323 at 09:47:08.598
20260127 entries: 1301 at 10:26:01.153, 2337 at 11:13:53.699
```

The replay was run beyond pre-09:30 and produced comparable independent candidate enter intents.

### 3. AWS shadow observer worker dry-run hook

Implementation:

```text
tools/aws_shadow_observer_dry_run.py
tests/test_aws_shadow_observer_dry_run.py
```

Dry-run artifacts:

```text
runs/shadow-comparison/2026-05-11-observer-dry-run-20260123/
runs/shadow-comparison/2026-05-11-observer-dry-run-20260127/
```

Results:

```text
20260123: PASS_SHADOW_OBSERVER_DRY_RUN_ARTIFACTS, legacy_intent_count=2, card_shadow_intent_count=2, intent_diff_count=0
20260127: PASS_SHADOW_OBSERVER_DRY_RUN_ARTIFACTS, legacy_intent_count=2, card_shadow_intent_count=2, intent_diff_count=0
```

Required artifact contract emitted:

```text
scenario_spec.json
active_universe.json
broker_state_snapshots.jsonl
legacy_order_intents.jsonl
card_shadow_order_intents.jsonl
intent_diff.jsonl
intent_compare_summary.json
summary.md
```

### 4. Verify/archive integration dry-run plan

Plan artifact:

```text
docs/AWS_SHADOW_VERIFY_ARCHIVE_DRY_RUN_2026-05-11.md
```

Guardrail:

```text
No live cron was modified.
No EC2 start/stop ownership was added.
```

## Code changes

```text
src/steamer_card_engine/legacy_replay.py
  - added --enforce-one-enter-per-symbol
  - added --symbols scoped replay filter

src/steamer_card_engine/order_intent_compare.py
  - added candidate_enter_vs_actual_order_submit comparison
  - added timing comparison and clock_alignment_diff classification

tools/aws_shadow_observer_dry_run.py
  - added observer-only artifact emitter
```

## Remaining blockers before real-money validation

```text
- clock/timing parity is not yet clean, especially 20260123
- broker/account snapshot parity is placeholder-only
- exit/stop/trailing parity is not implemented
- pending order lifecycle parity is not implemented
- AWS live same-machine observer has not been enabled
```

## Topology/config impact

Unchanged. Local tools/artifacts/docs only. No AWS/Gateway/cron/broker changes in this slice.
