# Steamer Card Engine — Product Sprint P1 / Live Trading Capability v0

## Sprint goal / milestone

Make **Live Trading Capability v0** operator-credible and reportable for `steamer-card-engine`.

This sprint exists because `steamer-card-engine` is not only a Steamer-internal adjacent track.
It is also a product line we intend to push outward.

The question for this sprint is:

> can the product earn a guarded live-capability posture without lying about safety, permissions, or operator control?

## Current rollout policy

- Overall posture: **active sprint, scaffold-first**
- Controller posture: **doc-driven sprint controller pack scaffolded**
- Live controller jobs: **progress pass enabled; handoff pass scaffolded/disabled**
- Rollout mode: **staged / docs-first**
- Execution posture: **forward-mandatory inside approved gates**
- Report posture: ordinary progress stays in sprint truth; important decisions report immediately
- Ordered stages:
  1. `capability-posture-contract`
  2. `operator-control-contract`
  3. `bounded-live-path-contract`
  4. `reportable-p1`

Boundary note:
- current M1 remains closed under its written contract
- Sprint A owns pair-contract coupling for Steamer strategy work
- this sprint owns guarded product live-capability posture only
- backtest engine/product ownership belongs to this line; strategy interpretation and campaign cadence do not
- no unrestricted live-authority expansion is implied

## Execution contract / forcing move

This sprint is a **ready-only contract sprint**.

The milestone closes when repo truth contains a coherent, operator-usable P1 pack:
- explicit capability posture states
- explicit operator control contract
- explicit bounded live path contract
- reportable docs/receipts tying the above into product/runtime topology

Current forcing move:
- `stage-4 reportable-p1` is closed; maintain pack coherence and prep for operator handoff.

## Path audit + best-case timing

Connectivity verdict: **connected**.

Why it connects:
- product docs already define the main safety boundaries
- M1 already proved the sim-only artifact/product contract layer
- the next bounded product edge is guarded live capability rather than a broad rewrite

Best-case timing map:
- `capability-posture-contract` -> **0.5-1 good active day**
- `operator-control-contract` -> **0.5-1 good active day**
- `bounded-live-path-contract` -> **0.5-1 good active day**
- `reportable-p1` -> **0.5-1 good active day**
- fastest plausible finish -> **~2-4 calendar days**

Launching user:
- **CK**

Launch confirmation meaning:
- CK accepted that product live-trading capability should advance as an adjacent line without fighting Sprint A.

## Lane / stage scorecard

| Stage | Status | Hard gate | Evidence pointer |
|---|---|---|---|
| stage-0-bootstrap | done | sprint pack exists in repo truth | `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-19_steamer_card_engine_p1_live-trading-capability_v0_sprint-pack.md` |
| stage-1-capability-posture-contract | done | product states between sim-only and live-capable are explicit and operator-inspectable | this sprint doc + `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-19_steamer_card_engine_p1_stage1_capability-posture-contract.md` |
| stage-2-operator-control-contract | done | status / arm / disarm / flatten surfaces are explicitly bounded | `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-19_steamer_card_engine_p1_stage2_operator-control-contract.md` + `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-30_steamer_card_engine_p1_bounded-live-smoke_operator-control_seed-implementation.md` |
| stage-3-bounded-live-path-contract | done | one guarded path from current product state to bounded live capability is explicit | `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-20_steamer_card_engine_p1_stage3_bounded-live-path-contract.md` |
| stage-4-reportable-p1 | done | the slice reads as one coherent product live-capability line | this sprint doc + supporting tech notes |

## Current blockers / risks

- The main risk is **fake readiness**: product docs can sound live-ready before capability, operator control, and guardrails are explicitly connected.
- The second risk is **milestone collision**: if Sprint A and Product Sprint P1 are allowed to own the same gate, both lines will drift and fake progress.
- The third risk is **authority ambiguity**: if auth/session posture does not visibly state `trade_enabled`, live-capability claims become unsafe theater.
- The fourth risk is **market-phase ambiguity at the open**: current repo truth does not yet operationalize 盤前試搓 vs 正式開盤 semantics, pre-open order-style restrictions, or full-session coverage validation; see `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-04-08_steamer_card_engine_market-phase-gating-gap_backlog.md` and planning packet `/root/.openclaw/workspace/steamer-card-engine/ops/execution-packets/2026-04-08_steamer-card-engine_market-phase-gating-and-dashboard-truth.packet.md`.

## Allowed auto-actions

The controller may:
- update this sprint doc
- sync related `STATUS.md`, `topology-pack-l0.md`, and tech notes when repo truth changed
- append concise durable notes to `memory/YYYY-MM-DD.md`
- run docs cold-lane ingest after material operator-doc changes
- prepare rollout / rollback / observation checklists
- scaffold the next bounded execution-pack or helper spec once the contract stages make that truthful
- launch or continue the next bounded in-scope doc/contract move inside the declared stage order

