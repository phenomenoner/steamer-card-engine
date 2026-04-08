# Execution packet — steamer-card-engine market-phase gating + dashboard truth surface (planning only)

Status: **planning only / do not implement yet**

## 1) Verdict

Run this as a two-issue line with one order:

1. **Issue 1: runtime / artifact market-phase gating**
2. **Issue 2: dashboard truth surface for pre-open attempts**

Reason:
- Issue 1 is the upstream truth bug: pre-open `entry && ok` can become `execution-request` artifacts before the declared regular session.
- Issue 2 is the downstream observability bug: Mission Control currently renders those artifacts as ordinary execution evidence.

Do **not** start with dashboard cosmetics. If Issue 1 stays open, Issue 2 can only hide or relabel contaminated artifacts.

## 2) Whole-picture promise

User/operator/system outcome:
- a TW cash `full-session` run means the engine and dashboard agree on what counts as:
  - pre-open trial match evidence
  - official regular-session-open evidence
  - valid regular-session execution attempts
  - actual order lifecycle / fills

Milestone/gate being advanced:
- keep Product Sprint P1 live-capability posture honest before any stronger live-trading claim

Fake-progress risks to avoid:
- only relabeling dashboard rows while artifact emission still records pre-open attempts as normal execution requests
- only blocking pre-open rows in one presenter path while aggregate counters/timeline/detail views still treat them as regular execution evidence
- broad exchange-calendar refactors before the first verifier-backed market-phase cut exists

## 3) Recommended bounded slice

### First proving slice

Land a **readable, verifier-backed phase gate** at the replay/live-sim artifact edge before touching dashboard UX.

Smallest first slice:
1. define a minimal market-phase classifier for TW cash around the open/close
2. gate `execution-log.jsonl` emission in `sim_compare.py`
3. emit a truthful anomaly / phase note when a `full-session` bundle only has partial source coverage or pre-open entry attempts
4. only then add dashboard phase-aware rendering / filtering for historical artifacts

Why this is the right proving edge:
- it closes the real bug at the artifact source
- it is fixture-testable without live broker authority
- it gives the dashboard a better truth surface to consume later

Explicitly out of scope for the first slice:
- broker-connected live submission changes
- full TWSE microstructure modeling
- broad strategy-card schema redesign
- deep PnL/fill reconstruction for old March fixtures

## 4) Contract / boundary rules

### Issue 1 — runtime / artifact market-phase gating

Inputs:
- event rows consumed by `sim_compare.py`
- decision rows (`stage`, `ok`, `ts` / `time`, `side`, `symbol`)
- scenario/session contract (`09:00–13:30` regular session for current `full-session` TWSE posture)

Outputs:
- phase-aware execution emission behavior
- truthful anomalies or phase-state disclosures when source coverage does not match the declared session slice

Error / non-happy states:
- missing or ambiguous event timestamps
- source coverage begins before regular session or ends materially early for a `full-session` scenario
- pre-open entry attempts appear without explicit opt-in
- session/open signal is unavailable and fallback policy must remain conservative

State changes / side effects:
- artifact truth changes in `execution-log.jsonl`, possibly `anomalies.json`, and maybe manifest/summary disclosures

Invariants that must continue to hold:
- M1/P1 sim-only boundary remains intact (`trade_enabled=false` where applicable)
- no broker submission semantics are introduced
- legacy artifacts remain readable even if newly marked as phase-ambiguous or contract-violating

### Issue 2 — dashboard truth surface

Inputs:
- existing day bundles / historical artifacts
- new phase-aware artifacts once Issue 1 lands

Outputs:
- Mission Control evidence feed that does not present pre-open attempts as ordinary regular-session execution evidence

Error / non-happy states:
- historical artifacts without explicit phase fields
- partial source coverage where dashboard can only infer phase from timestamps

Invariants that must continue to hold:
- dashboard remains read-only
- timeline/detail drawers still expose raw receipts on demand
- truth is clarified, not prettified

## 5) Architecture cut

### Issue 1 likely files
- `src/steamer_card_engine/sim_compare.py`
- `tests/test_sim_compare.py`
- likely a new helper module such as:
  - `src/steamer_card_engine/market_phase.py`, or
  - `src/steamer_card_engine/session_clock.py`
