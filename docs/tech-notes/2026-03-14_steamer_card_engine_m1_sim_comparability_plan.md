# Steamer Card Engine — M1 SIM Comparability Plan (Internal Note)

- Date (UTC): 2026-03-14
- Public reference doc (source of truth for the milestone shape):
  - `steamer-card-engine/docs/MILESTONE_M1_SIM_COMPARABILITY.md`

## Why this note exists

This is an internal continuity note tying the public `steamer-card-engine` milestone plan back to Steamer operator reality.

Key truth to preserve:
- `steamer-card-engine` remains an **adjacent productization track**.
- The daily Steamer system of record remains the **current live-sim chain**.
- M1 is a **sim-only** milestone designed to produce artifacts that are *qualitatively comparable* to the baseline bot.

## What M1 is (in one sentence)

Freeze the comparability contracts (ScenarioSpec + SIM artifact bundle), then make `steamer-card-engine` emit those artifacts for replay-sim and live-sim-attached runs, with a comparator report against baseline artifacts.

## Internal posture / authority boundary

- No live trading authority expansion.
- Default capability posture stays:
  - `market_data_enabled=true` (for sim)
  - `trade_enabled=false`
  - `account_query_enabled=false` unless explicitly required for a sim-only inspection path

If any run is missing identity/contracts/checksums: mark `failed/partial` and emit anomalies; do not “best-effort” into acceptance.

## Serial-first then sprint-driven

CK’s intended execution shape:

1) **Serial foundation (pre-sprint)**
   - baseline artifact inventory + mapping plan to `SIM_ARTIFACT_SPEC`
   - canonical ScenarioSpec set (3+ scenarios) for the M1 evidence pack
   - validator + comparator skeleton (contract-first)

2) **Sprint milestone (implementation)**
   - replay runner + artifact emission in candidate lane
   - live-sim-attached ingestion (still sim-only)
   - evidence pack runs + comparator reports

## Acceptance evidence expectations (operator-facing)

M1 acceptance should produce an “evidence pack” (stored artifacts + short review notes) containing:

- baseline-bot bundles (v1-compliant; include `scenario-spec.json` + `scenario_fingerprint`)
- steamer-card-engine bundles (v1-compliant; include `scenario-spec.json` + `scenario_fingerprint`)
- comparator reports
- per-scenario human review notes (qualitative parity, anomaly explanations)

## Risk / rollback posture

- Nothing in this plan changes daily operations.
- If M1 work causes confusion about authority boundaries, treat that as a regression:
  - tighten docs language
  - tighten default capability posture
  - remove/disable any CLI that could be misread as live-authority

## Cross-reference

- Internal seed note (what is already true about the public repo’s boundary):
  - `TECH_NOTES/2026-03-11_steamer_card_engine_seed_internal_note.md`

## Sprint/controller pack (internal control surface)

This plan is now instantiated as a doc-driven sprint-controller pack (docs-first; no cron provisioning by default):

- Sprint doc:
  - `/root/.openclaw/workspace/steamer-card-engine/ops/sprints/steamer-card-engine-m1-sim-comparability-sprint.md`
- Controller config:
  - `/root/.openclaw/workspace/steamer-card-engine/ops/sprint-controllers/steamer-card-engine-m1-sim-comparability.controller.v1.yaml`
- Pack tech note:
  - `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-14_steamer_card_engine_m1_sprint-controller-pack.md`
