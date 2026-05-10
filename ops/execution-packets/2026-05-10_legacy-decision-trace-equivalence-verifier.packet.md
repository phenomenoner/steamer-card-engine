# Legacy decision trace equivalence verifier — blade/spec

## Goal
Build a repo-local verifier for `steamer-card-engine` that can compare legacy Steamer decision traces against card-engine compatibility card decisions across multiple recorded days.

## Boundary
- In scope: decision-trace equivalence for legacy `decisions.jsonl` rows with embedded `state` snapshots.
- First supported gates: `REV_SHORT_AFTER_UP`, `LONG_ONE_VCP`.
- Out of scope: broker execution, fills, PnL, live trading, remote push, modifying legacy bot runtime behavior.

## Inputs
- Legacy data root, default: `/workspace/CC/StrategyExecuter_Steamer-Antigravity/.data`
- Rows: `{machine}/{date}/decisions.jsonl`
- Card-engine compatibility gate params from explicit verifier defaults / optional scenario JSON.

## Outputs / artifacts
- Machine JSON summary with per-day/per-machine counts, mismatches, first divergence, reason distribution.
- JSONL mismatch sample file.
- Human-readable markdown consistency report derived from machine JSON.
- Local git commit only; no remote push.

## Invariants
- `strategy_async_original.py` remains untouched.
- Legacy repo evidence folders remain untouched.
- No files written into Hermes/Xixi A2A handoff folders.
- No broker/secrets/raw account surface access.
- Decision equality is judged before PnL/fill equivalence.

## Topology/config impact
Unchanged. This is repo-local verifier tooling and documentation only; no cron, gateway, live monitor, or runtime routing changes.

## Verifier plan
- Dry-run: run the verifier against a bounded two-day subset and inspect JSON/markdown artifacts.
- Multi-day run: run across all detected non-empty January 2026 DT3/R6 decision files.
- Counterfactual: run with intentionally wrong params and require mismatch count > 0.
- Tests: add unit tests for gate compatibility and reason/enter comparison behavior.
- Human report: generated markdown must cite machine summary path and disclose limitations.

## Rollback
Revert the local commit. Generated report artifacts are isolated under `runs/legacy-equivalence/`.