- possible spec/doc follow-up:
  - `docs/SCENARIO_SPEC.md`
  - `docs/SIM_ARTIFACT_SPEC.md`
  - `docs/DAYTRADING_GUARDRAILS.md`

### Issue 2 likely files
- `src/steamer_card_engine/dashboard/aggregator.py`
- `frontend/src/App.tsx`
- `tests/test_dashboard.py`

### Files/modules not to touch in the first proving slice
- live broker adapter implementation
- operator-control arm/disarm flow
- broad auth/session capability codepaths
- unrelated dashboard gamification / styling work

## 6) Verifier plan

### Issue 1 focused tests
- add fixture tests for timestamps around the boundary:
  - `08:59:59` -> blocked / not emitted as regular execution request
  - `09:00:00` -> allowed regular-session gate open
  - `13:24:59` -> regular session
  - `13:25:00` -> final-auction phase
  - `13:30:00+` -> session closed
- add a regression test showing pre-09:00 `entry && ok` no longer increments `execution_requests`
- add a truth test for partial `full-session` source coverage disclosure

### Issue 2 focused tests
- dashboard test fixture with pre-open execution artifacts must not render them as normal execution-request evidence
- dashboard should still let an operator inspect raw payload / anomaly / phase note for historical ambiguous artifacts
- counters and timeline summaries must remain truthful after phase-aware filtering or relabeling

### Repo-root smoke expectations (for implementation phase, not now)
- `pytest -q tests/test_sim_compare.py tests/test_dashboard.py`
- one fixture-day readback showing:
  - no regular-session execution attempts before `09:00`
  - historical pre-open artifacts are visibly phase-marked or violation-marked in Mission Control

### Exact completion proof
- one checked-in receipt note showing the boundary behavior before/after on fixture day `2026-03-12`
- one topology statement confirming whether topology changed or remained unchanged

## 7) Mutation / rollback posture

Read-only or mutating:
- current packet is planning-only
- future implementation mutates repo code/docs/tests only; no external runtime authority expansion

Dry-run / plan-first path:
- this packet itself is the plan-first artifact
- start implementation only after CK re-opens the line

Idempotency expectations:
- issue packet and backlog note updates are doc-truth changes and are idempotent on retry

Smallest rollback:
- revert the planning packet + backlog updates if the line is re-cut differently

Topology changed or unchanged:
- topology unchanged for this planning pass

## 8) Delegation packet

### Worker objective
Design the smallest verifier-backed implementation cut for:
- runtime/artifact market-phase gating first
- dashboard truth surface second

### Scope boundary
- no code implementation yet
- planning only
- be explicit about file touches, verifiers, and stop-loss boundaries

### First artifact expected
- a compact issue map with:
  - file-level touch list
  - first proving slice
  - exact tests
  - open-risk list

### Stop-loss conditions
- if the plan starts requiring a broad exchange-calendar or live-broker refactor before the first proving slice exists
- if dashboard work becomes the main work before the artifact gate is specified
- if pre-open semantics cannot be stated cleanly enough to test on fixture data

### Claude CLI second-brain note
- one standalone Claude CLI planning pass was used as a bounded second-brain review
- its useful push was consistent with the chosen order:
  - fix artifact gating first
  - keep dashboard truth work as a separate defense-in-depth slice for historical artifacts

## 9) WAL closure

What durable truth changes now:
- backlog is now split explicitly into Issue 1 and Issue 2 with file-level grounding
- this execution packet freezes the planned slice order and verifier posture

Docs/spec updates required now:
- backlog note update
- this planning packet
- sprint run-journal pointer

Decision log needed?
- not yet; this is a bounded planning cut, not a product-direction change

Push receipts required?
- yes, for repo-truth planning surfaces if committed

## 10) Open risks / tradeoffs

- The biggest tradeoff is whether the first gate should infer phase from timestamps only, or wait for richer `session` / `quote` / `trade` semantics. Timestamp-first is the better first slice if it stays clearly labeled as v0.
- Historical March fixtures are already contaminated by pre-open execution attempts. The dashboard must handle them truthfully even after Issue 1 is fixed.
- `full-session` currently means `09:00–13:30` at the declared spec layer. If CK wants `08:30+` pre-open to become a first-class part of the scenario contract, that is a separate spec decision and should not be smuggled into the first bug-fix slice.
