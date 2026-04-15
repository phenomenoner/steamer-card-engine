# Strategy Powerhouse verifier bridge — TimesFM v1 bucket baseline

- recorded: 2026-04-15
- source: `strategy-powerhouse-framework/docs/verifiers/2026-04-15_timesfm_regime_rank_assist_v1_bucket_baseline.md`
- family / candidate: `timesfm_regime_rank_assist`
- verifier_id: `timesfm_regime_rank_assist_v1_bucket_baseline`
- status: **prepared, not run**
- intended surface: `replay` planning only

## Why this bridge exists
The original TimesFM handoff was honest but still broad.
This verifier bridge narrows the next gate to one question only:

Can TimesFM-derived ranking / bucketing beat dumb baselines enough to keep this line alive?

## Current downstream truth
- the handoff remains **observation-only**
- no card/deck activation is implied
- no live-sim readiness is claimed
- no intraday strategy claim is unlocked by this verifier contract alone

## Required proof before any stronger claim
A valid result receipt must show:
- same-universe comparison against trivial baselines
- walk-forward stability
- friction-aware usefulness
- explicit verdict `PROMISING / HOLD / ITERATE / KILL`

Without that receipt, the correct downstream state is still `proposal only`.

## Safe abort rule
If the verifier result is mush or blocked, retire the line or hold it cleanly.
Do not convert a weak benchmark into a decorative active candidate.

## Topology statement
- topology unchanged
- this is verifier preparation only
- execution ownership stays in `steamer-card-engine`
- research/control-plane ownership stays in `strategy-powerhouse-framework`
