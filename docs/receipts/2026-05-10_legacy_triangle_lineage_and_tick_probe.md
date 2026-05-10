# Legacy triangle verifier — lineage classification and tick probe

## Verdict

Second verifier slice landed for the triangle-equivalence plan.

It does not yet run full latest-legacy gate replay, but it proves two necessary foundations:

1. Existing full-sweep mismatches can be classified into concrete causes.
2. Core price-path state (`px`, `open_px`, `max_seen`, `min_seen`) can be reconstructed from recorded ticks when using exchange timestamps and ignoring pre-open trial ticks.

## Artifacts

Implementation:

```text
src/steamer_card_engine/legacy_lineage.py
src/steamer_card_engine/legacy_tick_probe.py
tests/test_legacy_lineage_and_tick_probe.py
```

Lineage classifier output:

```text
runs/legacy-equivalence/2026-05-10-revshort-lineage/lineage_classification.json
runs/legacy-equivalence/2026-05-10-revshort-lineage/lineage_samples.json
runs/legacy-equivalence/2026-05-10-revshort-lineage/lineage_report.md
```

Tick probes:

```text
runs/legacy-equivalence/2026-05-10-tick-probe-20260129/tick_probe_summary.json
runs/legacy-equivalence/2026-05-10-tick-probe-20260129/tick_probe_report.md
runs/legacy-equivalence/2026-05-10-tick-probe-20260122/tick_probe_summary.json
runs/legacy-equivalence/2026-05-10-tick-probe-20260122/tick_probe_report.md
```

## Lineage classifier result

Input: seven DT3 `REV_SHORT_AFTER_UP` January sessions from the prior full sweep.

```text
verdict: PASS_CLASSIFIED
classified_rate: 1.0
total_mismatches: 91,753
```

Aggregate classes:

```json
{
  "policy_lineage": 89981,
  "risk_order_layer": 1772
}
```

Interpretation:

- Most mismatches are policy/config/logic lineage, not direct card-engine semantic failure.
- 1,772 rows are risk/order-layer reasons such as `no_funds` / `lot_limit_reached`; these should not be forced into pure card gate logic.

## Tick reconstruction probe

### PASS-compatible day: `dt3/20260129`

```text
verdict: PASS_FEASIBLE
sampled_decisions: 800
```

Core price fields all matched after accounting for same-exchange-timestamp ambiguity:

```text
px       mismatches=0, timestamp_ambiguous_matches=58
open_px  mismatches=0
max_seen mismatches=0, timestamp_ambiguous_matches=4
min_seen mismatches=0
```

### Full-sweep FAIL day: `dt3/20260122`

```text
verdict: PASS_FEASIBLE
sampled_decisions: 800
```

Core price fields also matched after timestamp ambiguity handling:

```text
px       mismatches=0, timestamp_ambiguous_matches=63
open_px  mismatches=0
max_seen mismatches=0, timestamp_ambiguous_matches=1
min_seen mismatches=0
```

## Important implementation note

The first naive tick probe gave false mismatches because it used recorder receive time and included pre-open trial ticks. Legacy state uses exchange `time` and only updates price-path state for `isOpen` / `isContinuous` ticks. After correcting those assumptions, the sampled core price reconstruction became feasible.

Some residual price ambiguity is caused by multiple trade records sharing the same exchange timestamp. The probe treats those as `timestamp_ambiguous_matches` when the historical state falls within the same timestamp's possible ordering window.

## Current conclusion

The reliable next step is to implement latest-legacy replay for `REV_SHORT_AFTER_UP` using reconstructed tick state, then compare:

```text
A: historical decisions.jsonl
B: latest legacy replay from ticks
C: card-engine candidate trace
```

The classifier indicates that full-sweep mismatches are currently explainable as lineage/risk-layer issues; the tick probe indicates recorded ticks are good enough for core price-path replay.

## Tests

```text
uv run pytest tests/test_legacy_equivalence.py tests/test_legacy_lineage_and_tick_probe.py tests/test_sim_compare.py -q
```

Result:

```text
25 passed
```

## Topology/config impact

Unchanged. No cron, gateway, live monitor, broker, or remote topology changed.
