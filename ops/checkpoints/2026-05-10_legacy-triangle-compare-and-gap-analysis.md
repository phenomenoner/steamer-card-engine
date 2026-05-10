# WAL — legacy triangle compare and mechanism gap analysis — 2026-05-10

## Change

Added triangle A/B/C trace comparator and documented why whole-mechanism legacy parity requires more than strategy card parameters.

## Why now

CK asked to continue the `steamer-card-engine verifier` line non-stop and specifically asked whether current mismatch indicates missing runtime components or card schema surfaces.

## Artifacts

```text
src/steamer_card_engine/triangle_compare.py
tests/test_triangle_compare.py
docs/LEGACY_EQUIVALENCE_GAP_ANALYSIS_2026-05-10.md
docs/receipts/2026-05-10_triangle_compare_and_mechanism_gap.md
runs/legacy-equivalence/2026-05-10-triangle-compare-20260129-pre930/
```

## Result

First bounded triangle smoke:

```text
A historical: dt3/20260129 decisions <= 09:30
B latest legacy replay: recorded ticks <= 09:30
C card candidate: generated from B state
verdict: PASS_BC_SEMANTICS
```

Pairwise deltas:

```text
B_vs_C: row_delta=0, enter_true_delta=0, reason_delta={}
A_vs_B: row_delta=535, enter_true_delta=0, reason_delta now_time_5 +4218 / sweet -3683
A_vs_C: same as A_vs_B
```

## Interpretation

- Card-engine gate semantics match latest replay state for this bounded slice.
- Remaining A-vs-B gap is replay/runtime substrate: exact sweet-range policy, recorder placement, active universe/event selection, not immediate card semantic mismatch.
- Whole-mechanism parity needs additional contracts: RunUniverseSpec, MarketObservationPolicy, FeaturePipelineSpec, DecisionTraceSchema, PolicyLineageSpec.

## Verification

```text
uv run pytest tests/test_legacy_equivalence.py tests/test_legacy_lineage_and_tick_probe.py tests/test_legacy_replay.py tests/test_triangle_compare.py tests/test_sim_compare.py -q
```

Expected/observed: `28 passed`.

## Rollback

Revert the local commit containing this WAL and related files. No runtime topology, cron, gateway, broker, or remote state changed.

## Topology

Unchanged.
