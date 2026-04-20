# TimesFM v1 real-data first run — blocked receipt

- recorded: 2026-04-20
- family_id: `timesfm_regime_rank_assist`
- variant_id: `timesfm_bucket_baseline_daily_30m`
- verifier_id: `timesfm_regime_rank_assist_v1_bucket_baseline`
- verdict: `BLOCKED`
- topology: unchanged

## Verdict
The line can now run a bounded receipt engine, but it still cannot produce an honest **real-data TimesFM first run** on this host.

## What is now confirmed
### 1. Real daily-selected-universe lineage exists
Representative AWS daily-selected universe lineage is present locally via watchlist artifacts such as:
- `openclaw-async-coding-playbook/projects/trading-research/artifacts/tw-watchlist/2026-04-17/watchlist.csv`
- `StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/backtests/2026-04-19_weekend_counterfactual_pack_latest10d.md`

So this is **not** blocked by total absence of candidate symbol sets.

### 2. No local TimesFM score surface exists yet
A repo-wide search found no real-data files with any of:
- `timesfm_score`
- `timesfm_pred_return`
- `timesfm_pred_price`

The only hits are the newly added substrate itself and fixture artifacts.

### 3. TimesFM runtime backend is not actually available on the host
Bounded probe:
- created isolated probe env at `/root/.openclaw/workspace/.state/steamer/timesfm_probe_20260420`
- `uv pip install timesfm` succeeds only at the package level
- importing `timesfm` fails because neither backend is present:
  - missing `jax`
  - missing `torch`

So the host still lacks a runnable TimesFM inference backend.

### 4. Real-data close-history surface is not yet wired into this runner path
The real watchlists are present, but this pass did not find a clean already-wired daily cross-sectional close-history table that can be handed directly to `steamer-card-engine-timesfm-first-run` together with real TimesFM outputs.

## Why this is still blocked
The new runner needs two things for a truthful first receipt:
1. real daily close history for a fixed universe across a bounded window
2. real TimesFM-derived scores for the same symbol-date rows

Right now, neither the TimesFM score surface nor its executable backend is available locally.

## What this does prove
- the previous blocker "no executable local substrate" is closed
- the next blocker is now sharper and honest: **model-runtime plus real-data wiring**

## Honest next move
Choose one bounded path:
1. add a supported TimesFM backend on this host, then build the smallest real-data adapter
2. generate TimesFM outputs in a separate controlled lane and import the resulting symbol-date score CSV here
3. stop the line and keep TimesFM at packet-only status until a proper model lane is approved