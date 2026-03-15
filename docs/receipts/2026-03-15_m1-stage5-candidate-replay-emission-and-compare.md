# M1 Stage 5 Receipt — candidate replay emission path + truthful compare

Date (UTC): 2026-03-15

## Outcome

- `status`: **done**
- Stage 4 blocker is resolved at the M1 scope level:
  - `replay run` now emits a real v1 artifact bundle (candidate lane)
  - canonical compare was re-run only after a truthful candidate-emitted bundle existed

## Canonical scenario

- `scenario_id`: `tw-paper-sim.twse.2026-03-06.full-session`
- `session_date`: `2026-03-06`
- baseline source: `openclaw-async-coding-playbook/projects/trading-research/artifacts/tw-paper-sim/2026-03-06/`

## Code changes that unblock Stage 4/5

- `src/steamer_card_engine/cli.py`
  - implemented `replay run` candidate-emission path (no longer placeholder)
  - added replay flags for scenario/baseline/output/run identity control
  - added dry-run planning mode and JSON receipt output
- `src/steamer_card_engine/sim_compare.py`
  - parameterized emitter/provenance metadata so bundle emission can truthfully identify runtime origin
  - baseline normalizer behavior remains default-compatible for existing `sim normalize-baseline`
- tests
  - added replay emission + replay dry-run tests in `tests/test_sim_compare.py`
  - full test suite still green

## Artifact receipts (canonical run)

### Baseline bundle (fresh Stage 5 baseline receipt)

- `runs/baseline-bot/2026-03-06/replay-sim_tw-paper-sim-twse-2026-03-06-full-session_baseline_20260315T035401Z/`

### Candidate bundle (engine-emitted via `replay run`)

- `runs/steamer-card-engine/2026-03-06/replay-sim_tw-paper-sim-twse-2026-03-06-full-session_candidate_20260315T040424Z/`
- candidate provenance proof:
  - `run-manifest.json` → `provenance.engine_name = "steamer-card-engine-replay-runner"`

### Compare output

- `comparisons/replay-sim_tw-paper-sim-twse-2026-03-06-full-session_baseline_20260315T035401Z__replay-sim_tw-paper-sim-twse-2026-03-06-full-session_candidate_20260315T040424Z/`
- comparator result: `status = pass`
- hard-fail reasons: none

## Command evidence logs

- baseline normalize JSON receipt:
  - `docs/receipts/artifacts/2026-03-15_stage5_normalize_baseline.json`
- candidate replay-run JSON receipt (final):
  - `docs/receipts/artifacts/2026-03-15_stage5_replay_run_candidate_final.json`
- compare JSON receipt (final):
  - `docs/receipts/artifacts/2026-03-15_stage5_compare_final.json`

## Framing / honesty constraints

- This Stage 5 success is about **truthful candidate artifact emission + contract-level comparability gates**.
- It is **not** a claim of behavior parity beyond current bridge logic.
- Candidate emission still bridges legacy baseline data sources in M1; this is explicit in config/provenance and remains sim-only (`trade_enabled=false`).

## Copilot CLI review (direct one-shot lane)

- command lane: standalone `copilot -p` (non-ACP)
- review log: `docs/receipts/artifacts/2026-03-15_stage5_copilot_review.txt`
- useful feedback absorbed in-scope:
  1. removed environment-coupled baseline fallback by making `replay run --baseline-dir` required,
  2. changed candidate `config-snapshot.json` actor key from `normalizer` to `emitter` to avoid semantic drift.

## Topology decision

- **Capability changed**: `replay run` now emits candidate bundles.
- **Boundary did not change**: no live authority expansion, no broker submission path, no new external dependency.
- Topology docs were updated to reflect the new replay capability without changing authority boundaries.
