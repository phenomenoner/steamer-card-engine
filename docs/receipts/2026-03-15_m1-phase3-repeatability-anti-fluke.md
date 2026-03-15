# M1 Phase 3 Receipt — repeatability / anti-fluke pass

Date (UTC): 2026-03-15

## Outcome

- `status`: **done**
- Repeatability confidence improved with command receipts + deterministic compare recheck + added regression tests.

## Checks executed

### 1) `--baseline-dir` enforcement

- receipt: `docs/receipts/artifacts/2026-03-15_phase3_baseline_dir_enforcement.json`
- stderr log: `docs/receipts/artifacts/2026-03-15_phase3_baseline_dir_enforcement.err`
- result: exit code `2` with argparse-required-flag error (expected)

### 2) Scenario mismatch hard-fail

- receipt: `docs/receipts/artifacts/2026-03-15_phase3_scenario_mismatch_compare.json`
- output dir: `comparisons/phase3_mismatch_2026-03-06_vs_2026-03-12/`
- result: exit code `3`, comparator `status=fail`
- hard-fail reasons include:
  - scenario_id mismatch
  - scenario_fingerprint mismatch

### 3) Candidate provenance consistency across 3-scenario pack

- receipt: `docs/receipts/artifacts/2026-03-15_phase3_candidate_provenance_scan.json`
- result:
  - all candidate lanes = `steamer-card-engine`
  - all candidate `engine_name` = `steamer-card-engine-replay-runner`
  - all candidate `trade_enabled=false`
  - all candidate config snapshots contain emitter block

### 4) Compare replayability/auditability recheck

- receipt: `docs/receipts/artifacts/2026-03-15_phase3_compare_replayability.json`
- recheck output dir: `comparisons/phase3_recheck_2026-03-10/`
- result:
  - `compare-manifest.json` hash matches original scenario compare
  - `diff.json` hash matches original scenario compare

## Regression tests added

- file: `tests/test_sim_compare.py`
- added tests:
  - `test_sim_compare_hard_fails_scenario_mismatch`
  - `test_replay_run_requires_baseline_dir`
- test receipt: `docs/receipts/artifacts/2026-03-15_phase3_pytest.txt`
- suite result: `16 passed`

## Topology note

- No capability boundary change.
- This phase strengthens confidence/repeatability via tests and receipts only.
