# Steamer Card Engine M1 — Stage 4 first live-sim bundle execution pack

## Purpose

Close Stage 4 (`live-sim-attached`) by producing the **first truthful** `run_type=live-sim` v1 bundle.

This gate is **not** a ready-only gate.
`sim run-live` existing in the CLI is necessary, but not sufficient.
Stage 4 closes only when a real emitted bundle exists under `steamer-card-engine/runs/...` with explicit sim-only posture.

## Ownership

- Controller role:
  - decide when the gate is green enough to run
  - invoke the execution primitive directly or launch the bounded worker that does so
  - write sprint truth / receipts afterward
- Execution primitive owner:
  - `/root/.openclaw/workspace/steamer-card-engine/tools/steamer_card_engine_stage4_live_sim_first_run.py`
- Underlying engine command:
  - `steamer-card-engine sim run-live ...`

This preserves the controller rule (`controller != main worker`) while still giving the sprint a concrete way to finish its own milestone.

## Preconditions

- `steamer-card-engine` commit `a65d947` (or later) is present so `sim run-live` exists.
- A captured baseline dir exists under:
  - `/root/.openclaw/workspace/openclaw-async-coding-playbook/projects/trading-research/artifacts/tw-paper-sim/<session_date>/`
- That dir contains at minimum:
  - `dashboard.json`
  - `decisions.jsonl`
  - dashboard-referenced trade JSONL files reachable under `tw-trades/<session_date>/`

## Default inputs

- Engine repo:
  - `/root/.openclaw/workspace/steamer-card-engine`
- Deck:
  - `/root/.openclaw/workspace/steamer-card-engine/examples/decks/tw_cash_intraday.toml`
- Captured baseline dir:
  - `/root/.openclaw/workspace/openclaw-async-coding-playbook/projects/trading-research/artifacts/tw-paper-sim/<session_date>/`
- Output root:
  - `/root/.openclaw/workspace/steamer-card-engine/runs`

## Exact commands

### Dry-run / contract validation

```text
python3 /root/.openclaw/workspace/steamer-card-engine/tools/steamer_card_engine_stage4_live_sim_first_run.py --session-date <YYYY-MM-DD> --dry-run
```

### Emit the real Stage 4 bundle

```text
python3 /root/.openclaw/workspace/steamer-card-engine/tools/steamer_card_engine_stage4_live_sim_first_run.py --session-date <YYYY-MM-DD>
```

The helper script resolves the standard paths and calls the checked-in engine CLI with `--json` receipts.

## Expected outputs

A successful emit writes a bundle under:
- `/root/.openclaw/workspace/steamer-card-engine/runs/steamer-card-engine/<session_date>/<run_id>/`

Minimum truth surfaces expected in that bundle:
- `run-manifest.json`
- `scenario-spec.json`
- `event-log.jsonl`
- `feature-provenance.jsonl`
- `intent-log.jsonl`
- `risk-receipts.jsonl`
- `execution-log.jsonl`
- `order-lifecycle.jsonl`
- `fills.jsonl`
- `positions.jsonl`
- `pnl-summary.json`
- `anomalies.json`
- `config-snapshot.json`
- `file-index.json`

## Success receipt

The gate-moving receipt is:
- a bundle exists under `runs/steamer-card-engine/<session_date>/<run_id>/`
- `run-manifest.json` says:
  - `run_type=live-sim`
  - `capability_posture.trade_enabled=false`
  - simulator-disclosed `execution_model.fill_model`
- `scenario-spec.json` + `scenario_fingerprint` exist
- `anomalies.json` + `file-index.json` exist

Ready-only posture is **not** a success receipt for this gate.

## Rollback

If the run is noisy/ambiguous but safely sim-only:
1. do **not** widen scope or invent a new ad-hoc worker
2. keep the execution pack/helper in repo truth
3. record the blocker honestly in the sprint doc / receipts
4. if a candidate bundle is materially misleading and not referenced by receipts yet, remove just that bundle directory rather than rewriting the sprint contract

## Topology note

- **Topology unchanged.**
- This pack names the missing execution primitive; it does not add a new runtime lane by itself.
