# Steamer dashboard tabbed surface — live sim + strategy-powerhouse (read-only)

- date: 2026-04-09
- repo: `steamer-card-engine`
- branch: `feat/gemini-gamify-dashboard`
- topology changed: **no**

## What landed

The browser dashboard is now a broader **Steamer Dashboard** with two top-level read-only tabs:

1. `Live Sim`
   - preserves the prior Mission Control semantics
   - still reads committed replay/live-sim compare fixtures
   - still exposes execution/event/phase truth from the selected fixture date

2. `Strategy Powerhouse / Strategy Cards`
   - shows research/control truth from **local artifacts only**
   - does **not** claim live execution authority
   - does **not** mutate governance or deck state
   - keeps `steamer-card-engine` as the primary execution surface and treats strategy-powerhouse as research/packaging/control support only

## Local artifact sources

The new tab reads from these local sources:

- proposal plan
  - `.state/steamer/card-engine-morning-paired-lane/proposed_distinct_families_20260409.json`
- current active plan (for proposal-vs-active truth)
  - `.state/steamer/card-engine-morning-paired-lane/active_deck_plan.json`
- morning packet
  - `StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/backtests/2026-04-09_distinct_families_morning_packet.md`
- synthetic verifier receipt
  - `StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/verifiers/2026-04-09_distinct_families_synthetic_verifier.md`
- selected card/deck manifests
  - `examples/cards/tw_vcp_dryup_reclaim_bounded.toml`
  - `examples/cards/tw_orb_reclaim_long_5m.toml`
  - `examples/cards/tw_gap_reclaim_long_3m.toml`
  - matching deck manifests under `examples/decks/`

## Surface contract

For each strategy-powerhouse card, the dashboard now shows:

- candidate id / family id / display name
- current proposal status (`hold` / `ready` / `synthetic-proven`)
- validation status and next gate when applicable
- selected parameter pack summary
- handoff readiness phrasing
- proposal state (`proposed`, not silently active)
- packet / verifier / proposal path references

## Truth boundary

This slice is intentionally read-only.

- `steamer-card-engine` remains the execution surface
- `strategy-powerhouse` remains research / packaging / control-plane support only
- the proposed distinct-family plan is surfaced as **proposal truth**, not activated truth
- no cron / launcher / runtime topology change was made

## Verifiers

- `uv run pytest -q tests/test_dashboard.py`
- `npm run build` in `frontend/`
- API smoke:
  - `/api/strategy-powerhouse` returns the three proposed families with statuses:
    - `tw_orb_reclaim_long_5m` → `ready`
    - `tw_gap_reclaim_long_3m` → `synthetic-proven`
    - `tw_vcp_dryup_reclaim_bounded` → `hold`

## Remaining limit

This tab is still a **local artifact summary**, not a generalized strategy-powerhouse runtime.
If the local research packet family changes, the dashboard source surface should be refreshed in the same pass to keep the read-only truth aligned.
