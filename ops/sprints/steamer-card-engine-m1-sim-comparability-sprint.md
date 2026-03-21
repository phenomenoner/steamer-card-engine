# Steamer Card Engine — M1 SIM comparability sprint

## Sprint goal / milestone

Deliver M1 as a **sim-only, contract-first** milestone:

- baseline-bot and steamer-card-engine both produce reviewable **v1 SIM artifact bundles**
- comparator hard-fails on scenario identity / `execution_model` mismatch
- replay-sim evidence proof is already frozen and truthful
- next staged milestone edge is a **live-sim-attached** v1 bundle under the same sim-only boundary
- eventual M1 acceptance remains evidence-driven rather than best-effort theater

Non-negotiable boundary:
- **no live trading authority**
- **no broker order submission codepaths** exercised for M1
- `execution_model` mismatch is a **hard stop** for comparison

## Current rollout policy

- Overall posture: **active sprint, scaffold-first**
- Controller posture: **doc-driven sprint controller pack arranged**
- Live controller jobs: **progress pass enabled**; `captain-prep` remains scaffolded/disabled
- Rollout mode: **staged**, not parallel chaos
- Execution posture: **all-green mandatory inside approved gates**; routine approval pings are out-of-contract
- Report posture: ordinary progress goes to sprint truth / scheduled windows; **important decisions report immediately**
- Current stage order remains:
  1. foundation
  2. contract-freeze
  3. replay-sim-comparable
  4. live-sim-attached
  5. evidence-pack acceptance

## Execution contract — Stage 4 first live-sim bundle

This sprint is **not** a ready-only sprint.
The active gate closes only when the first truthful `run_type=live-sim` bundle exists under `steamer-card-engine/runs/...`.

Execution surfaces:
- execution pack: `/root/.openclaw/workspace/steamer-card-engine/ops/sprints/steamer-card-engine-m1-stage4-live-sim-first-run-pack.md`
- execution primitive: `/root/.openclaw/workspace/steamer-card-engine/tools/steamer_card_engine_stage4_live_sim_first_run.py`
- underlying engine command: `steamer-card-engine sim run-live ...`
- default captured input: `projects/trading-research/artifacts/tw-paper-sim/<session_date>/`
- success receipt: first bundle under `steamer-card-engine/runs/steamer-card-engine/<session_date>/<run_id>/` with truthful `run-manifest.json` + required v1 artifacts

Controller role:
- keep the scorecard truthful
- decide when the active gate is green enough to run
- invoke the checked-in execution primitive directly or launch the bounded worker that does so
- write back receipts / blockers / next checks after the run

This keeps the controller out of “main worker” mode while still giving the sprint a concrete way to finish its own milestone.

## Lane / stage scorecard

| Stage | Status | Hard gate | Evidence pointer |
|---|---|---|---|
| foundation | done | baseline normalizer + comparator skeleton shipped; hard-stop checks wired | `steamer-card-engine/src/steamer_card_engine/sim_compare.py` |
| contract-freeze | done | acceptance contract frozen; anti-gaming rules explicit | `steamer-card-engine/docs/M1_EVIDENCE_PACK_ACCEPTANCE_CONTRACT.md` |
| replay-sim-comparable | done | candidate lane emits truthful replay bundles; 3-scenario replay proof exists | `steamer-card-engine/docs/receipts/2026-03-15_m1-phase1-evidence-pack-3-scenarios.md` |
| live-sim-attached | done | first live-sim-attached run emitted a truthful v1 bundle while staying sim-only | `steamer-card-engine/runs/steamer-card-engine/2026-03-17/live-sim_tw-live-sim-twse-2026-03-17-full-session_candidate_20260318T005626Z/` |
| evidence-pack acceptance | done | final M1 acceptance must remain truthful and use the frozen contract/evidence rules | `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-18_steamer_card_engine_m1_evidence_pack_acceptance.md` |

## Stage 4 gate — live-sim-attached (closed 2026-03-18)

Goal: produce the **first truthful** `run_type=live-sim` v1 artifact bundle while staying strictly **sim-only**.

