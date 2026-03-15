# M1 Evidence Pack Index (Pre-sprint)

Date (UTC): 2026-03-15

This index is the operator-facing entrypoint for the current M1 pre-sprint evidence pack.

## Scope

- lane: replay-sim only
- authority posture: `trade_enabled=false`
- bundle contract: `sim-artifacts/v1`
- acceptance contract: `docs/M1_EVIDENCE_PACK_ACCEPTANCE_CONTRACT.md`
- packaging hygiene policy: `docs/EVIDENCE_PACKAGING_HYGIENE.md`

Packaging note:

- Some `event-log.jsonl` files are symlink-deduped when byte-identical.
- `file-index.json` content hashes remain the source of truth.
- For standalone exports, dereference symlinks (`tar --dereference`).

## Scenario set (3)

### 1) tw-paper-sim.twse.2026-03-06.full-session

- baseline bundle:
  - `runs/baseline-bot/2026-03-06/replay-sim_tw-paper-sim-twse-2026-03-06-full-session_baseline_20260315T082717Z/`
- candidate bundle:
  - `runs/steamer-card-engine/2026-03-06/replay-sim_tw-paper-sim-twse-2026-03-06-full-session_candidate_20260315T082717Z/`
- compare output:
  - `comparisons/replay-sim_tw-paper-sim-twse-2026-03-06-full-session_baseline_20260315T082717Z__replay-sim_tw-paper-sim-twse-2026-03-06-full-session_candidate_20260315T082717Z/`
- command receipts:
  - `docs/receipts/artifacts/2026-03-15_phase1_2026-03-06_normalize_baseline.json`
  - `docs/receipts/artifacts/2026-03-15_phase1_2026-03-06_replay_candidate.json`
  - `docs/receipts/artifacts/2026-03-15_phase1_2026-03-06_compare.json`
- short review note:
  - scenario id / run ids / compare status / anomaly caveat are documented in
    `docs/receipts/2026-03-15_m1-phase1-evidence-pack-3-scenarios.md`

### 2) tw-paper-sim.twse.2026-03-12.full-session

- baseline bundle:
  - `runs/baseline-bot/2026-03-12/replay-sim_tw-paper-sim-twse-2026-03-12-full-session_baseline_20260315T082719Z/`
- candidate bundle:
  - `runs/steamer-card-engine/2026-03-12/replay-sim_tw-paper-sim-twse-2026-03-12-full-session_candidate_20260315T082719Z/`
- compare output:
  - `comparisons/replay-sim_tw-paper-sim-twse-2026-03-12-full-session_baseline_20260315T082719Z__replay-sim_tw-paper-sim-twse-2026-03-12-full-session_candidate_20260315T082719Z/`
- command receipts:
  - `docs/receipts/artifacts/2026-03-15_phase1_2026-03-12_normalize_baseline.json`
  - `docs/receipts/artifacts/2026-03-15_phase1_2026-03-12_replay_candidate.json`
  - `docs/receipts/artifacts/2026-03-15_phase1_2026-03-12_compare.json`
- short review note:
  - scenario id / run ids / compare status / anomaly caveat are documented in
    `docs/receipts/2026-03-15_m1-phase1-evidence-pack-3-scenarios.md`

### 3) tw-paper-sim.twse.2026-03-10.full-session

- baseline bundle:
  - `runs/baseline-bot/2026-03-10/replay-sim_tw-paper-sim-twse-2026-03-10-full-session_baseline_20260315T082721Z/`
- candidate bundle:
  - `runs/steamer-card-engine/2026-03-10/replay-sim_tw-paper-sim-twse-2026-03-10-full-session_candidate_20260315T082721Z/`
- compare output:
  - `comparisons/replay-sim_tw-paper-sim-twse-2026-03-10-full-session_baseline_20260315T082721Z__replay-sim_tw-paper-sim-twse-2026-03-10-full-session_candidate_20260315T082721Z/`
- command receipts:
  - `docs/receipts/artifacts/2026-03-15_phase1_2026-03-10_normalize_baseline.json`
  - `docs/receipts/artifacts/2026-03-15_phase1_2026-03-10_replay_candidate.json`
  - `docs/receipts/artifacts/2026-03-15_phase1_2026-03-10_compare.json`
- short review note:
  - scenario id / run ids / compare status / anomaly caveat are documented in
    `docs/receipts/2026-03-15_m1-phase1-evidence-pack-3-scenarios.md`

## Operator notes for adding scenario #4+

1. Use a baseline source day with both `decisions.jsonl` and resolvable trade inputs.
2. Emit baseline bundle via `sim normalize-baseline` with explicit `--scenario-id`.
3. Emit candidate bundle via `replay run` with explicit `--baseline-dir` and same `--scenario-id`.
4. Run `sim compare` and require `status=pass` with zero hard-fail reasons.
5. Add pointer entries in this index + a short review note in `docs/receipts/`.
6. Confirm acceptance rules in `docs/M1_EVIDENCE_PACK_ACCEPTANCE_CONTRACT.md` still hold.

## Topology note

- This index adds operator discoverability only.
- It does not change runtime capability, trust boundary, or external dependencies.
