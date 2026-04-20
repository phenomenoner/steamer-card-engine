# Result receipt — TimesFM v1 bucket baseline

- recorded: 2026-04-20T10:42:14.381802+00:00
- family_id: `timesfm_regime_rank_assist`
- variant_id: `timesfm_bucket_baseline_daily_30m`
- verifier_id: `timesfm_regime_rank_assist_v1_bucket_baseline`
- verdict: `HOLD`
- topology: unchanged

## Universe rule
- fixed-universe symbols (3): AAA, BBB, CCC
- input path: `/root/.openclaw/workspace/steamer-card-engine/tests/fixtures/timesfm_first_run_fixture.csv`

## Date range / walk-forward slices
- evaluation dates: 2026-01-21 -> 2026-01-24 (4 sessions)
- slice count: 3

## Baselines run
- last_return
- momentum_5_20
- simple_reversal
- moving_average_slope
- simple_volatility_proxy

## Score mappings run
- TimesFM score resolved from one of: timesfm_score / timesfm_pred_return / timesfm_pred_price

## Decision-grade metrics
- TimesFM rank IC: 1.0000
- TimesFM top bucket hit rate: 1.0000
- TimesFM top-minus-bottom spread: 0.080000
- TimesFM friction-aware score: 0.080000
- strongest trivial baseline: last_return
- strongest baseline rank IC: 1.0000
- strongest baseline top-minus-bottom spread: 0.080000
- strongest baseline friction-aware score: 0.080000

## Interpretation
This runnable substrate now computes the bounded first-pass benchmark honestly from a daily cross-sectional CSV. Result quality still depends on the input dataset; this receipt does not imply live-sim or card activation.

## What this proves
- the TimesFM first-run lane now has an executable local substrate
- the lane can emit a bounded receipt with fixed-universe, slice, baseline, and friction-aware metrics

## What this does not prove
- no live-readiness claim
- no intraday edge claim
- no automatic promotion to an active card/deck

## Next governed move
- run the same tool on a real fixed-universe daily dataset and judge PROMISING / HOLD / ITERATE / KILL from the resulting receipt