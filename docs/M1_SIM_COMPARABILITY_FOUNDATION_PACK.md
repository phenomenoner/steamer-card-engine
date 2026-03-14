# M1 SIM Comparability — Foundation Pack (v0)

## Purpose

This document turns the M1 plan into a **receipt-first execution pack**:

1) a baseline vs candidate **artifact inventory** (what exists / what is missing),
2) a **comparison contract v0** (what “comparable” means operationally),
3) a concrete **gap map** and **stage-ordered work packages** that can be sprinted.

This is **sim-only**. Nothing here grants live authority.

## Non‑negotiable boundary (restate)

- `steamer-card-engine` is an **adjacent productization track**, not the live Steamer execution lane.
- M1 is **contract-first** and **sim-only**:
  - allowed: `replay-sim`, `live-sim` with **simulated execution**
  - forbidden: broker order submission codepaths (any “real submit” semantics)
- **Hard stop**: if `execution_model` disclosure differs between lanes, the run is **not comparable**.

## Baseline vs candidate — artifact inventory (v0)

M1 comparability is expressed through `docs/SIM_ARTIFACT_SPEC.md` + `docs/SCENARIO_SPEC.md`.

This inventory is intentionally split into:
- **Observed baseline signals (known to exist today)** — the minimum current Steamer SIM lane already emits.
- **Required M1 artifacts** — what the M1 bundle must contain for comparison.

> Note: baseline-bot may reach “v1 bundle complete” either by **native emission** or by a **converter** that lifts legacy logs into the v1 bundle contract.

### Observed baseline signals (known today)

Baseline Steamer SIM lane is known to record at least:

- `ticks.jsonl` — market events/ticks (raw or semi-normalized)
- `decisions.jsonl` — strategy decisions / signals / context snapshots
- `orders.jsonl` — order lifecycle / broker-facing events (format varies)

These three files are the practical “always start here” baseline inventory because they exist before the v1 contract is fully enforced.

### Required M1 artifact bundle (contract)

For M1 comparison, both lanes must produce bundles conforming to:
- `SIM_ARTIFACT_SPEC.md` (bundle layout + required files)
- `SCENARIO_SPEC.md` (scenario identity + fingerprint)

At minimum, a *comparable* pair must include (see `SIM_ARTIFACT_SPEC` for exact fields):

- `run-manifest.json`
- `scenario-spec.json` (**required for M1 evidence packs**; recommended-only in base `SIM_ARTIFACT_SPEC` v1)
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

## Comparison contract v0 (operational)

### Comparator inputs

A comparison is defined over **two** run bundles:

- `baseline_bundle_dir/` (lane=`baseline-bot`)
- `candidate_bundle_dir/` (lane=`steamer-card-engine`)

Both are expected to satisfy `SIM_ARTIFACT_SPEC` v1 acceptance checks.

### Fail-fast rules (hard gates)

A comparator must fail fast (no “best effort”) if any is true:

1) **Scenario identity mismatch**
   - `scenario_id` differs, or
   - `scenario_fingerprint` differs (required for M1 evidence runs)

2) **Execution model mismatch** (hard stop)
   - any material difference in the disclosed `execution_model` fields
   - especially: `fill_model` (must be simulated in both lanes for M1)

3) **Artifact compliance failure**
   - missing required files
   - checksum mismatch vs `file-index.json`
   - schema version mismatches without explicit compatibility rules

### Comparator outputs (minimum)

The comparator produces:

- `compare-manifest.json` (metadata + pass/fail reasons)
- `summary.md` (human review)
- `diff.json` (machine diff for key metrics)

Suggested `compare-manifest.json` (minimal):

```json
{
  "compare_version": "m1-compare/v0",
  "status": "pass",
  "hard_fail_reasons": [],
  "baseline": {"run_id": "...", "lane": "baseline-bot"},
  "candidate": {"run_id": "...", "lane": "steamer-card-engine"},
  "scenario": {"scenario_id": "...", "scenario_fingerprint": "..."},
  "execution_model": {
    "baseline": {"hash": "...", "fill_model": "sim-fill-model/v1"},
    "candidate": {"hash": "...", "fill_model": "sim-fill-model/v1"}
  }
}
```

`status` is a string enum: `pass` | `fail`. If `status=pass`, `hard_fail_reasons` must be empty.

`execution_model.*.hash` should be a stable hash of the canonicalized `execution_model` disclosure from each lane’s `run-manifest.json` (so mismatch is a hard gate even before deeper diffs).

Suggested `diff.json` fields (minimum, reviewable):

- counts: fills, orders, intents, risk decisions
- per-symbol totals: traded qty, max position, entry/exit count
- exposure summary: max gross exposure, max net exposure
- exit-reason distribution (if available)
- PnL (reported, not a gate): gross / fees / taxes / net
- anomalies: by severity and category

Severity vocabulary (see `SIM_ARTIFACT_SPEC` anomalies section): `critical` | `major` | `minor` | `info`.

## Gap map (baseline-bot → v1 bundle)

This is the first “truth table” that should drive Phase 0 execution.

