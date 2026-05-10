# Triangle compare and mechanism gap — 2026-05-10

## Verdict

`triangle_compare` landed and the first A/B/C smoke passes the key semantic invariant:

```text
B latest-legacy replay vs C card candidate: PASS_BC_SEMANTICS
```

This means card-engine gate semantics match the latest replay state for the bounded pre-09:30 slice. Remaining A-vs-B/A-vs-C differences are replay/runtime substrate gaps, not immediate card-gate semantic drift.

## Artifacts

Implementation:

```text
src/steamer_card_engine/triangle_compare.py
tests/test_triangle_compare.py
```

Smoke artifact:

```text
runs/legacy-equivalence/2026-05-10-triangle-compare-20260129-pre930/triangle_compare_summary.json
runs/legacy-equivalence/2026-05-10-triangle-compare-20260129-pre930/triangle_compare_report.md
```

Mechanism gap analysis:

```text
docs/LEGACY_EQUIVALENCE_GAP_ANALYSIS_2026-05-10.md
```

## Smoke run

Dataset:

```text
A: /workspace/CC/StrategyExecuter_Steamer-Antigravity/.data/dt3/20260129/decisions.jsonl
B: runs/legacy-equivalence/2026-05-10-latest-legacy-replay-20260129-pre930/latest_legacy_replay_decisions.jsonl
C: generated from B state via card-engine evaluator
slice: REV_SHORT_AFTER_UP <= 09:30:00 local
```

Result:

```json
{
  "A_vs_B": {
    "row_delta": 535,
    "enter_true_delta": 0,
    "symbol_count_delta": 0,
    "reason_delta_top20_scope": {
      "now_time_5": 4218,
      "sweet": -3683
    }
  },
  "B_vs_C": {
    "row_delta": 0,
    "enter_true_delta": 0,
    "symbol_count_delta": 0,
    "reason_delta_top20_scope": {}
  },
  "A_vs_C": {
    "row_delta": 535,
    "enter_true_delta": 0,
    "symbol_count_delta": 0,
    "reason_delta_top20_scope": {
      "now_time_5": 4218,
      "sweet": -3683
    }
  }
}
```

Interpretation:

- `B_vs_C` clean: card candidate semantics are identical on B replay state.
- `A_vs_B` still differs in row count and `sweet` vs `now_time_5` distribution.
- Because `enter_true_delta=0`, the no-entry trading invariant matches for this slice.
- The remaining pre-09:30 gap points to active replay substrate / exact sweet-range policy / recorder placement, not a trade-entry semantic mismatch.

## Mechanism gap conclusion

The mismatch is not just “strategy card schema missing one field”. The legacy bot's decision stream blends multiple layers:

1. active universe / target-list filtering
2. market data observation policy
3. feature pipeline formulas and warmup
4. pure strategy gate
5. runtime risk/order/sizing blockers
6. recorder semantics
7. historical policy lineage

Recommended schema split:

```text
Card manifest            -> pure signal family and strategy params
Deck manifest            -> risk/capital/execution binding
ScenarioSpec             -> event source/session/timestamp semantics
RunUniverseSpec          -> evaluated symbol universe lineage
FeaturePipelineSpec      -> EMA/zigzag/slope/sweet formulas and tolerances
DecisionTraceSchema      -> layered gate/risk/order/final decision rows
PolicyLineageSpec        -> historical config/code grouping
```

## Tests

```text
uv run pytest tests/test_legacy_equivalence.py tests/test_legacy_lineage_and_tick_probe.py tests/test_legacy_replay.py tests/test_triangle_compare.py tests/test_sim_compare.py -q
```

Result:

```text
28 passed
```

## Topology/config impact

Unchanged. Repo-local verifier/replay/report tooling only. No remote push.
