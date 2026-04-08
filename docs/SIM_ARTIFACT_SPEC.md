# SIM Artifact Spec

## Purpose

Define a stable, comparable artifact contract for simulation runs across two lanes:

- `baseline-bot` (oracle lane)
- `steamer-card-engine` (candidate lane)

This spec is for `replay-sim` / `live-sim` outputs only. It does not grant live trading authority.

## Scope and boundary

In scope:

- run identity and folder layout
- required artifact files and minimum fields
- provenance and execution-model disclosure
- checksum/index requirements
- comparison-critical logs (risk, order lifecycle, feature provenance)

Out of scope:

- internal optimization heuristics
- private operator workflows
- broker credentials/session secrets

## Versioning and encoding

- `schema_version`: semantic string, example `"sim-artifacts/v1"`
- Text encoding: UTF-8
- Time format: ISO-8601 UTC (`YYYY-MM-DDTHH:MM:SS.sssZ`)
- Line logs: JSONL (one JSON object per line)
- Monetary values: explicit currency + numeric value (no implicit currency)

## Run folder layout

```text
runs/<lane>/<session_date>/<run_id>/
  run-manifest.json
  scenario-spec.json          # recommended in base v1; required for M1 evidence packs (see M1 comparability posture below)
  event-log.jsonl
  feature-provenance.jsonl
  intent-log.jsonl
  risk-receipts.jsonl
  execution-log.jsonl
  order-lifecycle.jsonl
  fills.jsonl
  positions.jsonl
  pnl-summary.json
  anomalies.json
  config-snapshot.json
  file-index.json
```

Repository packaging note (does not change artifact semantics):

- A required artifact path may be a symlink in the repo when its content is byte-identical to a canonical copy.
- Compliance is determined by resolved file content + `file-index.json` hashes, not by whether a path is symlinked.
- Export standalone bundles with symlink dereference to keep the archive self-contained.

### Naming rules

- `lane`: `baseline-bot` | `steamer-card-engine`
- `session_date`: exchange session date (`YYYY-MM-DD`)
- `run_id`: unique per run, recommended to include mode + scenario + timestamp

Example:

```text
runs/steamer-card-engine/2026-03-11/replay-sim_tw-gap-reclaim_20260311T060102Z/
```

## Scenario identity linkage

Scenario identity is defined by `docs/SCENARIO_SPEC.md`.

This artifact spec focuses on run outputs, but comparison reliability depends on both lanes using the same ScenarioSpec identity.

v1 posture:

- `scenario_id` remains required in `run-manifest.json`
- `scenario-spec.json` is recommended (not yet required)
- if `scenario-spec.json` is absent, ScenarioSpec-equivalent fields must stay explicit in `run-manifest.json`

M1 comparability posture (stricter than base v1):

- for M1 evidence packs, `scenario-spec.json` is **required** in both lanes
- for M1 evidence packs, `scenario_fingerprint` is **required** in `run-manifest.json`

## Required artifacts

### 1) `run-manifest.json` (required)

Canonical run identity and provenance.

Minimum fields:

- `schema_version`
- `run_id`
- `lane`
- `run_type` (`replay-sim` | `live-sim`)
- `scenario_id`
- `session_date`
- `started_at_utc`, `ended_at_utc`
- `status` (`success` | `failed` | `partial`)
- `provenance`
- `market_event_source`
- `execution_model`
- `capability_posture`
- `artifact_files` (relative paths)

Recommended (v1, for stronger cross-lane checks):

- `scenario_spec_version` (for example `"scenario-spec/v1"`)
- `scenario_fingerprint` (hash of canonical ScenarioSpec payload)
- `session_phase_contract` (explicit phase classifier contract used by the run)
- `session_phase_trace` (phase transitions observed across the normalized stream)

`provenance` minimum:

- `engine_name`
- `engine_git_sha`
- `dependency_lock_hash`
- `config_hash`
- `python_version`

`market_event_source` minimum:

- `source_id` (dataset identity/path hash)
- `timezone`
- `calendar`
- `time_range`
- `adjustment_mode`

`execution_model` minimum:

- `fee_model`
- `tax_model`
- `slippage_model`
- `rounding_rule`
- `fill_model`
- `random_seed` (nullable but explicit)

Note:
- `fill_model` must make the execution posture explicit (simulated vs anything broker-backed).
- For M1 evidence packs, `fill_model` must be a simulator (no broker submission semantics).

`capability_posture` minimum:

- `market_data_enabled` (bool)
- `trade_enabled` (bool)
- `account_query_enabled` (bool)

### 2) `event-log.jsonl` (required)

Normalized inbound market events.

Minimum per record:

- `seq_no`
- `event_id`
- `event_time_utc`
- `symbol`
- `event_type`
- `payload`

### 3) `feature-provenance.jsonl` (required)

Feature/synthesizer output identity for comparison and drift detection.

Minimum per record:

- `feature_record_id`
- `event_id` (or source window reference)
- `symbol`
- `feature_name`
- `feature_version`
- `window_spec`
- `value_hash` (or canonicalized value)
- `computed_at_utc`

### 4) `intent-log.jsonl` (required)

