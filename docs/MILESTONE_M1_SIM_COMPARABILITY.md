# Milestone M1 — SIM Comparability (Replay + Live-Sim Artifacts)

## What this milestone is

`M1` is the first **bounded, sim-only** milestone for `steamer-card-engine`.

Goal: make `steamer-card-engine` able to run Steamer **SIM tests** (replay-sim first, then market-data-attached live-sim with **simulated execution**) and produce **recording/sim artifacts** that are *qualitatively comparable* to the current Steamer baseline bot.

This milestone is intentionally **not** about matching ticks perfectly or achieving PnL parity. It is about producing **trustworthy receipts** (events → features → intents → risk → execution → lifecycle → fills/positions) so a human can review diffs and say: “this candidate run is the same kind of behavior on the same scenario.”

## Boundary (non-negotiable)

- `steamer-card-engine` is an **adjacent productization track**, not the live Steamer execution lane.
- **Sim-only authority**:
  - replay-sim and live-sim are allowed
  - live trading is **out of scope**
  - default posture must remain `trade_enabled=false` (see `docs/SIM_ARTIFACT_SPEC.md` capability posture)

## Definition of done (success criteria)

M1 is complete when all are true:

1. **Contract freeze is real**
   - `docs/SCENARIO_SPEC.md` + `docs/SIM_ARTIFACT_SPEC.md` are treated as stable contracts for M1 (versioned, with explicit acceptance checks).

2. **Candidate lane produces v1-compliant artifacts**
   - For `run_type=replay-sim`, `steamer-card-engine` emits the required artifact bundle defined by `docs/SIM_ARTIFACT_SPEC.md`.
   - Bundles include provenance (`engine_git_sha`, lock hash, config hash) and checksums (`file-index.json`).

3. **Baseline lane is comparable via the same artifact contract**
   - There exists a repeatable way to produce a **baseline-bot** bundle in the same artifact format (either native emission or a converter).
   - The baseline lane is treated as an **oracle lane** for qualitative review, not a “specification of implementation quirks.”

4. **Comparator produces a reviewable diff report**
   - A comparator can:
     - fail fast on ScenarioSpec mismatch
     - validate v1 artifact compliance
     - generate a summary diff across key fields (fills, positions, entry/exit timing, max exposure, anomaly categories)

5. **Evidence set exists (canonical scenarios)**
   - At least **3 scenarios** (different regimes) are run in both lanes and archived as the M1 evidence set.

6. **Evidence runs are strictly comparable**
   - For the M1 evidence pack, both lanes include `scenario-spec.json` and `scenario_fingerprint` (hard requirement for M1, even if base v1 contracts mark them as “recommended”).
   - If `execution_model` semantics differ between lanes, the run is **not comparable** and must be treated as a hard stop (no behavioral review).

## Explicit non-goals

- Live trading, broker connectivity, or “arm/disarm” operator workflows
- Tick-perfect event parity between lanes
- Exact fill-by-fill matching
- PnL parity (gross/net) as a pass/fail gate
- Multi-broker portability
- Performance optimization beyond “reasonable for offline replay”
- Any claim of runtime parity, production readiness, or broker-execution fidelity

## Phased path (serial foundation → sprint milestone)

This plan is deliberately ordered to avoid “build runtime first, then invent comparability.”

### Phase 0 — Foundation (serial, pre-sprint)

**Goal:** make comparability *possible* before writing runtime.

Execution pack (recommended starting point):
- `docs/M1_SIM_COMPARABILITY_FOUNDATION_PACK.md`

Work packages:

- **F0.1: Baseline artifact inventory**
  - Identify what the baseline bot already records (ticks/decisions/orders), and what must be transformed to fit `SIM_ARTIFACT_SPEC`.
  - Decide: baseline emits v1 directly vs a converter produces v1.

- **F0.2: Canonical scenario set**
  - Choose 3+ ScenarioSpecs (days + slices + symbol sets) to serve as the M1 evidence set.
  - Record ScenarioSpec payloads and assign stable `scenario_id`s.

- **F0.3: Comparator acceptance harness skeleton**
  - Implement (or stub) the following *separately from runtime*:
    - artifact validator: required files + schema checks + checksum checks
    - diff report generator: baseline vs candidate comparisons

Gate (Phase 0 exit):

- A written “M1 contract pack” exists:
  - ScenarioSpec(s)
  - artifact spec acceptance checklist
  - comparator expected output shape

Receipts:

- ScenarioSpec JSON files stored as fixtures (or referenced by stable hashes)
- Comparator produces a deterministic summary for two pre-existing bundles
- A frozen **evidence manifest** listing canonical ScenarioSpecs, expected artifact paths, and comparator report filenames

Current implementation receipt (2026-03-14):
- CLI added: `sim normalize-baseline` and `sim compare`.
- Baseline conversion currently focuses on honest normalization + placeholders where legacy artifacts lack order/fill/position detail.
- Comparator now hard-fails on `execution_model` mismatch and emits scaffold compare outputs.
- First replay-sim comparability plumbing receipt is now archived (same-source baseline/candidate normalization; validates gates/reporting wiring):
  - note: `docs/receipts/2026-03-14_m1-stage3-first-replay-sim-comparable.md`
  - comparator: `comparisons/replay-sim_tw-paper-sim-twse-2026-03-06-full-session_baseline_20260314T200700Z__replay-sim_tw-paper-sim-twse-2026-03-06-full-session_candidate_20260314T200700Z/summary.md`
- Stage 4 candidate-engine-emitted attempt is now receipted as a blocker: replay CLI/runtime still does not emit a candidate v1 bundle path (`replay run` remains placeholder), so Stage 4 compare could not be run honestly.
  - note: `docs/receipts/2026-03-14_m1-stage4-candidate-engine-emitted-blocker.md`
