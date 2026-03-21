# 2026-03-18 — Steamer Card Engine M1 evidence-pack acceptance (post Stage 4)

## Verdict

**M1 evidence-pack acceptance gate: closed (sim-only, contract-frozen).**

This acceptance is based on the frozen pre-sprint evidence-pack contract + the existing 3-scenario replay-sim evidence set, with Stage 4’s first `run_type=live-sim` bundle recorded as an additional milestone requirement proof (not a comparator-backed scenario pair).

## Acceptance statement (Freeze v1 contract)

I assert M1’s evidence-pack acceptance is valid only because all of the following are true:

- Scenario count proof: **>=3 distinct `scenario_id`s** exist in the replay-sim evidence set.
- Per-scenario pointers exist for baseline bundle, candidate bundle, comparator outputs, and a short review note.
- Hard gates were not bypassed:
  - scenario identity mismatch is a hard-fail
  - `execution_model` mismatch is a hard stop
- Anti-gaming rules were not violated (no relabeling baseline-normalized outputs as candidate-native; no suppressed hard-fails).
- Authority posture remains **sim-only** (`trade_enabled=false`).

## Evidence pointers

Replay-sim evidence pack (3 scenarios):
- Index: `/root/.openclaw/workspace/steamer-card-engine/docs/M1_EVIDENCE_PACK_INDEX.md`
- Acceptance contract (frozen): `/root/.openclaw/workspace/steamer-card-engine/docs/M1_EVIDENCE_PACK_ACCEPTANCE_CONTRACT.md`
- Review note: `/root/.openclaw/workspace/steamer-card-engine/docs/receipts/2026-03-15_m1-phase1-evidence-pack-3-scenarios.md`

Stage 4 live-sim-attached proof (first truthful bundle):
- Bundle dir: `/root/.openclaw/workspace/steamer-card-engine/runs/steamer-card-engine/2026-03-17/live-sim_tw-live-sim-twse-2026-03-17-full-session_candidate_20260318T005626Z/`
- Manifest truth surface (expected): `run_type=live-sim`, `capability_posture.trade_enabled=false`, `scenario_id` present, `scenario_fingerprint` present.

## Topology / authority statement

- **Topology unchanged.**
- **Authority unchanged:** still sim-only; no broker submission semantics.

## Rollback posture

If any acceptance claim is later disputed:
1. mark the sprint Stage 5 gate back to `active` in the sprint doc
2. add an explicit blocker note (what hard gate failed / what evidence was missing)
3. do **not** change runtime authority or enable new cron lanes to “manufacture” closure
