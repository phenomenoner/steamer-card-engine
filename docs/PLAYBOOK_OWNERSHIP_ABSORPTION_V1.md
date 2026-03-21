# Steamer Card Engine — Playbook Ownership Absorption v1

Status: completed locally on 2026-03-21, not pushed

This repo now owns the Steamer card-engine product surfaces that were previously parked under `openclaw-async-coding-playbook/projects/steamer/`.

## Absorbed surfaces

- `ops/sprints/steamer-card-engine-m1-sim-comparability-sprint.md`
- `ops/sprints/steamer-card-engine-m1-stage4-live-sim-first-run-pack.md`
- `ops/sprints/steamer-card-engine-p1-live-trading-capability-v0-sprint.md`
- `ops/sprint-controllers/steamer-card-engine-m1-sim-comparability.controller.v1.yaml`
- `ops/sprint-controllers/steamer-card-engine-p1-live-trading-capability-v0.controller.v1.yaml`
- `tools/steamer_card_engine_m1_postclose_watchdog.py`
- `tools/steamer_card_engine_stage4_live_sim_first_run.py`
- `docs/tech-notes/*.md` (product-only card-engine notes imported from playbook)

## Boundary

- This repo owns the **card-engine product line** truth.
- It does **not** own the live Steamer runtime / governance truth.
- Cross-repo references into Steamer runtime now point to `StrategyExecuter_Steamer-Antigravity/projects/steamer/`.

## Topology

- topology: **changed**
- remote push: not performed
