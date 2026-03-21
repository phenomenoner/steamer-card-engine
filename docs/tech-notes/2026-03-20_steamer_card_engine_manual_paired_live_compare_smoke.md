# 2026-03-20 — Steamer card-engine manual paired live compare smoke

## Verdict

A same-day **manual paired live-compare smoke** now works for Steamer:
- current AWS baseline sim runtime can be **captured intraday** from EC2,
- captured data is **synced back to local host**,
- `steamer-card-engine` can emit both a **baseline live-sim bundle** and a **candidate live-sim bundle** from that shared capture,
- and the pair can now produce a **passing compare receipt** under a shared scenario contract.

This closes the immediate "can we manually attach card-engine to the same-day morning lane and get a truthful local compare surface?" question at the **manual smoke** level.

It does **not** yet mean:
- this is the canonical daily automation surface,
- card-engine is already a distinct alpha-producing strategy lane,
- or operator compare outputs are rich enough for decision-grade per-symbol / exposure / exit attribution.

## Why this note exists

CK's real gate was not "does M1 have more paperwork?" but:

1. can card-engine be attached to the **same-day live baseline runtime**,
2. can its data land **locally like the baseline lane**, and
3. can we get a **paired compare receipt** instead of isolated single-engine bundles.

Before this pass, the line had proof-of-life bundle receipts, but no clean same-day manual compare path against the active AWS sim lane.

## What changed

### New helper

Added a bounded operator helper:
- `projects/steamer/tools/steamer_card_engine_manual_paired_live_compare.py`

What it does:
1. uses SSM to snapshot current EC2 live-sim run dirs into a bounded manual capture,
2. stages those captures through S3,
3. syncs them back to the local host under:
   - `/workspace/steamer/.data/card-engine-manual-sync/YYYYMMDD/<stamp>/captures/...`
4. generates a **shared pair-level scenario spec** per capture,
5. emits:
   - baseline bundle under `steamer-card-engine/runs/baseline-bot/<session_date>/...`
   - candidate bundle under `steamer-card-engine/runs/steamer-card-engine/<session_date>/...`
6. runs `sim compare`,
7. writes a local JSON receipt under:
   - `/root/.openclaw/workspace/.state/steamer/manual-card-engine-paired-live/YYYYMMDD/`

### Important contract fix

The first smoke attempt produced a truthful failure:
- `scenario_fingerprint mismatch`

Root cause:
- baseline and candidate were deriving scenario identity independently,
- which made the compare fail even though both were consuming the same captured runtime stream.

Fix applied in the helper:
- generate a **shared explicit scenario-spec.json** from the synced capture,
- feed that exact same scenario spec into both baseline and candidate emission paths.

This converts the compare from "same data but mismatched scenario contract" into a truthful pair-level compare surface.

## Execution receipts

### Manual smoke receipt
- JSON receipt:
  - `/root/.openclaw/workspace/.state/steamer/manual-card-engine-paired-live/20260320/manual-paired-live-compare-20260320T012107Z.json`
- Remote capture command id:
  - `f162ca52-8a5a-4777-8d9a-b24ead8f9add`
- Local capture root:
  - `/workspace/steamer/.data/card-engine-manual-sync/20260320/20260320T012107Z`

### Active captured runs
Two active AWS sim lanes were captured and compared:
1. `ENTRY_MODE=LONG_ONE_VCP__VCP_MIN_TREND_SLOPE=10__tick_volume_mode=auto__feed=neoapitest`
2. `ENTRY_MODE=LONG_ONE_VCP__VCP_MIN_TREND_SLOPE=2__tick_volume_mode=auto__feed=neoapitest`

### Compare outputs
Both pair-level compare receipts passed:

#### slope=10
- baseline bundle:
  - `steamer-card-engine/runs/baseline-bot/2026-03-20/baseline-live-sim-entry-mode-long-one-vcp-vcp-min-trend-slope-10-tick-volume-mode-auto-feed-neoapitest-20260320T012107Z`
- candidate bundle:
  - `steamer-card-engine/runs/steamer-card-engine/2026-03-20/candidate-live-sim-entry-mode-long-one-vcp-vcp-min-trend-slope-10-tick-volume-mode-auto-feed-neoapitest-20260320T012107Z`
- compare dir:
  - `steamer-card-engine/comparisons/manual-live-paired-20260320-entry-mode-long-one-vcp-vcp-min-trend-slope-10-tick-volume-mode-auto-feed-neoapitest-20260320T012107Z`
- result:
  - `status=pass`
  - `events=44964`
  - `decisions=36905`
  - `anomalies=1`

#### slope=2
- baseline bundle:
  - `steamer-card-engine/runs/baseline-bot/2026-03-20/baseline-live-sim-entry-mode-long-one-vcp-vcp-min-trend-slope-2-tick-volume-mode-auto-feed-neoapitest-20260320T012107Z`
- candidate bundle:
  - `steamer-card-engine/runs/steamer-card-engine/2026-03-20/candidate-live-sim-entry-mode-long-one-vcp-vcp-min-trend-slope-2-tick-volume-mode-auto-feed-neoapitest-20260320T012107Z`
- compare dir:
  - `steamer-card-engine/comparisons/manual-live-paired-20260320-entry-mode-long-one-vcp-vcp-min-trend-slope-2-tick-volume-mode-auto-feed-neoapitest-20260320T012107Z`
- result:
  - `status=pass`
  - `events=44963`
  - `decisions=36905`
  - `anomalies=1`

## What this proves

It proves that the following bounded line is now real:
- same-day AWS sim runtime -> manual capture -> local sync -> paired bundle emission -> compare receipt

This is the **smallest truthful compare-capable surface** missing from the line earlier today.

## What this does NOT prove

This smoke does **not** yet prove card-engine outperforms or differs from the original trading bot in a decision-grade way.

Reason:
- current `sim run-live` bridge is still a **captured-stream bundle emitter**,
- compare output remains an **M1 comparator skeleton**,
- current compare receipts still show scaffold counts like fills/orders/intents/risk all zero for this smoke,
- rich per-symbol / exposure / exit-reason diffs remain placeholder surfaces.

So the truthful reading is:
- **pairing and local compare plumbing now works**,
- **strategy-difference reporting is still the next real gate**.

## Next recommended slice

Smallest next slice:
1. keep this helper as the manual forcing function,
2. upgrade compare output from scaffold to operator-useful diff summary,
3. define the canonical promotion rule from this manual smoke into the official same-day morning paired lane,
4. only then discuss whether card-engine is ready to be judged as a distinct strategy surface versus the baseline bot.

## Topology check

- repo truth changed: **yes**
- topology changed: **no**
- canonical cron surface changed: **no**
- runtime placement changed: **no**
- authority boundary changed: **no**

This pass adds a **manual bounded helper + receipt surface**, not a new live cron lane.