Hard gate checklist (must all be true):
- A candidate bundle exists under `steamer-card-engine/runs/steamer-card-engine/<session_date>/<run_id>/` with required v1 artifacts + `file-index.json` checksums.
- `run-manifest.json` is explicit and consistent:
  - `run_type=live-sim`
  - `capability_posture.trade_enabled=false` (sim-only authority)
  - `execution_model.fill_model` is simulator-disclosed (no broker submission semantics)
  - `scenario_id` present; for any evidence-pack candidate, also require `scenario-spec.json` + `scenario_fingerprint`
  - `market_event_source.source_id` is disclosed (what live-sim feed / dataset identity was used)
- If a baseline bundle + compare is produced for the same live-sim session:
  - comparator must still hard-fail on ScenarioSpec / `execution_model` mismatch (no best-effort comparisons)

Observation checklist (record as receipts alongside the bundle):
- Which command/path was used (`docs/CLI_SPEC.md` target includes `sim run-live --dry-run`), and what guardrails were used to keep sim-only.
- Feed integrity notes: gaps/out-of-order events, symbol coverage; ensure `anomalies.json` is present and truthful.
- Explicit stop condition: **any** hint of trade-enabled or broker submission path → abort and mark run `status=failed` (M1 violation).

Rollback posture (if Stage 4 gets noisy/ambiguous):
- Do not enable additional controller cron jobs just to manufacture movement.
- Keep M1 replay evidence pack frozen; treat Stage 4 as an isolated, receipted push line until it is clean.

## Current blockers / risks

- Stage 4 is now closed under the written sprint contract: the first truthful `run_type=live-sim` bundle exists under `steamer-card-engine/runs/steamer-card-engine/2026-03-17/live-sim_tw-live-sim-twse-2026-03-17-full-session_candidate_20260318T005626Z/`.
- Evidence-pack acceptance is now closed under the same sim-only authority boundary (receipt: `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-18_steamer_card_engine_m1_evidence_pack_acceptance.md`).
- The old timing-semantic follow-up is now resolved by promotion receipt: same-day morning attachment is expressed by the strategy-powerhouse-governed canonical morning paired lane (`ec9108a8-933a-44eb-b841-e37a7198fd3a` @ 09:05 Asia/Taipei) instead of the retired post-close M1 pair. See `projects/steamer/TECH_NOTES/2026-03-20_steamer_canonical-morning_paired-lane_promotion.md`.
- The first truthful Stage 4 bundle was emitted manually at 2026-03-18 08:56 Asia/Taipei using the checked-in execution helper against captured baseline dir `tw-paper-sim/2026-03-17`; this closes the current written gate and now also has a canonical morning-attachment follow-on surface.
- Only one live sprint-controller pass is enabled so far; `captain-prep` is still scaffold-only and awaits a clean reason to enable, not a routine approval ping.
- Steamer docs-memory targeted ingest remains allowlist-blocked, so sprint/operator docs rely on truthful fallback ingest for now.
- Evidence packaging hygiene is improved, but canonical symlink targets must not be moved/deleted casually.

## Allowed auto-actions

A doc-driven controller for this sprint may:
- update this sprint doc
- sync minimal related docs when repo truth changed
- append concise durable notes to `memory/YYYY-MM-DD.md`
- run docs cold-lane ingest after material operator-doc changes
- prepare stage-gate / rollout / rollback / observation checklists
- invoke the checked-in Stage 4 execution primitive / execution pack when the active gate is green and still sim-only
- launch or continue the next bounded in-scope worker/implementation move inside the active gate when it stays sim-only and inside existing boundaries

It may **not**:
- redefine M1
- expand scope into live trading
- bypass stage order
- invent “best effort” comparisons that ignore identity/model hard gates
- turn the controller into the main coding worker
- stop for routine approval once the next move is already green inside the declared sprint scope

## Escalate-to-CK conditions

Report immediately only if:
1. milestone definition needs to change
2. the live-sim-attached gate is genuinely ambiguous
3. any step risks exercising broker submission semantics or another safety hazard
4. rollback is needed and the clean path is unclear
5. the next move widens scope materially beyond M1 or needs a new authority/resource class
6. a real strategic tradeoff deserves CK’s decision now rather than at the next report window

## Docs / topology / memory sync checklist

