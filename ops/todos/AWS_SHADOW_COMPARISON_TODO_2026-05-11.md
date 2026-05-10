# AWS shadow comparison TODO — 2026-05-11

## Goal

Align legacy bot vs `steamer-card-engine` order intent with high confidence before any real-money replacement validation.

Lane name: **AWS shadow comparison**

Daily intake rule:

```text
Before 09:00 Asia/Taipei:
- if CK provides a stock-code batch, use that batch;
- otherwise use the existing AWS sim watchlist/selection.
```

Safety rule:

```text
No EC2 lifecycle ownership, no broker order submission, no live replacement claim until evidence gates pass.
```

## Current status

Completed / landed locally:

```text
- legacy decision gate equivalence verifier
- lineage mismatch classifier
- tick price-path reconstruction probe
- latest legacy replay smoke
- triangle compare
- order-intent v1 smoke
- AWS shadow comparison daily intake/preflight cron
- AWS shadow lane preflight
- disabled dry-run observer manifest
```

Known truth label:

```text
Current evidence is necessary but not sufficient.
Current order-intent v1 is entry-intent smoke only, not live replacement confidence.
```

## TODO checklist

### P0 — next local replay gate

- [x] Implement **independent replay enter-order comparison**.
  - Do not use legacy `decisions.jsonl` as candidate input.
  - Candidate path must be: `ticks.jsonl -> latest legacy/card replay state -> card-engine decision trace -> order intent`.
  - Compare against legacy actual orders on days with `orders.jsonl` entries.
  - Required output:
    ```text
    scenario_spec.json
    order_intents_legacy.jsonl
    order_intents_candidate.jsonl
    order_intents_actual_legacy.jsonl
    intent_diff.jsonl
    intent_compare_summary.json
    intent_compare_report.md
    ```
  - Acceptance:
    ```text
    independent_candidate=true
    live_replacement_confidence=false until later gates
    entry order intent mismatches classified, not hidden
    tests pass
    WAL + docs ingest + local commit
    ```

- [x] Extend replay beyond pre-09:30 into **post-09:30 actual-entry windows**.
  - Target first days with actual legacy entries, currently observed:
    ```text
    dt3/20260123
    dt3/20260127
    ```
  - Acceptance:
    ```text
    candidate emits comparable enter/order-block intent around actual entry windows
    mismatch class distribution is machine-readable
    no tautological same-source candidate comparison
    ```

### P0 — shadow comparison substrate

- [x] Implement **AWS shadow observer worker dry-run hook**.
  - Must run observer-only.
  - Must not submit orders.
  - Must not call EC2 start/stop.
  - Must write artifacts under:
    ```text
    /opt/trading/current/data/sim/${DAY}/_shadow_compare/order_intent_v1
    ```
  - Required artifacts:
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
  - Acceptance:
    ```text
    shadow_lane_preflight.py passes with manifest
    no forbidden lifecycle tokens in manifest/hook
    dry-run does not require EC2 lifecycle changes
    WAL + local commit
    ```

- [x] Add verify/archive integration plan for shadow artifacts.
  - Do not modify live cron until dry-run evidence is clean.
  - Integration target:
    ```text
    existing 08:35 kickoff starts observer
    existing 08:45 verify checks observer health marker
    existing 13:40 archive includes shadow artifacts
    existing 13:46 stop guardrail remains sole stop owner
    ```
  - Acceptance:
    ```text
    diff contains no start-instances/stop-instances ownership
    archive dry-run shows shadow paths included
    verify dry-run shows observer health marker checked
    ```

### P1 — replay/feature completeness

- [ ] Formalize `ActiveUniverseSpec`.
  - Determine whether legacy has hidden filters between input symbol list and actual evaluated symbols.
  - Acceptance:
    ```text
    symbol list -> active universe transformation documented
    universe_diff classified separately from strategy/gate mismatch
    ```

- [ ] Formalize `MarketObservationPolicy`.
  - Must include:
    ```text
    exchange time vs receive time
    isOpen/isContinuous inclusion
    pre-open trial tick exclusion
    same timestamp ordering ambiguity
    ```
  - Acceptance:
    ```text
    replay uses policy artifact, not implicit assumptions
    ```

- [ ] Expand `FeaturePipelineSpec`.
  - Needed fields:
    ```text
    EMA seed/time-aware formula
    zigzag threshold/hysteresis/cooldown/min ticks
    slope windows/resample/median3 denoise
    sweet range exact policy
    high-update/new-high tolerance
    ```
  - Acceptance:
    ```text
    post-09:30 candidate reasons become explainable by feature_diff/gate_diff, not unknown
    ```

### P1 — order lifecycle parity