It may **not**:
- redefine the milestone without approval
- bypass stage order
- widen P1 into broad production-readiness claims
- pretend operator-governed live control is already implemented if the contract is not explicit
- claim ownership of Sprint A's pair-contract problem
- turn the controller into the main coding worker

## Escalate-to-human conditions

Report immediately only if:
1. milestone definition needs to change
2. the live-capability cut is genuinely ambiguous
3. rollback is needed and the clean path is unclear
4. a safety hazard or forbidden execution path appears
5. repeated failures suggest the sprint should pause or be re-cut
6. the next useful move widens scope materially beyond Product Sprint P1

## Docs / topology / memory sync checklist

When durable truth changes, update in the same pass:
- this sprint doc
- relevant `STATUS.md` / `topology-pack-l0.md` / tech notes
- push receipts for changed repos
- docs cold-lane ingest if operator-facing docs changed materially
- `memory/YYYY-MM-DD.md`

If topology does **not** change, say so explicitly in the receipt.

## Captain / handoff block

Current sprint read:
- M1 is closed under its written contract
- Product Sprint P1 is now the next bounded productization edge for `steamer-card-engine`
- this line is intentionally separate from Sprint A and must not fight it
- ownership split contract note: `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-26_backtest-loop-ownership-contract_with_strategy-powerhouse_and_mandate-framework.md`
- immediate forcing move: `stage-4 reportable-p1` is closed; maintain pack coherence and prep handoff

## Run journal

- 2026-03-19 — sprint pack scaffolded after CK approved running A+B in parallel without collision.
- 2026-03-19 — one live progress manager was provisioned for Product Sprint P1 (`ac9002f2-f086-4ee1-8fb3-de222b4e7d67`); handoff remains scaffolded.
- 2026-03-19 — stage-1 capability posture ladder contract note added (no topology change): `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-19_steamer_card_engine_p1_stage1_capability-posture-contract.md`.
- 2026-03-19 — stage-1 `capability-posture-contract` marked **done**; stage-2 `operator-control-contract` activated.
- 2026-03-19 — stage-2 operator control contract note added (no topology change): `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-19_steamer_card_engine_p1_stage2_operator-control-contract.md`.
- 2026-03-20 — stage-2 `operator-control-contract` clarified (explicit mapping to auth/session + CLI spec); stage-2 marked **done** (no topology change).
- 2026-03-20 — stage-3 bounded live path contract note added (no topology change): `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-20_steamer_card_engine_p1_stage3_bounded-live-path-contract.md`; stage-3 activated.
- 2026-03-21 — stage-3 marked **done**; stage-4 `reportable-p1` activated (no topology change).
- 2026-03-22 — stage-4 coherence pass: refreshed sprint-pack forcing-move truth + cleaned `docs/TOPOLOGY.md` cross-links + updated scaffold cron spec docs to point at canonical sprint surfaces (no topology change).
- 2026-03-23 — stage-4 `reportable-p1` marked **done** (pack is reportable end-to-end; no topology change).
- 2026-03-25 — repo hygiene: ignore `runs/` + `comparisons/` artifacts via `.gitignore` (no topology change).
- 2026-03-26 — progress pass: re-checked sprint surfaces + upstream Steamer status/topology for collision; stage-4 remains closed (no topology change).
- 2026-03-27 — progress pass: re-checked sprint surfaces + upstream Steamer status/topology for collision; stage-4 remains closed (no topology change).
- 2026-03-30 — bounded live smoke gate landed as a seed executable control slice (`operator status|arm-live|disarm-live|flatten` + TTL auto-disarm + explicit disarmed refusal smoke command + receipts), with explicit non-broker boundary (no topology change): `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-30_steamer_card_engine_p1_bounded-live-smoke_operator-control_seed-implementation.md`.
- 2026-03-30 — progress pass: wired the bounded-live smoke seed note into the stage-2 evidence pointer for reportability (no topology change).
- 2026-03-31 — progress pass: re-checked sprint surfaces + upstream Steamer status/topology for collision; stage-4 remains closed (no topology change).
- 2026-04-01 — progress pass: re-checked sprint surfaces + upstream Steamer status/topology for collision; stage-4 remains closed (no topology change).
- 2026-04-02 — progress pass: re-checked sprint surfaces + upstream Steamer status/topology for collision; stage-4 remains closed (no topology change).
- 2026-04-03 — progress pass: re-checked sprint surfaces + upstream Steamer status/topology for collision; stage-4 remains closed (no topology change).
- 2026-04-05 — upstream Steamer workflow recut accepted: for the bounded `autonomous-entry-bearing-pivot-v0` sprint, `steamer-card-engine` is now the primary live-sim execution surface for family × variation sweeps while final strategy authority remains upstream in Steamer. Product Sprint P1 ownership is unchanged. (Topology unchanged.)
- 2026-04-06 — progress pass: upstream Steamer added official TWSE holiday calendar gating; synced `docs/DAYTRADING_GUARDRAILS.md` with a market-day gating guardrail to keep P1 live-capability posture honest. (Topology unchanged.)

