# 2026-04-15 — steamer-card-engine broker-preflight readiness blade map

## Whole-picture promise

Give the future trading-day smoke cron a truthful entry gate for broker-preflight readiness, without pretending the repo is already broker-connected.

## Bounded slice

Add a seed `operator preflight-smoke` surface that:
- reads logical session posture
- reads operator baseline posture
- applies trading-day gate
- returns `ready` or `blocked` with explicit blockers

## Non-goals

- no real broker login or attach
- no market-data socket attach
- no cron activation in this slice
- no live-order execution

## Verifier plan

- `uv run pytest -q tests/test_cli.py`
- manual JSON smoke for `operator preflight-smoke`
- docs/README/CLI_SPEC/TOPOLOGY coherence pass

## Activation truth

Prepared-only. This slice defines the cron entry gate; it does not activate a trading-day cron and does not remove broker-not-connected blockers.
