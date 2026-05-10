# Legacy decision trace equivalence report

Machine summary: `/root/.openclaw/workspace/steamer-card-engine/runs/legacy-equivalence/2026-05-10-revshort-multiday/summary.json`
Mismatch samples: `/root/.openclaw/workspace/steamer-card-engine/runs/legacy-equivalence/2026-05-10-revshort-multiday/mismatch_samples.jsonl`

## Verdict
FAIL_NEEDS_COMPATIBILITY_MAPPING

## Scope
- data_root: `/workspace/CC/StrategyExecuter_Steamer-Antigravity/.data`
- gates: REV_SHORT_AFTER_UP
- datasets: 7
- Equality target: decision trace (`enter`, `reason`) from embedded legacy `state`; not PnL/fill/execution equivalence.

## Aggregate

| gate | rows | enter mismatches | reason mismatches | enter match | reason match |
|---|---:|---:|---:|---:|---:|
| REV_SHORT_AFTER_UP | 571133 | 2163 | 91753 | 0.996213 | 0.839349 |

## Per dataset

- `dt3/20260121` `REV_SHORT_AFTER_UP`: rows=58298, enter_mismatches=577, reason_mismatches=34204, enter_match=0.990103, reason_match=0.413290
- `dt3/20260122` `REV_SHORT_AFTER_UP`: rows=156333, enter_mismatches=1585, reason_mismatches=57548, enter_match=0.989861, reason_match=0.631888
- `dt3/20260123` `REV_SHORT_AFTER_UP`: rows=35856, enter_mismatches=0, reason_mismatches=0, enter_match=1.000000, reason_match=1.000000
- `dt3/20260126` `REV_SHORT_AFTER_UP`: rows=84071, enter_mismatches=1, reason_mismatches=1, enter_match=0.999988, reason_match=0.999988
- `dt3/20260127` `REV_SHORT_AFTER_UP`: rows=129252, enter_mismatches=0, reason_mismatches=0, enter_match=1.000000, reason_match=1.000000
- `dt3/20260128` `REV_SHORT_AFTER_UP`: rows=9195, enter_mismatches=0, reason_mismatches=0, enter_match=1.000000, reason_match=1.000000
- `dt3/20260129` `REV_SHORT_AFTER_UP`: rows=98128, enter_mismatches=0, reason_mismatches=0, enter_match=1.000000, reason_match=1.000000

## Limitations
- The first slice uses compatibility-card gate functions over already-recorded legacy state snapshots.
- It does not reconstruct features from ticks yet; if state fields are absent, that future phase is required.
- VCP January traces may reflect older legacy semantics; divergences are reported, not normalized away.
