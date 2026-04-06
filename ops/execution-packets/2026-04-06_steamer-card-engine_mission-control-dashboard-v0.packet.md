# Execution packet — steamer-card-engine Mission Control Dashboard v0

## Objective

Build a **production-grade, read-only browser dashboard** for `steamer-card-engine` that visualizes daily live-sim / paired-compare artifacts as a battle report, strategy-card observability surface, and replay drilldown surface.

The opening proof is not “perfect analytics.”
The opening proof is:

> a recent AWS paired-live capture day can be opened in browser and read clearly from real artifacts.

## Authoritative inputs

- `docs/tech-notes/2026-04-06_steamer_card_engine_mission-control_dashboard_v0_build-packet.md`
- `docs/tech-notes/2026-03-20_steamer_card_engine_manual_paired_live_compare_smoke.md`
- `comparisons/manual-live-paired-20260402-entry-mode-long-one-vcp-vcp-min-trend-slope-10-tick-volume-mode-auto-feed-neoapitest-20260402T010536Z/compare-manifest.json`
- `comparisons/manual-live-paired-20260402-entry-mode-long-one-vcp-vcp-min-trend-slope-10-tick-volume-mode-auto-feed-neoapitest-20260402T010536Z/diff.json`
- `comparisons/manual-live-paired-20260402-entry-mode-long-one-vcp-vcp-min-trend-slope-10-tick-volume-mode-auto-feed-neoapitest-20260402T010536Z/summary.md`
- equivalent `20260402` slope-2 compare files
- `runs/baseline-bot/2026-04-02/...`
- `runs/steamer-card-engine/2026-04-02/...`

## Demo fixture set

Opening fixture set:
- `20260331`
- `20260401`
- `20260402`

Opening hero day:
- `20260402`

## Scope

### In scope
- React frontend
- FastAPI backend
- local read-only aggregator
- date index / date switching
- daily command view
- strategy-card leaderboard/detail
- anomaly panel
- replay/event timeline drilldown
- transaction/PnL panels with truthful empty-state contract
- local browser-openable deployment path

### Out of scope
- broker-connected controls
- write-back into Steamer/card-engine runtime
- websocket/live streaming
- operator auth redesign
- deep cross-day analytics warehouse
- fake transaction reconstruction when artifacts do not carry it

## Architecture contract

### Frontend
- React + TypeScript
- componentized production UI
- drawer-based drilldowns

### Backend
- FastAPI
- read-only REST
- normalized cached day bundle

### Data contract rule
Frontend must not directly stitch raw logs into business meaning.
The aggregator owns normalization.

## Expected artifacts

1. frontend app skeleton
2. backend app skeleton
3. aggregator module for day-bundle generation
4. read-only API routes
5. demoable daily command page for `20260402`
6. screenshot receipts
7. smoke tests
8. short runbook for local launch in browser

## Suggested file shape

- `app/` or `backend/` for FastAPI
- `frontend/` for React app
- `dashboard_data/` or `src/steamer_card_engine/dashboard/` for aggregator logic
- tests for aggregator + API

## Verifiers

### Must-pass
- app loads locally in browser
- `20260402` renders without manual file editing
- date switch among `20260331`, `20260401`, `20260402` works
- strategy-card panel opens
- replay/event detail opens
- transaction/PnL empty-state renders truthfully where data is absent

### Nice-to-have
- screenshot goldens
- loading skeletons
- stale/missing-data alert badges

## Stop-loss

Stop and report if any is true:
- same root-cause hypothesis already had 2 meaningful attempts
- no clear progress within ~10–15 minutes
- execution drifts into UI bike-shedding before core day-bundle/API artifact exists
- wrapper/tooling mechanics become the main work before a core artifact exists

Report-back format:
- where it is stuck
- what was tried
- options 1/2/3 with risk/time

## Delivery posture

- milestone-first
- demo-first
- browser-readable over architecture vanity
- no fake claims about transactions/PnL richness
- keep the first cut production-shaped, but bounded
