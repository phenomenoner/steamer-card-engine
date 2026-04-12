# 2026-04-12 — dashboard strategy-powerhouse focus lines + architecture map

- status: done
- topology: unchanged
- scope: extend the existing Strategy Powerhouse tab so operators can see the latest research-line status and a plain-language canon flow without leaving the dashboard

## What changed
- Kept the existing top-level Steamer Dashboard tabs unchanged:
  - `Live Sim`
  - `Strategy Powerhouse / Strategy Cards`
- Extended the existing `Strategy Powerhouse` tab with three read-only dynamic sections:
  1. **架構對照表 / Canon Flow**
  2. **Current Focus Lines**
  3. **中文對照 / Glossary**

## Dynamic truth sources
The new sections are built from local artifacts on every load (no hand-wired front-end constants):
- intake-lane handoffs under `StrategyExecuter_Steamer-Antigravity/projects/steamer/handoffs/`
- failed-auction family-selection packet under `projects/steamer/research/provenance/backtests/`
- Variant 1 verifier contract / results under `projects/steamer/research/provenance/verifiers/` and `.../backtests/`
- active/proposal paired-lane plan truth already indexed by the existing dashboard path

## Why this slice
This was the smallest truthful way to surface the new strategy line and the Chinese/plain-language architecture explanation without:
- inventing a new dashboard service
- replacing the existing strategy-card history surface
- hand-maintaining a separate operator status page

## Current operator value
The tab now answers these questions directly:
- is the intake lane opened or still x_scout-only?
- has failed-auction-short been family-selected yet?
- is Variant 1 only a verifier contract, or has a real-data scan been run?
- has the line actually been handed off to steamer-card-engine live-sim/replay yet?
- what do the English lane names mean in plain Chinese?

## Files changed
- `src/steamer_card_engine/dashboard/strategy_powerhouse.py`
- `frontend/src/App.tsx`
- `tests/test_dashboard.py`
- `docs/receipts/2026-04-12_dashboard_strategy-powerhouse_focus-lines_and_architecture-map.md`

## Verification
- `uv run pytest -q tests/test_dashboard.py`
- `cd frontend && npm run build`

## Truth / boundary notes
- Read-only only; no execution or governance authority added
- Existing `Strategy Powerhouse / Strategy Cards` history surface still stands
- The new sections summarize the latest indexed local truth; they do not silently promote a research line into live-sim

## Topology statement
- no new service
- no new API family
- no scheduler/cron change
- no runtime authority change
- only a broader read-only dashboard summary surface over already-local artifacts