| v1 artifact | Baseline current source (likely) | Candidate source (M1) | Gap / notes |
|---|---|---|---|
| `run-manifest.json` | **Derived/new** (wrap day/run identity + provenance) | **New** | Must disclose capability posture and execution_model; M1 evidence requires fingerprint fields. |
| `scenario-spec.json` | **Derived/new** (ScenarioSpec chosen by operator) | **New** | Required for M1 evidence pack in both lanes. |
| `event-log.jsonl` | `ticks.jsonl` → normalized | **New** (replay runner output) | Baseline tick schema must be normalized to comparator-friendly shape. |
| `feature-provenance.jsonl` | maybe absent → derived/placeholder | **New** | For M1, a minimal feature identity log is enough; can be “no-op features” initially but must be explicit. |
| `intent-log.jsonl` | `decisions.jsonl` → intent extraction | **New** (card→intent) | Baseline “decision” semantics must map to stable `intent_id` + reason codes. |
| `risk-receipts.jsonl` | may be implicit → derived/new | **New** | If baseline has no explicit risk layer, emit a trivial `allow` receipt but keep IDs linkable. |
| `execution-log.jsonl` | `orders.jsonl` / derived exec requests | **New** | Execution requests must remain simulated; no broker submission semantics. |
| `order-lifecycle.jsonl` | `orders.jsonl` (format varies) | **New** | Need consistent lifecycle states; baseline conversion may be lossy at first but must be explicit. |
| `fills.jsonl` | baseline fill events (if any) or derived | **New** (fill model) | M1 allows simulated fills; must disclose model and seed. |
| `positions.jsonl` | derived from fills/orders | **New** | Keep simple snapshots if full transitions are hard initially. |
| `pnl-summary.json` | derived | **New** | Report-only; don’t gate M1 on PnL matching. |
| `anomalies.json` | derived/new | **New** | Must record scenario mismatch, missing ticks, checksum failures, etc. |
| `config-snapshot.json` | baseline config export / derived | **New** | Needs hashes referenced by manifest. |
| `file-index.json` | new | **New** | Required for integrity + deterministic comparison. |

### Open decision (needs a Phase 0 call)

**Baseline emits v1 directly vs converter produces v1.**

- If baseline can be made to emit v1 artifacts without destabilizing daily ops: prefer **native emission**.
- If baseline emission changes risk the daily lane: prefer a **post-close converter/landing step**.

Either way, the *output contract* is identical: v1 bundle + integrity index.

## Stage-ordered work packages (sprint-ready)

This ordering is intended to prevent a common failure mode: building “runtime” first and inventing comparability later.

Note: these stages intentionally align with the phased path in `docs/MILESTONE_M1_SIM_COMPARABILITY.md` (same order; this doc is the more execution-oriented breakdown).

### Stage 0 — Foundation (pre-sprint, serial)

**F0.1 Baseline inventory + mapping**
- write the mapping for each v1 artifact: source, derivation, known lossiness
- choose baseline strategy: native emission vs converter

**F0.2 Canonical ScenarioSpecs (evidence set seed)**
- select 3+ ScenarioSpecs (regime-diverse)
- assign stable `scenario_id`s and freeze payloads

**F0.3 Comparator skeleton (contract-first)**
- validator: required files + schema checks + `file-index` checks
- comparator: fail-fast gates + summary report shape

Exit gate:
- Baseline v1 emission strategy is chosen (native emission vs converter) and recorded.
- Comparator produces a deterministic summary diff for two pre-existing bundles (smoke test of the contract).
- A written evidence manifest exists listing canonical ScenarioSpecs, expected run paths, and comparator report filenames.

### Stage 1 — Contract freeze (schema + semantics lock)

**C1.1 Pin version strings** (`scenario-spec/v1`, `sim-artifacts/v1`)

**C1.2 ID-linkability**
- enforce chain: `event_id → intent_id → risk_decision_id → exec_request_id → order_id → fill_id → position_id`

**C1.3 Qualitative comparability rubric**
- define what must match vs can differ

**C1.4 M1 evidence strictness**
- require `scenario-spec.json` + `scenario_fingerprint` for evidence runs
- enforce `execution_model` match as a hard stop for comparison

Exit gate:
- version strings and evidence strictness rules are pinned in contract docs.
- validator rejects malformed bundles; comparator fails fast on scenario/execution_model mismatch.

### Stage 2 — Replay-sim comparable candidate lane (must come before live-sim)

**R2.1 Replay runner emits normalized events** (`event-log.jsonl`)

**R2.2 Minimal card→intent pipeline**

**R2.3 Simulated execution receipts**
- deterministic fill model + explicit `execution_model`
- capability posture stays `trade_enabled=false`

**R2.4 Artifact completeness**
- generate all required files + `file-index.json` + `config-snapshot.json`

Exit gate:
- candidate bundle passes validator for at least 1 canonical ScenarioSpec.

### Stage 3 — Live-sim attached ingestion (still simulated execution)

This stage is allowed only after Stage 2 is green.

**S3.1 Live-sim event ingestion + normalization**
- emit normalized `event-log.jsonl`

**S3.2 Capability posture enforcement**
- `trade_enabled=false` remains enforced
- execution remains **simulated** (explicit `execution_model` disclosure)
- any broker-submission semantics/signals ⇒ treat as **milestone failure**

**S3.3 Drift detection**
- detect feed drift (missing ticks / symbol gaps / out-of-order) and emit `anomalies.json`

Exit gate:
- live-sim-attached run emits a v1 bundle with explicit capability posture and explicit anomalies for feed drift.

### Stage 4 — Evidence pack acceptance (3+ scenarios)

Stage 4 is the M1 acceptance evidence pack.

**A4.1 Baseline v1 bundle production for canonical ScenarioSpecs**

**A4.2 Candidate v1 bundle production for canonical ScenarioSpecs**

**A4.3 Comparator report + human review notes**

Exit gate:
- evidence pack exists; each scenario has baseline+candidate bundles + comparator + short review note.

## Cross-links

- Milestone plan: `docs/MILESTONE_M1_SIM_COMPARABILITY.md`
- Scenario identity contract: `docs/SCENARIO_SPEC.md`
- Artifact contract: `docs/SIM_ARTIFACT_SPEC.md`