When durable truth changes, update in the same pass:
- this sprint doc
- relevant `STATUS.md` / topology / tech notes
- push receipts for changed repos
- docs cold-lane ingest if operator-facing docs changed materially
- `memory/YYYY-MM-DD.md`

If topology does **not** change, say so explicitly in the receipt.

## Captain / handoff block

Current sprint read:
- pre-sprint serial preparation is complete; this is now a **real sprint control surface**
- replay-sim proof is frozen with truthful 3-scenario evidence, acceptance contract, repeatability checks, and operator docs
- all written stage gates are now **closed** (Stage 4 live-sim bundle + Stage 5 evidence-pack acceptance); follow-up remains: live-sim-attached timing semantics vs automation schedule
- controller posture is now mixed: progress pass is **live**, `captain-prep` remains **disabled scaffold**
- execution contract is now explicit: **inside today’s approved gate, forward motion is mandatory unless an important decision or safety boundary appears**
- active gate closes on a **real first live-sim bundle**, not on CLI readiness alone
- checked-in execution surface now exists: `/root/.openclaw/workspace/steamer-card-engine/ops/sprints/steamer-card-engine-m1-stage4-live-sim-first-run-pack.md` + `/root/.openclaw/workspace/steamer-card-engine/tools/steamer_card_engine_stage4_live_sim_first_run.py`
- immediate forcing move: none inside M1 (all written gates closed); optional follow-up: clarify `live-sim-attached` timing semantics vs current 13:40/14:15 automation before treating it as canonical

## Run journal

