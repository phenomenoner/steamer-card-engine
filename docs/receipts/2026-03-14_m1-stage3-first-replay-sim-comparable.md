# M1 Stage 3 Receipt — first replay-sim comparable run

Date (UTC): 2026-03-14

## Canonical scenario used

- `scenario_id`: `tw-paper-sim.twse.2026-03-06.full-session`
- `session_date`: `2026-03-06`
- baseline source: `openclaw-async-coding-playbook/projects/trading-research/artifacts/tw-paper-sim/2026-03-06/`

Selection rationale: this day has complete baseline inputs (`decisions.jsonl` + dashboard-referenced trade files) with relatively small event volume (`lines_total=2170`), so it is the cleanest first comparability receipt candidate.

## Output artifacts

- baseline bundle:
  - `runs/baseline-bot/2026-03-06/replay-sim_tw-paper-sim-twse-2026-03-06-full-session_baseline_20260314T200700Z/`
- candidate bundle:
  - `runs/steamer-card-engine/2026-03-06/replay-sim_tw-paper-sim-twse-2026-03-06-full-session_candidate_20260314T200700Z/`
- comparator output:
  - `comparisons/replay-sim_tw-paper-sim-twse-2026-03-06-full-session_baseline_20260314T200700Z__replay-sim_tw-paper-sim-twse-2026-03-06-full-session_candidate_20260314T200700Z/compare-manifest.json`
  - `comparisons/replay-sim_tw-paper-sim-twse-2026-03-06-full-session_baseline_20260314T200700Z__replay-sim_tw-paper-sim-twse-2026-03-06-full-session_candidate_20260314T200700Z/diff.json`
  - `comparisons/replay-sim_tw-paper-sim-twse-2026-03-06-full-session_baseline_20260314T200700Z__replay-sim_tw-paper-sim-twse-2026-03-06-full-session_candidate_20260314T200700Z/summary.md`

## Comparator result

- status: `pass`
- hard fail reasons: none
- scenario fingerprint: matched
- execution_model hash: matched (`a2a2587964a530fc8b683e6bcb13009fc14dbd65e40ce80f16661f35a91743fc`)

## Framing (important)

This is a **plumbing receipt**, not a two-engine behavior-parity receipt yet:

- baseline lane and candidate lane were both produced by the same normalizer (`sim normalize-baseline`) from the same legacy baseline source directory.
- therefore this pass validates contract/gate/report wiring, not runtime behavior divergence.

## What this first receipt teaches

1. The M1 hard gates are actually live: scenario identity + execution_model mismatches would block compare; this run passed because both were aligned.
2. Comparator/report plumbing is now real for replay-sim evidence (`compare-manifest.json`, `diff.json`, `summary.md`) instead of planning-only.
3. Baseline artifacts still lack `orders.jsonl`, so both lanes carry one minor anomaly (`baseline-orders-missing`) and placeholder order/fill/position outputs.
4. Provenance still has explicit debt (`engine_git_sha="unknown"`, `dependency_lock_hash="unknown"`) and compare-manifest bundle paths are absolute; these need tightening before stronger acceptance claims.
