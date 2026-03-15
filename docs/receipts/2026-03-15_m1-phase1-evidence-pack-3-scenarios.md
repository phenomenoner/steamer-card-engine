# M1 Phase 1 Receipt — evidence-pack expansion to 3 scenarios

Date (UTC): 2026-03-15

## Outcome

- `status`: **done**
- M1 evidence pack now has **3 truthful replay-sim scenarios** with baseline bundle, candidate bundle (engine-emitted via `replay run`), comparator output, and short review notes.

## Scenario selection rationale (succinct)

To avoid fake breadth while still stress-testing the M1 lane, the 3-scenario set intentionally spans different event-volume regimes from the same TW paper-sim source family:

1. `2026-03-06` — sparse day (`~2k` events)
2. `2026-03-12` — mid-volume day (`~21k` events)
3. `2026-03-10` — higher-volume day (`~171k` events)

All three have `decisions.jsonl` + valid dashboard-referenced trade sources, so candidate replay emission remains truthful (no synthetic scenario fabrication).

## Per-scenario receipts + review notes

### Scenario A (anchor)

- `scenario_id`: `tw-paper-sim.twse.2026-03-06.full-session`
- baseline normalize receipt: `docs/receipts/artifacts/2026-03-15_phase1_2026-03-06_normalize_baseline.json`
- candidate replay receipt: `docs/receipts/artifacts/2026-03-15_phase1_2026-03-06_replay_candidate.json`
- compare receipt: `docs/receipts/artifacts/2026-03-15_phase1_2026-03-06_compare.json`
- path index: `docs/receipts/artifacts/2026-03-15_phase1_2026-03-06_paths.env`
- compare output dir:
  - `comparisons/replay-sim_tw-paper-sim-twse-2026-03-06-full-session_baseline_20260315T082717Z__replay-sim_tw-paper-sim-twse-2026-03-06-full-session_candidate_20260315T082717Z/`
- short review note:
  - comparator `status=pass`, no hard-fail reasons
  - baseline/candidate intent and risk counts match (`intents=200`, `risk=100`)
  - both bundles expose one known minor anomaly: `baseline-orders-missing` (truthfully carried forward)

### Scenario B

- `scenario_id`: `tw-paper-sim.twse.2026-03-12.full-session`
- baseline normalize receipt: `docs/receipts/artifacts/2026-03-15_phase1_2026-03-12_normalize_baseline.json`
- candidate replay receipt: `docs/receipts/artifacts/2026-03-15_phase1_2026-03-12_replay_candidate.json`
- compare receipt: `docs/receipts/artifacts/2026-03-15_phase1_2026-03-12_compare.json`
- path index: `docs/receipts/artifacts/2026-03-15_phase1_2026-03-12_paths.env`
- compare output dir:
  - `comparisons/replay-sim_tw-paper-sim-twse-2026-03-12-full-session_baseline_20260315T082719Z__replay-sim_tw-paper-sim-twse-2026-03-12-full-session_candidate_20260315T082719Z/`
- short review note:
  - comparator `status=pass`, no hard-fail reasons
  - higher event volume than anchor (`events=21002`) still emits truthful candidate bundle with matching scenario fingerprint
  - same known minor baseline limitation (`baseline-orders-missing`) remains explicit

### Scenario C

- `scenario_id`: `tw-paper-sim.twse.2026-03-10.full-session`
- baseline normalize receipt: `docs/receipts/artifacts/2026-03-15_phase1_2026-03-10_normalize_baseline.json`
- candidate replay receipt: `docs/receipts/artifacts/2026-03-15_phase1_2026-03-10_replay_candidate.json`
- compare receipt: `docs/receipts/artifacts/2026-03-15_phase1_2026-03-10_compare.json`
- path index: `docs/receipts/artifacts/2026-03-15_phase1_2026-03-10_paths.env`
- compare output dir:
  - `comparisons/replay-sim_tw-paper-sim-twse-2026-03-10-full-session_baseline_20260315T082721Z__replay-sim_tw-paper-sim-twse-2026-03-10-full-session_candidate_20260315T082721Z/`
- short review note:
  - comparator `status=pass`, no hard-fail reasons
  - high-volume input (`events=170851`) still preserves candidate provenance and comparability gates
  - same known minor baseline limitation (`baseline-orders-missing`) remains explicit

## Topology note

- **No topology/capability boundary change in Phase 1**.
- This phase expands evidence receipts only; no new live authority, external dependency, or runtime boundary shift.

## Definition-of-done check (Phase 1)

- ✅ 3-scenario evidence pack exists (anchor + 2 additional truthful scenarios)
- ✅ each scenario has baseline bundle + candidate-emitted bundle + compare output + short review note
- ✅ docs updated with receipt pointers in this same pass
