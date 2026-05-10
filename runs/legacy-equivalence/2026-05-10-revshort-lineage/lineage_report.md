# Legacy equivalence mismatch lineage report

Machine summary: `/root/.openclaw/workspace/steamer-card-engine/runs/legacy-equivalence/2026-05-10-revshort-lineage/lineage_classification.json`

## Verdict
PASS_CLASSIFIED

## Aggregate classes

| class | count | share of mismatches |
|---|---:|---:|
| policy_lineage | 89981 | 98.07% |
| risk_order_layer | 1772 | 1.93% |

## Dataset summaries

- `dt3/20260121` rows=58298 mismatches=34204 classes={'policy_lineage': 34204}
- `dt3/20260122` rows=156333 mismatches=57548 classes={'policy_lineage': 55776, 'risk_order_layer': 1772}
- `dt3/20260123` rows=35856 mismatches=0 classes={}
- `dt3/20260126` rows=84071 mismatches=1 classes={'policy_lineage': 1}
- `dt3/20260127` rows=129252 mismatches=0 classes={}
- `dt3/20260128` rows=9195 mismatches=0 classes={}
- `dt3/20260129` rows=98128 mismatches=0 classes={}

## Top reason pairs

- `now_time_3 -> now_time_5`: 37580
- `not_strong_up -> now_time_5`: 21262
- `no_recent_high -> now_time_5`: 12021
- `zz_not_down -> now_time_5`: 11190
- `angle -> now_time_5`: 7067
- `enter_rev_short -> now_time_5`: 708
- `no_funds: avail=8400.0 -> enter_rev_short`: 695
- `lot_limit_reached: limit=1 -> enter_rev_short`: 695
- `no_funds: avail=8400.0 -> now_time_5`: 127
- `lot_limit_reached: limit=1 -> now_time_5`: 127
- `above_ema -> now_time_5`: 88
- `enter_rev_short -> trend_conflict: sl2/3(4.48/6.0200000000000005)> 5.0 & sl1(-5.92) > -15.0`: 4
- `no_funds: avail=8400.0 -> trend_conflict: sl2/3(4.48/6.0200000000000005)> 5.0 & sl1(-5.92) > -15.0`: 4
- `lot_limit_reached: limit=1 -> trend_conflict: sl2/3(4.48/6.0200000000000005)> 5.0 & sl1(-5.92) > -15.0`: 4
- `enter_rev_short -> trend_conflict: sl2/3(1.9100000000000001/19.23)> 5.0 & sl1(-5.71) > -15.0`: 3
- `no_funds: avail=8400.0 -> trend_conflict: sl2/3(1.9100000000000001/19.23)> 5.0 & sl1(-5.71) > -15.0`: 3
- `lot_limit_reached: limit=1 -> trend_conflict: sl2/3(1.9100000000000001/19.23)> 5.0 & sl1(-5.71) > -15.0`: 3
- `enter_rev_short -> trend_conflict: sl2/3(4.51/6.05)> 5.0 & sl1(-5.95) > -15.0`: 3
- `no_funds: avail=8400.0 -> trend_conflict: sl2/3(4.51/6.05)> 5.0 & sl1(-5.95) > -15.0`: 3
- `lot_limit_reached: limit=1 -> trend_conflict: sl2/3(4.51/6.05)> 5.0 & sl1(-5.95) > -15.0`: 3
- `enter_rev_short -> trend_conflict: sl2/3(5.5/8.13)> 5.0 & sl1(-5.01) > -15.0`: 1

## Interpretation
- `risk_order_layer` rows should not be forced into card gate logic; model them as runtime/risk-layer decisions.
- `policy_lineage` rows need scenario/config grouping before demanding full-sweep PASS.
- `gate_semantics` rows are the priority bug bucket for card-engine replication once A-vs-B drift is ruled out.
