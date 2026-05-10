# Order intent equivalence goal opened — 2026-05-10

## Verdict

Goal opened for legacy-vs-card-engine order intent equivalence before real-money replacement testing.

Local replay order-intent v1 landed as **entry-intent smoke only**. It is necessary but not sufficient for live replacement confidence. AWS shadow lane is planned but not enabled; existing EC2 sim lifecycle was inspected first to avoid duplicate start/stop ownership.

## Implementation artifacts

```text
ops/execution-packets/2026-05-10_order-intent-equivalence-goal.packet.md
src/steamer_card_engine/order_intent_compare.py
tests/test_order_intent_compare.py
docs/AWS_SHADOW_COMPARISON_LANE_PLAN_2026-05-10.md
```

Replay smoke artifacts:

```text
runs/legacy-equivalence/2026-05-10-order-intent-20260123/
runs/legacy-equivalence/2026-05-10-order-intent-20260127/
runs/legacy-equivalence/2026-05-10-order-intent-20260129-pre930-independent/
```

Each smoke directory now includes:

```text
scenario_spec.json
order_intents_legacy.jsonl
order_intents_candidate.jsonl
order_intents_actual_legacy.jsonl
intent_diff.jsonl
intent_compare_summary.json
intent_compare_report.md
```

## Replay order intent v1

`order_intent_compare` reconstructs entry-order intent from decisions and compares it against actual legacy `order_submit` rows when `orders.jsonl` is present.

Intent fields currently checked:

```text
symbol
action
side
quantity
price_basis
order_type
order_time_in_force
```

### Smoke: 20260123

```text
verdict: PASS_ENTER_INTENT_SMOKE_ONLY
independent_candidate: false
live_replacement_confidence: false
legacy enter decisions: 2
actual legacy enter order_submit: 2
candidate enter: 2
```

Comparisons:

```text
legacy_enter_vs_actual_order_submit: match
legacy_enter_vs_candidate_enter: match
```

### Smoke: 20260127

```text
verdict: PASS_ENTER_INTENT_SMOKE_ONLY
independent_candidate: false
live_replacement_confidence: false
legacy enter decisions: 2
actual legacy enter order_submit: 2
candidate enter: 2
```

Comparisons:

```text
legacy_enter_vs_actual_order_submit: match
legacy_enter_vs_candidate_enter: match
```

### Independent no-entry smoke: 20260129 pre-09:30

```text
verdict: PASS_ENTER_INTENT_SMOKE_INDEPENDENT_CANDIDATE
independent_candidate: true
live_replacement_confidence: false
legacy enter decisions: 0
candidate enter: 0
```

This proves no-entry order intent parity on the independent latest-replay candidate pre-09:30 slice, but it is still not live replacement evidence because it has no actual entry orders and excludes post-09:30 feature/order lifecycle behavior.

## Important limitation

This v1 is necessary but not sufficient for live replacement confidence.

Current actual-order smokes use legacy decisions as candidate input for the two actual-order days, so `legacy_enter_vs_candidate_enter` is intentionally marked non-independent. The non-tautological check there is `legacy_enter_vs_actual_order_submit`: historical `enter=true` decisions correspond to actual legacy submitted enter orders with the same order-intent signature.

The 20260129 pre-09:30 smoke uses an independent latest-replay candidate, but has zero entry orders. It is a no-entry invariant check, not replacement-grade evidence.

It currently validates entry order intent shape for historical days with actual orders. It does not yet prove:

- replayed card-engine candidate matches legacy for all post-09:30 feature states;
- exit/stop/trailing order intent parity;
- broker/account snapshot parity;
- pending order lifecycle parity;
- AWS same-machine shadow parity.

## AWS daily sim lifecycle inspected

Existing enabled schedule surfaces found:

```text
08:25 EC2 power-on/readiness
08:35 online sim kickoff
08:45 verify+autoheal
13:40 archive/upload runtime artifacts
13:46 stop guardrail
```

Local specs contained two 13:46 stop-guardrail references, but live `openclaw cron list` showed only this one as current:

```text
c2eeb4f3-6a84-4910-ac7a-25938dda18da
```

Treat it as canonical stop owner unless later live readback changes.

## AWS lane recommendation

Do **not** add another lifecycle cron.

Recommended v1 topology:

```text
existing 08:25 power-on owns EC2 start
existing 08:35 kickoff launches normal sim + shadow observer worker
existing 08:45 verify checks both
existing 13:40 archive uploads normal + shadow artifacts
existing 13:46 stop guardrail remains sole stop owner
```

Shadow lane must emit per-run:

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

## Tests

```text
uv run pytest tests/test_order_intent_compare.py -q
```

Observed:

```text
4 passed
```

Full suite for closure should include triangle/replay/sim compare as well.

## Topology/config impact

Unchanged. No cron, AWS lifecycle, gateway, broker, or remote state changed.