Card/deck intent outputs before risk/execution decisions.

Minimum per record:

- `intent_id`
- `event_id`
- `intent_time_utc`
- `card_id`
- `card_version`
- `deck_id`
- `symbol`
- `side`
- `requested_qty`
- `reason_code`

### 5) `risk-receipts.jsonl` (required)

Risk decisions applied to intents.

Minimum per record:

- `risk_decision_id`
- `intent_id`
- `decision_time_utc`
- `decision` (`allow` | `block` | `reduce` | `delay` | `force_exit`)
- `policy_scope` (`card` | `deck` | `global`)
- `policy_name`
- `reason_code`
- `adjusted_qty` (nullable)

### 6) `execution-log.jsonl` (required)

Execution requests emitted after risk decisions.

Minimum per record:

- `exec_request_id`
- `risk_decision_id`
- `request_time_utc`
- `symbol`
- `side`
- `order_type`
- `qty`
- `limit_price` (nullable)

Recommended when session truth matters:
- `time_in_force`
- `market_phase`
- `phase_semantic_label`
- `session_contract_status`
- `order_profile_name`
- `requested_user_def_suffix`
- `market_observation_state` on normalized event rows when open-discovery evidence matters

### 7) `order-lifecycle.jsonl` (required)

Order state transitions for full lifecycle comparability.

Minimum per record:

- `lifecycle_event_id`
- `exec_request_id`
- `order_id`
- `event_time_utc`
- `state` (`new` | `ack` | `partial_fill` | `filled` | `cancel_requested` | `canceled` | `replace_requested` | `replaced` | `rejected`)
- `cum_qty`
- `leaves_qty`
- `last_fill_qty` (nullable)
- `last_fill_price` (nullable)
- `reason_code` (nullable)

### 8) `fills.jsonl` (required)

Normalized fill records.

Minimum per record:

- `fill_id`
- `order_id`
- `position_id`
- `fill_time_utc`
- `symbol`
- `side`
- `qty`
- `price`
- `fee_amount`
- `tax_amount`

### 9) `positions.jsonl` (required)

Position snapshots or transitions.

Minimum per record:

- `position_event_id`
- `position_id`
- `event_time_utc`
- `symbol`
- `net_qty`
- `avg_cost`
- `position_state`
- `exit_reason` (nullable)
- `realized_pnl_gross`
- `realized_pnl_net`

### 10) `pnl-summary.json` (required)

End-of-run summary (must be net-aware).

Minimum fields:

- `currency`
- `realized_pnl_gross`
- `fees_total`
- `taxes_total`
- `realized_pnl_net`
- `entry_count`
- `exit_count`
- `exit_reason_counts`
- `win_count`
- `loss_count`
- `max_position_qty`

Semantics note:

- `entry_count` / `exit_count` are counts of **filled trades** (i.e., backed by `fills.jsonl` / `positions.jsonl`).
- For early M1 bridge bundles where `order-lifecycle.jsonl` / `fills.jsonl` / `positions.jsonl` are placeholders,
  keep `entry_count=0` and carry any decision-layer counts in extra diagnostic fields (for example:
  `entry_request_count`, `entry_signal_count`).

### 11) `anomalies.json` (required)

Structured anomalies for diagnostics.

Minimum fields:

- `anomalies` (array)
- each anomaly: `anomaly_id`, `severity`, `category`, `message`, `related_ids`, `detected_at_utc`
- `severity` values: `critical` | `major` | `minor` | `info`

### 12) `config-snapshot.json` (required)

Resolved runtime config used by this run.

Minimum fields:

- `scenario_id`
- `deck_id`, `deck_version`
- `cards` (id/version list)
- `global_config_version`
- `config_hash`

### 13) `file-index.json` (required)

Integrity index for all artifacts in the run folder.

Minimum structure:

- `schema_version`
- `run_id`
- `generated_at_utc`
- `files`: array of
  - `path`
  - `bytes`
  - `sha256`

Rule: every required artifact above must appear in `files`.

## Correlation ID guidance

To support reliable diffs, keep IDs linkable across layers:

- `event_id -> intent_id -> risk_decision_id -> exec_request_id -> order_id -> fill_id -> position_id`

## Comparator baseline requirements

At minimum, cross-lane comparison must be able to compute:

- ScenarioSpec identity match (or explicit mismatch) before behavior diffs
- first entry time/price
- final exit time/price
- fill sequence and quantities
- max position size
- exit reason distribution
- realized net PnL
- anomalies by severity/category

## Security and privacy

Artifacts must not contain:

- raw credentials, API keys, cert passwords, session tokens
- personal identifiers unrelated to run analysis

If sensitive fields are needed for debugging, store redacted values only.

## v1 acceptance checklist

A run is v1-compliant only if:

1. all required files exist
2. `run-manifest.json` and `file-index.json` pass schema checks
3. every required file has a `sha256` entry in `file-index.json`
4. intent/risk/execution/order/fill/position chain is linkable by IDs
5. `pnl-summary.json` includes gross + net fields
6. `scenario_id` is present, and if `scenario-spec.json` exists it is consistent with `run-manifest.json`
`run-manifest.json`
