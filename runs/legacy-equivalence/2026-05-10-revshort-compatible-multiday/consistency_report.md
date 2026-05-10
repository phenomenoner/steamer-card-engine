# Legacy decision trace equivalence report

Machine summary: `/root/.openclaw/workspace/steamer-card-engine/runs/legacy-equivalence/2026-05-10-revshort-compatible-multiday/summary.json`
Mismatch samples: `/root/.openclaw/workspace/steamer-card-engine/runs/legacy-equivalence/2026-05-10-revshort-compatible-multiday/mismatch_samples.jsonl`

## Verdict
PASS

## Scope
- data_root: `/workspace/CC/StrategyExecuter_Steamer-Antigravity/.data`
- gates: REV_SHORT_AFTER_UP
- datasets: 4
- Equality target: decision trace (`enter`, `reason`) from embedded legacy `state`; not PnL/fill/execution equivalence.

## Aggregate

| gate | rows | enter mismatches | reason mismatches | enter match | reason match |
|---|---:|---:|---:|---:|---:|
| REV_SHORT_AFTER_UP | 272431 | 0 | 0 | 1.000000 | 1.000000 |

## Per dataset

- `dt3/20260123` `REV_SHORT_AFTER_UP`: rows=35856, enter_mismatches=0, reason_mismatches=0, enter_match=1.000000, reason_match=1.000000
- `dt3/20260127` `REV_SHORT_AFTER_UP`: rows=129252, enter_mismatches=0, reason_mismatches=0, enter_match=1.000000, reason_match=1.000000
- `dt3/20260128` `REV_SHORT_AFTER_UP`: rows=9195, enter_mismatches=0, reason_mismatches=0, enter_match=1.000000, reason_match=1.000000
- `dt3/20260129` `REV_SHORT_AFTER_UP`: rows=98128, enter_mismatches=0, reason_mismatches=0, enter_match=1.000000, reason_match=1.000000

## Limitations
- The first slice uses compatibility-card gate functions over already-recorded legacy state snapshots.
- It does not reconstruct features from ticks yet; if state fields are absent, that future phase is required.
- VCP January traces may reflect older legacy semantics; divergences are reported, not normalized away.