- [ ] Add broker/account snapshot schema.
  - Include:
    ```text
    available fund
    positions
    open orders
    pending orders
    per-symbol lot limit
    daily caps
    ```
  - Acceptance:
    ```text
    risk_sizing_diff can be separated from gate_diff
    ```

- [ ] Add exit / stop / trailing order intent reconstruction.
  - Current v1 only handles entry intent.
  - Acceptance:
    ```text
    exit_order / stop_order / trailing_stop intent rows emitted and compared
    ```

- [ ] Add pending order lifecycle comparison.
  - Compare cancel/modify/fill-driven state updates.
  - Acceptance:
    ```text
    order_lifecycle_diff has specific subreasons, not unknown
    ```

### P1 — mismatch reporting

- [ ] Expand mismatch classifier to cover shadow comparison.
  - Required classes:
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
  - Acceptance:
    ```text
    unknown mismatch rate is explicit and trends down over runs
    ```

- [ ] Add sequence/timing compare mode.
  - Current order-intent v1 is multiset-based.
  - Acceptance:
    ```text
    sequence/timestamp divergence cannot be hidden by matching multisets
    ```

### P2 — daily operations

- [ ] Let the 08:55 AWS shadow comparison intake/preflight cron run.
  - Existing job:
    ```text
    19b01d8b-94b6-446a-a89a-bf458a150c6a
    55 8 * * 1-5 @ Asia/Taipei
    ```
  - Acceptance:
    ```text
    if CK provided batch -> recorded in scenario/intake receipt
    if no batch -> existing AWS sim watchlist selected
    no EC2 lifecycle action taken by this cron
    ```

- [ ] After first preflight run, update this TODO with result.
  - Acceptance:
    ```text
    mark pass/blocker
    write WAL
    ingest docs if changed
    local commit
    ```


## 2026-05-11 P0 update

Closed to local/dry-run level:

```text
- independent replay enter-order comparison
- post-09:30 actual-entry windows for 20260123 / 20260127
- AWS shadow observer worker dry-run hook
- verify/archive dry-run integration plan
```

Key receipts:

```text
docs/receipts/2026-05-11_aws_shadow_comparison_p0_closure.md
runs/legacy-equivalence/2026-05-11-order-intent-independent-20260123/
runs/legacy-equivalence/2026-05-11-order-intent-independent-20260127/
runs/shadow-comparison/2026-05-11-observer-dry-run-20260123/
runs/shadow-comparison/2026-05-11-observer-dry-run-20260127/
```

Important blocker carried forward:

```text
Order shape parity passes on independent actual-entry days, but timing parity does not.
Initial timing gap: 20260123 max_abs_delta_seconds=684.645048; 20260127 max_abs_delta_seconds=8.797583.
After restoring legacy three-stage slope gate: 20260123 max_abs_delta_seconds=191.042596; 20260127 max_abs_delta_seconds=8.797583.
Treat as clock_alignment_diff / feature-replay-substrate gap before live confidence.
```

Timing probe receipt:

```text
docs/receipts/2026-05-11_aws_shadow_timing_gap_probe.md
```

Timing blocker closed for entry-order replay smoke:

```text
Root cause: replay used raw tick regression; legacy uses tick -> 1-second last-price resample -> median3 -> regression angle.
After resample + median3 fix: 20260123 max_abs_delta_seconds=0.041462; 20260127 max_abs_delta_seconds=0.047904.
```

Timing closure receipt:

```text
docs/receipts/2026-05-11_aws_shadow_timing_gap_closed.md
```

## Evidence gates before real-money validation

Do not recommend live replacement until all are true:

```text
- independent candidate replay enter-order parity passes on actual-entry days
- AWS shadow observer runs on same machine without lifecycle conflict
- order intent mismatches are zero or fully explained by accepted non-goals
- broker/account snapshot parity is implemented
- exit/stop/trailing intent parity has at least smoke evidence
- sequence/timing compare has no critical divergence
- multiple daily shadow comparison runs produce stable receipts
```

## Current references

```text
ops/execution-packets/2026-05-10_order-intent-equivalence-goal.packet.md
ops/checkpoints/2026-05-10_order-intent-equivalence-goal-opened.md
ops/checkpoints/2026-05-10_aws-shadow-comparison-schedule.md
docs/AWS_SHADOW_COMPARISON_LANE_PLAN_2026-05-10.md
docs/AWS_SHADOW_OBSERVER_MANIFEST_DRY_RUN_2026-05-10.json
docs/receipts/2026-05-10_order_intent_equivalence_goal_opened.md
docs/receipts/2026-05-10_shadow_lane_preflight.md
```