- 2026-03-19 — controller-pack truth sync: updated sprint-controller YAML + `projects/steamer/topology-pack-l0.md` to reflect M1 stage gates closed; removed duplicated/broken lines in topology pack. (Topology unchanged; authority unchanged.)
- 2026-03-14 — sprint doc seeded (internal control surface). Public milestone plan remains in `steamer-card-engine/docs/MILESTONE_M1_SIM_COMPARABILITY.md`.
- 2026-03-14 — lane-1 implementation receipts landed in public repo: `sim normalize-baseline` + `sim compare` (hard-fail on execution_model mismatch, scaffold compare outputs). Baseline normalizer currently emits placeholder order/fill/position artifacts when legacy baseline files are absent.
- 2026-03-14 — first replay-sim comparability plumbing receipt landed for canonical scenario `tw-paper-sim.twse.2026-03-06.full-session`: baseline bundle + candidate bundle + comparator outputs archived under `steamer-card-engine/runs/` and `steamer-card-engine/comparisons/`; comparator status `pass`; both lanes show one minor anomaly (`baseline-orders-missing`). Both bundles were generated from the same legacy source via normalizer, so this is contract/gate plumbing proof, not two-engine behavior parity yet.
- 2026-03-14 — Stage 4 serial attempt executed against the same canonical scenario and `execution_model` contract. Replay CLI remained placeholder, so no truthful candidate-engine-emitted bundle was produced; lane was intentionally stopped as BLOCKED with evidence note `steamer-card-engine/docs/receipts/2026-03-14_m1-stage4-candidate-engine-emitted-blocker.md`.
- 2026-03-15 — Stage 5 serial lane unblocked candidate emission: `replay run` now emits a truthful candidate v1 bundle (`provenance.engine_name=steamer-card-engine-replay-runner`) for canonical scenario `tw-paper-sim.twse.2026-03-06.full-session`, and compare rerun passed under matching scenario/execution-model gates. Receipt: `steamer-card-engine/docs/receipts/2026-03-15_m1-stage5-candidate-replay-emission-and-compare.md`.
- 2026-03-15 — pre-sprint serial queue completed: 3-scenario evidence pack, frozen acceptance contract, repeatability/anti-fluke receipts, operatorization/docs hygiene, and final batch Copilot review all landed. See `steamer-card-engine/docs/receipts/2026-03-15_m1-phase1-evidence-pack-3-scenarios.md`, `...phase2...`, `...phase3...`, `...phase4...`.
- 2026-03-15 — final Option B hygiene pass landed: evidence artifact footprint was cut materially via bounded dedupe without changing evidence truth; see `steamer-card-engine/docs/receipts/2026-03-15_m1-optionb-artifact-packaging-hygiene.md`.
- 2026-03-15 — upgraded from pre-sprint serial posture to an **active doc-driven sprint pack**. Controller config and scaffolded cron specs were added to repo truth.
- 2026-03-15 — live-enabled the sprint controller **progress** pass as `f4ab2bcc-eb96-4463-8398-ca67b4dc0437`; `captain-prep` remains scaffolded/disabled as `f111abe4-845d-4b70-9dbb-c2130d8e261f`. Live provisioning receipt: `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-15_steamer_card_engine_m1_sprint-live-provisioning.md`.
- 2026-03-16 — prepared an explicit Stage 4 (live-sim-attached) gate checklist + rollback/observation posture in this sprint doc to keep the next edge bounded and sim-only. (No topology/authority change.)
- 2026-03-17 — Stage 4 unblocked in `steamer-card-engine`: implemented `steamer-card-engine sim run-live` (bridge: consumes a captured baseline dir), supports `--dry-run`, and emits a v1 bundle with `run_type=live-sim` + explicit sim-only capability posture + `scenario-spec.json` + `scenario_fingerprint` + `anomalies.json` + `file-index.json`. Receipt: steamer-card-engine commit `a65d947`.
- 2026-03-17 — execution-contract closure: Stage 4 now has a named checked-in execution surface (`/root/.openclaw/workspace/steamer-card-engine/ops/sprints/steamer-card-engine-m1-stage4-live-sim-first-run-pack.md` + `/root/.openclaw/workspace/steamer-card-engine/tools/steamer_card_engine_stage4_live_sim_first_run.py`). The milestone remains **concrete-artifact closure**: gate moves only when the first truthful `run_type=live-sim` bundle exists. Next forcing move: execute that pack against a real captured feed dir and archive the first bundle under `runs/steamer-card-engine/...`. (Topology unchanged; authority unchanged.)
- 2026-03-17 — Stage 4 execution helper dry-run validated against captured session `2026-03-17`: the helper resolved the canonical `tw-paper-sim/2026-03-17` input, produced a side-effect-free receipt, and confirmed sim-only `run_type=live-sim` posture before the first real emission attempt. (Topology unchanged; authority unchanged.)
- 2026-03-17 — cron-gap hardening pass: diagnosed that the live controller (`f4ab2bcc...`) is a 13:40 post-close progress lane (not pre-open launch), then added live watchdog `909de5a3-b481-4e50-88fd-2c649c4b3829` (14:15) to auto-page on missing/non-OK controller runs and Stage 4 blocker posture. Receipt: `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-17_steamer_card_engine_m1_cron-gap-hardening.md`. (Topology changed: +1 bounded watchdog lane; authority unchanged.)
- 2026-03-18 — manual Stage 4 execution move succeeded during market hours: the checked-in helper emitted the first truthful `run_type=live-sim` v1 bundle against captured baseline dir `tw-paper-sim/2026-03-17`, under `steamer-card-engine/runs/steamer-card-engine/2026-03-17/live-sim_tw-live-sim-twse-2026-03-17-full-session_candidate_20260318T005626Z/`. Verified truth surfaces: `run_type=live-sim`, `trade_enabled=false`, `scenario-spec.json`, `anomalies.json`, and `file-index.json` all present. Under the current written sprint contract, Stage 4 is now closed and the next active gate becomes evidence-pack acceptance (since closed; see `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-18_steamer_card_engine_m1_evidence_pack_acceptance.md`). The later same-day morning attachment follow-up was resolved on 2026-03-20 by promoting a strategy-powerhouse-governed canonical morning paired lane (`projects/steamer/TECH_NOTES/2026-03-20_steamer_canonical-morning_paired-lane_promotion.md`).
- 2026-03-18 — Stage 5 evidence-pack acceptance closed under the frozen contract (replay-sim 3-scenario pack) and recorded as a single receipt note: `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-18_steamer_card_engine_m1_evidence_pack_acceptance.md`. (Topology unchanged; authority unchanged.)
- 2026-03-17 — WAL contract update: inside the approved sprint scope, ordinary forward motion is now **all-green and mandatory**; only important decisions / safety boundaries should interrupt the line, and those should be reported immediately rather than deferred to the next routine window. (Topology unchanged; control contract changed.)
