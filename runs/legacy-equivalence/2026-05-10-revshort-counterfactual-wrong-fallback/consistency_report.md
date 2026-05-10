# Legacy decision trace equivalence report

Machine summary: `/root/.openclaw/workspace/steamer-card-engine/runs/legacy-equivalence/2026-05-10-revshort-counterfactual-wrong-fallback/summary.json`
Mismatch samples: `/root/.openclaw/workspace/steamer-card-engine/runs/legacy-equivalence/2026-05-10-revshort-counterfactual-wrong-fallback/mismatch_samples.jsonl`

## Verdict
FAIL_NEEDS_COMPATIBILITY_MAPPING

## Scope
- data_root: `/workspace/CC/StrategyExecuter_Steamer-Antigravity/.data`
- gates: REV_SHORT_AFTER_UP
- datasets: 1
- Equality target: decision trace (`enter`, `reason`) from embedded legacy `state`; not PnL/fill/execution equivalence.

## Aggregate

| gate | rows | enter mismatches | reason mismatches | enter match | reason match |
|---|---:|---:|---:|---:|---:|
| REV_SHORT_AFTER_UP | 98128 | 2 | 2 | 0.999980 | 0.999980 |

## Per dataset

- `dt3/20260129` `REV_SHORT_AFTER_UP`: rows=98128, enter_mismatches=2, reason_mismatches=2, enter_match=0.999980, reason_match=0.999980

## Limitations
- The first slice uses compatibility-card gate functions over already-recorded legacy state snapshots.
- It does not reconstruct features from ticks yet; if state fields are absent, that future phase is required.
- VCP January traces may reflect older legacy semantics; divergences are reported, not normalized away.
