# 2026-03-14 — Steamer Card Engine M1 sprint-controller pack (internal)

## Purpose

Instantiate the doc-driven sprint controller framework for the **Steamer Card Engine M1 SIM comparability** milestone.

This pack is an internal control surface only:
- it does **not** change daily Steamer operations
- it does **not** provision cron jobs by default
- it exists to keep stage order / gates / evidence targets explicit and auditable

## Public source of truth (milestone plan)

- `steamer-card-engine/docs/MILESTONE_M1_SIM_COMPARABILITY.md`

Execution foundation pack (public, receipt-first):
- `steamer-card-engine/docs/M1_SIM_COMPARABILITY_FOUNDATION_PACK.md`

## Boundary truth to preserve

- `steamer-card-engine` is an **adjacent productization track**, not the live Steamer lane.
- M1 is **sim-only** and **contract-first**.
- Replay-comparable comes **before** market-data-attached live-sim.
- `execution_model` mismatch is a **hard stop** for comparison.
- Broker order submission codepaths must **not** be exercised for M1.

## Controller artifacts (this repo)

- Sprint doc:
  - `/root/.openclaw/workspace/steamer-card-engine/ops/sprints/steamer-card-engine-m1-sim-comparability-sprint.md`
- Controller config (framework v1 surface):
  - `/root/.openclaw/workspace/steamer-card-engine/ops/sprint-controllers/steamer-card-engine-m1-sim-comparability.controller.v1.yaml`

## Intended usage

- Treat the sprint doc as the single “what stage are we in?” scorecard.
- When a stage gate flips, update:
  - sprint doc scorecard + journal
  - relevant public docs if the contract changes (rare; should be treated as a boundary event)
  - `projects/steamer/topology-pack-l0.md` if topology truth changes

## Status update (2026-03-15)

- The sprint pack is no longer just seeded; it is now arranged as an **active doc-driven sprint pack**.
- See activation/update note:
  - `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-15_steamer_card_engine_m1_sprint-activation-pack.md`
- Proposed controller cron specs now exist as scaffolded repo truth, but remain **disabled** until explicit approval.

## Non-goals

- No attempt to auto-run or auto-enable jobs.
- No operator runbook copy/paste into public docs.
- No posture drift toward live trading.