- 2026-04-07 — progress pass: re-checked sprint surfaces + upstream Steamer status/topology for collision; stage-4 remains closed (no topology change).
- 2026-04-08 — dashboard truth check surfaced a missing open-phase contract edge: current repo truth already defines `full-session` as `09:00–13:30`, but the replay/live-sim bundle path still reflects source min/max timing and does not operationalize 盤前試搓 vs 正式開盤 gating, pre-open ROD-only constraints, or official-open confirmation before normal intraday execution requests. Backlog note added at `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-04-08_steamer_card_engine_market-phase-gating-gap_backlog.md`. (Topology unchanged.)
- 2026-04-08 — planning-only execution packet landed for the next bounded cut: split the line into Issue 1 (runtime/artifact market-phase gating) and Issue 2 (dashboard truth surface), grounded likely files, verifier plan, and delayed-implementation packet order. Claude CLI was used as a bounded second-brain review for planning only; no implementation started. Packet: `/root/.openclaw/workspace/steamer-card-engine/ops/execution-packets/2026-04-08_steamer-card-engine_market-phase-gating-and-dashboard-truth.packet.md`. (Topology unchanged.)
- 2026-04-08 — deeper legacy-vs-product all-session review completed locally: extracted the legacy bot’s effective session topology (warmup/pre-open, open discovery, regular entry, exit/stop monitoring, forced close, post-close tail), mapped it to steamer-card-engine doc/code surfaces, and used Claude CLI as a bounded second-brain cross-review to derive a generalized phase model + ownership split without cloning the old bot. Internal analysis docs were kept local-only; no implementation started. (Topology unchanged.)
- 2026-04-08 — the same reconciliation line was extended to cover live-sim topology and post-development verification: replay-sim and captured-baseline-dir live-sim should share the same downstream phase-classifier truth, and the opening verifier ladder should include historical tick-data / captured-baseline-dir checks for phase-trace consistency, forced-close boundaries, and dashboard phase-field truth. Internal analysis docs were kept local-only; backlog truth updated remotely. (Topology unchanged.)
- 2026-04-08 — implementation slice 1 landed on `feat/gemini-gamify-dashboard`: added a shared TWSE session-phase classifier, suppressed regular-entry execution artifacts outside the generalized regular-session window, disclosed `session_phase_contract` + `session_phase_trace` in `run-manifest.json`, labeled historical pre-open execution attempts as `execution-phase-violation` in Mission Control, updated artifact/guardrail docs, and passed verifier runs (`uv run pytest -q` and `frontend npm run build`). The slice intentionally stops short of richer open-discovery and forced-close executor semantics. (Topology unchanged.)
- 2026-04-08 — implementation slice 2a landed on the same branch: expanded the generalized TWSE phase contract to include entry-cutoff / exit-monitor-only / forced-exit / final-auction windows, advanced run-manifest disclosure to `twse-session-phase/v1`, added semantic/order-profile/user-def metadata to allowed regular-entry execution artifacts, tightened bundle validation around phase-contract disclosure, and passed verifier runs again (`uv run pytest -q`, `frontend npm run build`). This still stops short of actual open-discovery event logic and forced-close executor lifecycle behavior. (Topology unchanged.)
- 2026-04-08 — implementation slice 2b landed on the same branch: added open-discovery observation preservation (`market_observation_state` on events + `open_discovery_summary` in run-manifest) when normalized streams carry trial/open hints, and added a first non-entry execution bridge for `exit`/`reduce`/`forced_exit`/`close`/`flatten` stages using phase-aware order profiles. Synthetic verifier additions cover trial-match -> official-open evidence and forced-exit request emission. This still stops short of full open-state modeling and forced-close lifecycle execution. (Topology unchanged.)
- 2026-04-08 — implementation slice 2c landed on the same branch: emitted execution requests now also create a first `order-lifecycle.jsonl` placeholder receipt (`state=new`) so the forced-exit bridge no longer stops at execution shells alone, and Mission Control now surfaces `open_discovery_summary` in the phase summary. Verifiers passed again (`uv run pytest -q`, `frontend npm run build`). Historical committed March fixtures remain truthful but are not backfilled with regenerated fields. (Topology unchanged.)
