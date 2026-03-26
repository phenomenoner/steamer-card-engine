# 2026-03-26 — Backtest-loop ownership contract with Strategy Powerhouse and Mandate Framework

## Verdict

`steamer-card-engine` is now the explicit owner of the **backtest engine/product surface**.
This line is a building-block owner, not the strategy-semantic or campaign-governor owner.

## Allowed scope (this repo)

- own backtest engine contracts, lineage checks, and representative/counterfactual pack tooling
- own productization docs/sprint surfaces for the engine capability
- publish bounded validation-pack artifacts for downstream strategy interpretation

## Forbidden scope (this repo)

- do not claim final strategy promotion/demotion authority for Steamer
- do not write Steamer nightly candidate/portfolio governor truth directly
- do not absorb mandate-campaign governance/cadence authority

## Cross-line handoff contract

1. `steamer-card-engine` emits validation packs + contract receipts.
2. `strategy powerhouse` consumes and interprets those packs in the strategy experiment loop.
3. `mandate-campaign-framework` governs campaign cadence/artifact discipline around those lines.

## Cadence posture

- Engine cadence remains Product Sprint P1 (`steamer-card-engine-p1-live-trading-capability-v0`).
- Cadence changes that cross into campaign governance must be routed through mandate-campaign-framework surfaces.

## Topology verdict

- Runtime topology changed: **no**
- Scheduler topology changed: **no**
- Ownership wording changed: **yes**
- Capital/lifecycle authority broadened: **no**