- Stage 5 unblocked the candidate emission path: `replay run` now emits a truthful v1 candidate bundle with candidate runtime provenance, and canonical compare has been re-run on `tw-paper-sim.twse.2026-03-06.full-session`.
  - note: `docs/receipts/2026-03-15_m1-stage5-candidate-replay-emission-and-compare.md`

### Phase 1 — Contract freeze (schema + semantics lock)

**Goal:** freeze the *interfaces* so runtime work cannot drift.

Work packages:

- **C1.1: Pin schema versions**
  - `scenario-spec/v1`
  - `sim-artifacts/v1`

- **C1.2: ID-linkability rules**
  - enforce the chain: `event_id → intent_id → risk_decision_id → exec_request_id → order_id → fill_id → position_id`

- **C1.3: “Qualitative comparability” rubric**
  - define what must be “close” vs what may differ (see Acceptance gates below)

- **C1.4: M1 evidence strictness**
  - require `scenario-spec.json` + `scenario_fingerprint` for evidence runs
  - require matching `execution_model` disclosure for comparisons

Gate (Phase 1 exit):

- Contract docs are updated with:
  - stable version strings
  - acceptance checklist references
  - comparator baseline requirements (already partly present in `SIM_ARTIFACT_SPEC`)

Receipts:

- `schemas/` or JSONSchema snapshots (optional but recommended)
- validator CLI/test that rejects malformed bundles

### Phase 2 — Replay-comparable candidate lane (replay-sim)

**Goal:** candidate engine can replay a scenario and emit v1 artifacts.

Work packages:

- **R2.1: Replay runner reads normalized market events**
  - input: a canonical event stream for a ScenarioSpec
  - output: `event-log.jsonl` plus run envelope

- **R2.2: Minimal card → intent pipeline**
  - implement one replay-only card path that emits intents deterministically

- **R2.3: Risk receipts + execution model (simulated)**
  - risk layer emits receipts (allow/block/reduce) even if initially simple
  - execution emits lifecycle and fills via a deterministic fill model

- **R2.4: Artifact completeness**
  - generate all required files + `file-index.json` + `config-snapshot.json`

Gate (Phase 2 exit):

- For at least 1 ScenarioSpec, candidate lane produces a **v1-compliant** bundle and passes validator.

Receipts:

- `runs/steamer-card-engine/<date>/<run_id>/...` bundles for at least one scenario
- validator output logs

### Phase 3 — Market-data-attached live-sim (execution still simulated)

**Goal:** candidate lane can attach to a live-sim market feed and still produce comparable artifacts.

Work packages:

- **S3.1: Live-sim event ingestion**
  - consume the live-sim market event source
  - write the same normalized `event-log.jsonl`

- **S3.2: Capability posture enforcement**
  - `trade_enabled=false` remains enforced
  - run-manifest declares capability posture explicitly
  - execution remains **simulated** (disclosed in `execution_model` fields)

- **S3.3: Drift detection**
  - detect missing ticks / symbol gaps / out-of-order events
  - emit `anomalies.json` with severity categories

Gate (Phase 3 exit):

- Live-sim-attached run produces a v1-compliant bundle with explicit capability posture.

Receipts:

- Live-sim run bundles + anomaly summaries

### Phase 4 — Milestone acceptance (evidence pack)

**Goal:** demonstrate qualitative comparability on canonical scenarios.

Acceptance gates:

- **A4.1: Scenario identity match**
  - same `scenario_id` / matching ScenarioSpec fingerprint (or explicit mismatch that fails fast)

- **A4.2: Artifact compliance**
  - both lanes pass the v1 acceptance checklist (see `SIM_ARTIFACT_SPEC`)

- **A4.3: Comparator report is reviewable**
  - produces:
    - entry/exit summary (time/price)
    - fill sequence summary (counts, qty totals)
    - max exposure
    - exit reason distribution
    - net PnL (reported, not a hard gate)
    - anomaly diff
  - all diffs must be traceable via the ID chain (event → intent → risk → exec → order → fill → position)

- **A4.4: Minimum comparability rubric (loose thresholds)**
  - Scenario identity and execution-model disclosure match are hard requirements (see A4.1).
  - Default starting thresholds (tunable per scenario, but must be recorded in the review note):
    - first-entry **side** matches per symbol (or is explicitly explained)
    - total traded qty per symbol is within a broad band (example: 0.5×–2× baseline)
    - max position size is within a broad band (example: 0.5×–2× baseline)
    - exit-reason family (stop/take-profit/time/forced-exit) is consistent or explained
    - no `critical` anomalies remain “unclassified”

- **A4.5: Qualitative parity judgment**
  - human review signs off that behavior is “the same class” for M1:
    - intent cadence and direction are plausible
    - risk decisions are explainable
    - lifecycle and fills are coherent
  - review notes should minimally include: `scenario_id`, baseline run_id, candidate run_id, the thresholds used, and anomaly explanations

Receipts:

- Evidence pack containing:
  - baseline bundles + candidate bundles
  - comparator reports
  - short written review notes per scenario

## Risk posture / rollback stance

- M1 introduces **no live authority**.
- M1 must not exercise broker **order submission** codepaths; any such activation is milestone failure.
- All runs must declare `capability_posture` explicitly.
- If any ambiguity is detected (ScenarioSpec mismatch, missing files, checksum mismatch):
  - mark the run as `status=failed` or `partial`
  - emit `anomalies.json`
  - do not silently “best-effort” into a pass

## Cross-links

- Scenario identity contract: `docs/SCENARIO_SPEC.md`
- Artifact contract + acceptance checklist: `docs/SIM_ARTIFACT_SPEC.md`
- Migration sequencing context: `docs/MIGRATION_PLAN.md`
