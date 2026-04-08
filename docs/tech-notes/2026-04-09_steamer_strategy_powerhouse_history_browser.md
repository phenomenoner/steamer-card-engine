# 2026-04-09 — Strategy Powerhouse tab upgraded into a read-only family history browser

- repo: `steamer-card-engine`
- branch: `feat/gemini-gamify-dashboard`
- topology changed: **no**

## Verdict

The existing `Strategy Powerhouse / Strategy Cards` tab is now a smaller truthful **family history browser / research control surface** instead of only a current-proposal summary.

`Live Sim` stays intact.

## What changed

The strategy tab still stays read-only and local-artifact-backed, but each surfaced family now carries:

- current gate
- handoff state
- latest packet
- verifier history
- family timeline
- related source receipts

The browser does **not** claim broker, order, auth, or governance authority.
It remains a dashboard over local runtime-safe artifacts only.

## History sources used

Common local sources:

- `.state/steamer/card-engine-morning-paired-lane/proposed_distinct_families_20260409.json`
- `.state/steamer/card-engine-morning-paired-lane/active_deck_plan.json`
- `StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/backtests/2026-04-09_distinct_families_morning_packet.md`
- `StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/backtests/2026-04-09_distinct_families_bounded_backtest.md`
- `StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/verifiers/2026-04-09_distinct_families_synthetic_verifier.md`

Family-specific history sources where present:

- `StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/backtests/2026-04-09_tw_vcp_dryup_reclaim_blocker_surgery.md`
- `StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/backtests/2026-04-09_tw_gap_reclaim_long_param_estimate.md`

Sparse history remains explicit: if a family has no extra family-specific packet, the browser shows only the plan / packet / verifier / bounded-backtest chain that actually exists.

## How the browser now reads

### `tw_orb_reclaim_long`
- gate: `observation-ready`
- handoff: priority-1 observation proposal
- latest packet: morning packet handoff
- verifier history: synthetic verifier receipt is present, but the morning handoff still carries the family as contract-only
- timeline: proposal plan → morning packet → synthetic verifier → bounded backtest

### `tw_gap_reclaim_long`
- gate: `observation-ready`
- handoff: secondary observation proposal
- latest packet: targeted parameter estimate
- verifier history: positive-case synthetic verifier carried into the morning packet
- timeline: proposal plan → morning packet → synthetic verifier → targeted parameter estimate → bounded backtest

### `tw_vcp_dryup_reclaim`
- gate: `needs-real-trigger`
- handoff: HOLD until a recorded trigger exists beyond synthetic proof
- latest packet: blocker surgery packet
- verifier history: synthetic positive-case bridge exists
- timeline: proposal plan → morning packet → synthetic verifier → bounded backtest → blocker surgery

## API / frontend slice

No new dashboard tab was added and `Live Sim` semantics were not changed.

The existing `/api/strategy-powerhouse` surface was extended to carry:

- `metrics.history_event_count`
- `metrics.verifier_receipt_count`
- per-family `current_gate`
- per-family `handoff_state`
- per-family `latest_packet`
- per-family `verifier_history`
- per-family `family_timeline`

The frontend now renders those sections directly inside each family card.

## Verifiers / smokes

- `uv run pytest -q tests/test_dashboard.py`
- `uv run pytest -q`
- `npm run build` in `frontend/`
- API smoke via `TestClient(create_app())` confirming:
  - `tw_orb_reclaim_long_5m` latest packet = `packet`
  - `tw_gap_reclaim_long_3m` latest packet = `parameter-estimate`
  - `tw_vcp_dryup_reclaim_bounded` latest packet = `gate-analysis`
  - timeline counts render truthfully from local artifacts

## Boundary / topology statement

- still read-only
- still no broker / order / auth control
- still no governance mutation
- `steamer-card-engine` remains the execution surface
- `strategy-powerhouse` remains research / packaging / control-plane support only
- topology changed: **no**

## Remaining limits / next blade

This is still a **bounded local artifact browser**, not a generalized research warehouse.

Next useful blade if we keep pushing this line:

1. add an active-family handoff strip that truthfully shows the current active paired lane (`tw_vcp_dryup_plus_reclaim`) beside the proposal families
2. optionally dedupe/normalize family-history source discovery so future family packets can be added with less explicit path wiring
3. if the strategy-powerhouse packet cadence broadens, separate `timeline` vs `verifier-only` discovery into a thin indexed backend helper rather than hand-curated family maps
