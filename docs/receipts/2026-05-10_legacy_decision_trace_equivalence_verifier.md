# Legacy decision trace equivalence verifier — 2026-05-10

## Verdict

First verifier slice landed as a repo-local `steamer-card-engine` compatibility verifier.

- Supported first gate: `REV_SHORT_AFTER_UP`
- Compatibility basis: replay card logic over embedded legacy `decisions.jsonl.state`
- Equality target: decision trace `enter` + `reason`
- Scope: no broker, no fills, no PnL, no live execution
- Remote push: none

## Artifacts

Spec / blade:

```text
ops/execution-packets/2026-05-10_legacy-decision-trace-equivalence-verifier.packet.md
```

Verifier implementation:

```text
src/steamer_card_engine/legacy_equivalence.py
tests/test_legacy_equivalence.py
```

Passing compatible multi-day report:

```text
runs/legacy-equivalence/2026-05-10-revshort-compatible-multiday/summary.json
runs/legacy-equivalence/2026-05-10-revshort-compatible-multiday/mismatch_samples.jsonl
runs/legacy-equivalence/2026-05-10-revshort-compatible-multiday/consistency_report.md
runs/legacy-equivalence/2026-05-10-revshort-compatible-multiday/effective_config.json
```

Full detected REV_SHORT_AFTER_UP sweep, including incompatible historical/runtime-policy days:

```text
runs/legacy-equivalence/2026-05-10-revshort-multiday/summary.json
runs/legacy-equivalence/2026-05-10-revshort-multiday/consistency_report.md
```

Counterfactual wrong-parameter smoke:

```text
runs/legacy-equivalence/2026-05-10-revshort-counterfactual-wrong-fallback/summary.json
runs/legacy-equivalence/2026-05-10-revshort-counterfactual-wrong-fallback/consistency_report.md
```

## Compatible multi-day result

Dataset subset:

```text
dt3/20260123
dt3/20260127
dt3/20260128
dt3/20260129
```

Aggregate:

```json
{
  "REV_SHORT_AFTER_UP": {
    "rows": 272431,
    "legacy_enter_true": 6,
    "candidate_enter_true": 6,
    "enter_mismatches": 0,
    "reason_mismatches": 0,
    "enter_match_rate": 1.0,
    "reason_match_rate": 1.0
  }
}
```

Verdict: `PASS`.

## Full sweep result

The verifier also scanned all detected non-empty `REV_SHORT_AFTER_UP` DT3 legacy decision files.

Aggregate:

```json
{
  "REV_SHORT_AFTER_UP": {
    "rows": 571133,
    "legacy_enter_true": 1474,
    "candidate_enter_true": 2091,
    "enter_mismatches": 2163,
    "reason_mismatches": 91753,
    "enter_match_rate": 0.996212791066179,
    "reason_match_rate": 0.83934915334957
  }
}
```

Verdict: `FAIL_NEEDS_COMPATIBILITY_MAPPING`.

Interpretation: not all January files share the same decision contract. Some earlier dates include order/risk post-gate block reasons (`no_funds`, `lot_limit_reached`) or different runtime policy (`now_time_3`, missing/later trend-conflict behavior). The verifier intentionally reports these as incompatibilities instead of normalizing them away.

## Counterfactual smoke

Changed config:

```json
{"fallback_pct": 3.0}
```

Against `dt3/20260129`, the verifier detected the expected mismatch:

```json
{
  "rows": 98128,
  "legacy_enter_true": 2,
  "candidate_enter_true": 0,
  "enter_mismatches": 2,
  "reason_mismatches": 2
}
```

This proves the verifier is sensitive to a real strategy parameter change and is not merely copying legacy output.

## Notes / limitations

- This first slice validates card-engine compatibility logic against legacy state snapshots, not full feature reconstruction from ticks.
- PnL/fill/order lifecycle equivalence remains a later phase.
- `LONG_ONE_VCP` compatibility scaffolding exists in the implementation, but the reported PASS target in this receipt is `REV_SHORT_AFTER_UP` only.
- Future work should add scenario lineage metadata so each date is matched with its exact runtime policy/config before full-sweep PASS is expected.


## Review fixes applied

Independent review found two verifier-safety must-fixes; both are now addressed:

- Empty/no-data runs now raise `LegacyEquivalenceError` instead of emitting a false `PASS`.
- `--output-dir` is restricted to relative paths under `runs/legacy-equivalence/`; absolute/outside paths are rejected.

Additional polish:

- `--gate` default no longer silently combines the default gate with explicitly supplied gates.
- Explicit `--decision-file` paths outside `data_root` are labelled `external/<parent>` instead of crashing.

Post-fix tests:

```text
uv run pytest tests/test_legacy_equivalence.py tests/test_sim_compare.py -q
21 passed in 0.40s
```

## Topology/config impact

Unchanged. No cron, gateway, live monitor, broker, or remote topology changed.
