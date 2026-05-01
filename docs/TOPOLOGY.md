# Topology

This document is a **structure + boundaries map** for `steamer-card-engine`.

It’s intentionally practical: where things live, which files are contracts vs placeholders, and what the sharp edges are right now.

## Repo map (today)

```text
steamer-card-engine/
├── README.md
├── AGENTS.md
├── pyproject.toml
├── uv.lock
├── docs/
│   ├── PRODUCT_SCOPE.md
│   ├── ARCHITECTURE.md
│   ├── CARD_SPEC.md
│   ├── ADAPTER_SPEC.md
│   ├── CLI_SPEC.md
│   ├── SETUP.md
│   ├── AUTH_AND_SESSION_MODEL.md
│   ├── DAYTRADING_GUARDRAILS.md
│   ├── MIGRATION_PLAN.md
│   ├── MILESTONE_M1_SIM_COMPARABILITY.md
│   ├── M1_SIM_COMPARABILITY_FOUNDATION_PACK.md
│   ├── M1_EVIDENCE_PACK_ACCEPTANCE_CONTRACT.md
│   ├── M1_EVIDENCE_PACK_INDEX.md
│   ├── EVIDENCE_PACKAGING_HYGIENE.md
│   ├── EVIDENCE_PROVENANCE_ENVELOPE_SPEC.md
│   ├── SIM_ARTIFACT_SPEC.md
│   ├── SCENARIO_SPEC.md
│   ├── CONSULTANT_REVIEW_COPILOT.md
│   ├── tech-notes/
│   ├── receipts/
│   │   ├── 2026-03-14_m1-stage3-first-replay-sim-comparable.md
│   │   ├── 2026-03-14_m1-stage4-candidate-engine-emitted-blocker.md
│   │   ├── 2026-03-15_m1-stage5-candidate-replay-emission-and-compare.md
│   │   ├── 2026-03-15_m1-phase1-evidence-pack-3-scenarios.md
│   │   ├── 2026-03-15_m1-phase2-acceptance-contract-freeze.md
│   │   ├── 2026-03-15_m1-phase3-repeatability-anti-fluke.md
│   │   ├── 2026-03-15_m1-phase4-operatorization-doc-hygiene.md
│   │   ├── 2026-03-15_m1-optionb-artifact-packaging-hygiene.md
│   │   └── 2026-03-15_m1-pre-sprint-serial-closure.md
│   └── articles/
│       └── 2026-03-12-steamer-card-engine-overview/
├── ops/
│   ├── sprints/
│   └── sprint-controllers/
├── examples/
│   ├── cards/     # example card manifests (TOML)
│   ├── decks/     # example deck manifests (TOML)
│   ├── config/    # example global engine config (TOML)
│   └── profiles/  # example auth profiles (TOML)
├── src/steamer_card_engine/
│   ├── cli.py
│   ├── manifest.py
│   ├── models.py
│   ├── sim_compare.py         # M1 baseline normalizer + decision-grade comparator
│   ├── adapters/base.py
│   ├── cards/base.py
│   └── runtime/components.py
├── runs/
│   ├── baseline-bot/
│   │   ├── 2026-03-06/
│   │   ├── 2026-03-10/
│   │   ├── 2026-03-12/
│   │   └── 2026-03-20/        # newer local baseline receipts / working lane
│   └── steamer-card-engine/
│       ├── 2026-03-06/
│       ├── 2026-03-10/
│       ├── 2026-03-12/
│       ├── 2026-03-17/        # newer local candidate receipts / working lane
│       ├── 2026-03-18/        # newer local candidate receipts / working lane
│       └── 2026-03-20/        # newer local candidate receipts / working lane
├── comparisons/
│   ├── replay-sim_tw-paper-sim-twse-2026-03-06-full-session_baseline_...__replay-sim_tw-paper-sim-twse-2026-03-06-full-session_candidate_.../
│   ├── replay-sim_tw-paper-sim-twse-2026-03-10-full-session_baseline_...__replay-sim_tw-paper-sim-twse-2026-03-10-full-session_candidate_.../
│   ├── replay-sim_tw-paper-sim-twse-2026-03-12-full-session_baseline_...__replay-sim_tw-paper-sim-twse-2026-03-12-full-session_candidate_.../
│   ├── phase3_mismatch_2026-03-06_vs_2026-03-12/
│   ├── phase3_recheck_2026-03-10/
│   └── manual-live-paired-20260320-.../   # workspace-local paired compare lane
└── tests/
    ├── test_cli.py
    ├── test_manifests.py
    ├── test_sim_compare.py
    └── fixtures/
```

## “Docs-first” boundary (what is contract vs stub)

### Contracts (source of truth for semantics)

- `AGENTS.md` — contributor/agent protocol for safe repo work and claims discipline
- `docs/SETUP.md` — install/bootstrap and current safe command surface
- `docs/ARCHITECTURE.md` — planes, boundaries, intended components
- `docs/CARD_SPEC.md` — card + intent contract (fields + behavior rules)
- `docs/ADAPTER_SPEC.md` — market/broker normalization + routing expectations
- `docs/AUTH_AND_SESSION_MODEL.md` — logical session + capability posture
- `docs/DAYTRADING_GUARDRAILS.md` — emergency stop / forced exit / flatten policy
- `docs/CLI_SPEC.md` — intended CLI families + governance stance
- `docs/MIGRATION_PLAN.md` — phase slicing and dependency ordering
- `docs/MILESTONE_M1_SIM_COMPARABILITY.md` — bounded milestone plan for replay/live-sim artifact comparability
- `docs/M1_SIM_COMPARABILITY_FOUNDATION_PACK.md` — baseline inventory + comparison contract v0 + sprint-ready stage ordering for M1 execution
- `docs/SIM_ARTIFACT_SPEC.md` — simulation run artifacts, provenance, and checksum/index contract
- `docs/EVIDENCE_PROVENANCE_ENVELOPE_SPEC.md` — remote-safe aggregate provenance envelope + MarketDataHub stats/introspection contract draft
- `docs/SCENARIO_SPEC.md` — shared scenario identity contract for baseline-vs-candidate comparability

### Executable seed (v0.1)

- `src/steamer_card_engine/manifest.py`
  - TOML loading + validation for: auth profile / card / deck / global
- `src/steamer_card_engine/sim_compare.py`
  - M1 foundation tooling:
    - baseline artifact normalizer (`sim normalize-baseline`)
    - comparator (`sim compare`) with hard gates + decision-grade report outputs (`compare-manifest.json`, `diff.json`, `summary.md`)
- `src/steamer_card_engine/cli.py`
  - validate/inspect CLI for manifests + M1 sim normalization/comparison commands
  - active execution-family JSON surfaces (`replay run`, `sim run-live`, `sim normalize-baseline`, `sim compare`, `operator probe-session`, `operator preflight-smoke`, `operator live-smoke-readiness`) now share the same machine-readable `cli_contract` envelope (`cli-command/v1`)
  - auth logical-session inspection (`auth inspect-session`) with seed capability/health/day-gate disclosure, reusable `session_status + connections` shape, external `--probe-json` override, and named upstream truth adapter support via `--probe-source` (`--probe-json` wins on precedence)
  - operator session probing (`operator probe-session`) that emits the canonical snapshot for downstream preflight/cron consumers
  - canonical probe/preflight/live-smoke payloads now carry explicit `probe_freshness` + `probe_receipt` truth so operators can see both readiness and receipt provenance
  - preflight blocker classification now preserves failure family (`auth`, `stale`, `disconnected`, `capability-mismatch`) instead of flattening every miss into `not-connected`
  - the current named adapter proves broker + marketdata readiness from upstream cron-health receipts; it does not independently prove account-query connectivity
  - sim/replay JSON error paths now stay machine-readable under `--json` instead of dropping back to plain-text-only failures
- `ops/scripts/trading_day_preflight_seed.sh`
  - repo-side seed runner for the chain `operator probe-session -> operator preflight-smoke`
  - still accepts explicit probe fixture JSON, but can now ride named upstream truth adapters through env/CLI without changing the runner contract
- `tools/steamer_card_engine_trading_day_preflight_cron.py`
  - cron-safe wrapper for the trading-day preflight chain (`NO_REPLY` on green, concise `BLOCKED ...` on red)
  - defaults to `STEAMER_CARD_ENGINE_PROBE_SOURCE=steamer-cron-health` when no explicit probe fixture is injected
- `tests/test_cli.py`, `tests/test_manifests.py`, `tests/test_sim_compare.py`
  - pin current CLI behaviors, aligned `cli_contract` JSON envelopes, JSON error posture, validation rules, and M1 comparator hard-gate behavior
- `runs/...` + `comparisons/...`
  - committed M1 receipt artifacts (baseline bundle, candidate bundle, comparator outputs) for a 3-scenario pre-sprint evidence pack
  - compare outputs are now decision-grade (`compare-manifest.json`, `diff.json`, `summary.md`), not just placeholder plumbing
  - include both passing comparable pairs and explicit phase-3 mismatch replayability checks for hard-gate verification
  - working tree may also contain newer local run/comparison lanes (for example 2026-03-17/18/20 candidate receipts or `manual-live-paired-*` comparisons); treat those as workspace receipts until promoted into `docs/M1_EVIDENCE_PACK_INDEX.md`
  - Option B hygiene: duplicate `event-log.jsonl` payloads are symlink-deduped to canonical copies; content hashes remain unchanged

### Intentional placeholders (not yet “real runtime”)

- `src/steamer_card_engine/runtime/components.py`
  - **names** the future components, but does not implement conflict resolution / risk / execution
  - exposes only seed-grade, aggregate-only MarketDataHub stats helpers aligned with `docs/EVIDENCE_PROVENANCE_ENVELOPE_SPEC.md`; this is not full native runtime introspection
- operator commands now maintain a seed local posture/receipt state machine (`.state/operator_posture.json` + `.state/operator_receipts/`)
  - this is a bounded smoke/control surface, not a broker-connected production control plane
  - `live-smoke-readiness` now consumes the same probe/preflight posture contract as `probe-session -> preflight-smoke -> cron`, and only runs the bounded live-capability sequence when that gate is ready
  - `preflight-smoke` can now consume truthful upstream Steamer cron-health receipts through the canonical probe contract, while keeping the same prepared-only boundary
  - named-source/manual probe receipts now remain explicit in the emitted JSON surface; seed-only posture stays labeled unverified rather than pretending to have broker authority

## Sharp edges / known deltas

1. **Docs are richer than current models**
   - The docs describe `Intent` / `ExecutionRequest` / `OrderLifecycleEvent` shapes that are not fully represented in `src/steamer_card_engine/models.py` yet.
   - This is expected at v0.1, but it means: treat docs as the target contract; treat code as seed scaffolding.

2. **Overlay semantics are not yet frozen**
   - Card vs deck vs global policy merge/precedence rules (tighten vs widen) are described conceptually but not fully specified as executable semantics.

3. **Replay credibility still depends on receipts**
   - `docs/SIM_ARTIFACT_SPEC.md` defines the target artifact contract (event/feature/intent/risk/execution + checksums).
   - `replay run` now emits a real candidate v1 bundle path, but current M1 behavior is still a legacy-bridge emitter rather than full native runtime behavior parity.
   - M1 baseline/candidate emission currently uses conservative placeholders for unknown legacy fields (for example qty/fill/position details when baseline artifacts do not expose them).

4. **Scenario identity is now defined, but not yet enforced by runtime**
   - `docs/SCENARIO_SPEC.md` defines the shared identity shape needed for baseline-vs-candidate comparisons.
   - M1 SIM-comparability evidence runs require `scenario-spec.json` + `scenario_fingerprint`, but enforcement is not implemented yet.
   - Current CLI/runtime paths may still accept loosely specified replay inputs; strict ScenarioSpec validation is a next-step implementation item.

5. **Authority states are only seed-grade executable posture today**
   - Docs strongly assert operator-governed live authority.
   - A bounded local state machine now exists for `disarmed` ↔ `armed-live` with TTL/auto-disarm and receipt trails.
   - It is still not broker-connected runtime authority; sim attachments remain explicitly simulated and disclosure-first.


## Cross-line ownership contract (2026-03-26)

This repo now owns the **backtest engine/product surface** for the Steamer line.

Authority split:
- `steamer-card-engine` (this repo): engine capability + productization contracts
- `StrategyExecuter .../powerhouse`: strategy experiment loop + interpretation of validation results
- `mandate-campaign-framework`: governor cadence + artifact-governance discipline

Current bounded operating cut (2026-04-05):
- during the Steamer `autonomous-entry-bearing-pivot-v0` sprint, this repo is the **primary live-sim execution surface** for family × variation sweeps
- that does **not** transfer final strategy-promotion authority into this repo
- it also does **not** make this repo the Steamer daily control plane; native runtime truth stays in Steamer

Guardrails for this repo:
- allowed: engine contracts, lineage tooling, validation-pack productization
- must not: strategy semantic promotion authority, Steamer nightly governor writes, campaign-governor cadence ownership

Canonical note:
- `docs/tech-notes/2026-03-26_backtest-loop-ownership-contract_with_strategy-powerhouse_and_mandate-framework.md`

## Where to put new work (when v0.2 starts)

- **Contract models** → `src/steamer_card_engine/models.py`
- **Schema validation & merge semantics** → `src/steamer_card_engine/manifest.py` (+ tests)
- **Replay artifacts** → new module (likely `src/steamer_card_engine/replay/`)
- **Adapters** → `src/steamer_card_engine/adapters/` (expand beyond `base.py`)
- **Runtime components** → expand `src/steamer_card_engine/runtime/` (keep execution hot-path concerns explicit)
- **CLI surface** → `src/steamer_card_engine/cli.py` and tests in `tests/test_cli.py`

## Cross-links

- Setup guide: `docs/SETUP.md`
- Agent/contributor protocol: `AGENTS.md`
- Architecture overview: `docs/ARCHITECTURE.md`
- Product scope: `docs/PRODUCT_SCOPE.md`
- Auth/session model: `docs/AUTH_AND_SESSION_MODEL.md`
- Day-trading guardrails: `docs/DAYTRADING_GUARDRAILS.md`
- CLI spec: `docs/CLI_SPEC.md`
- Operator CLI exit/JSON contract note: `docs/tech-notes/2026-04-16_steamer_card_engine_operator_cli_exit_json_contract.md`
- Sim/replay/operator CLI alignment note: `docs/tech-notes/2026-04-16_steamer_card_engine_sim_replay_operator_cli_contract_alignment.md`
- Migration sequencing: `docs/MIGRATION_PLAN.md`
- SIM artifact contract: `docs/SIM_ARTIFACT_SPEC.md`
- Evidence provenance envelope contract: `docs/EVIDENCE_PROVENANCE_ENVELOPE_SPEC.md`
- Scenario identity contract: `docs/SCENARIO_SPEC.md`
- M1 pointers: `docs/MILESTONE_M1_SIM_COMPARABILITY.md`, `docs/M1_SIM_COMPARABILITY_FOUNDATION_PACK.md`, `docs/M1_EVIDENCE_PACK_INDEX.md`
- P1 sprint truth: `ops/sprints/steamer-card-engine-p1-live-trading-capability-v0-sprint.md`
- Mission Control dashboard sprint truth: `ops/sprints/steamer-card-engine-mission-control-dashboard-v0-sprint.md`
- Mission Control dashboard build packet: `docs/tech-notes/2026-04-06_steamer_card_engine_mission-control_dashboard_v0_build-packet.md`
- Mission Control dashboard fixture discovery now indexes committed replay-sim + manual-live-paired representatives across `2026-03-06` → `2026-04-09`; same-date compare variants remain collapsed to one representative entry; topology unchanged
- The browser surface is now a broader read-only `Steamer Dashboard` with two truthful tabs: `Live Sim` (execution receipts) and `Strategy Powerhouse / Strategy Cards` (local research/control artifact summary only). The strategy tab now carries per-family timeline / latest packet / verifier history / gate / handoff truth from local artifacts only. It does not change execution or governance topology.
- The strategy tab now also includes a thin read-only active-family baton line sourced from the same local proposal/active plan artifacts. It shows the current active paired-lane family, attached active decks, proposal handoff readiness, and explicit proposed-vs-active divergence or missing-active-plan truth. It still does not change execution or governance topology.
- The baton line now also surfaces explicit **activation/promotion truth** for the autonomous morning paired lane via `.state/steamer/card-engine-morning-paired-lane/activation_latest.json` (and its `runtime_window.effective_scope`), so the dashboard does not imply that a post-`09:05` activation retroactively changed the already-fired run.
- Strategy Powerhouse history / verifier / baton-source discovery now runs through a thin shared index helper (`src/steamer_card_engine/dashboard/history_source_index.py`) that resolves the latest proposal-day artifact bundle plus recognized family extras from local files only. It does not add a new service, authority surface, or topology edge.
- Strategy Powerhouse history-browser packet: `docs/tech-notes/2026-04-09_steamer_strategy_powerhouse_history_browser.md`
- History-source index slice receipt: `docs/receipts/2026-04-09_dashboard_history-source-index_slice.md`
- `五氣朝元` closure receipt for the baton-line authority sweep: `docs/receipts/2026-04-09_dashboard_active-family-baton-line_wuqi-chaoyuan_closure.md`
- Copilot consultant critique: `docs/CONSULTANT_REVIEW_COPILOT.md`

## Stage 0 fixture adapter probe topology note (2026-05-02)

Added `steamer-card-engine adapter probe --fixture paper-only --json` as a read-only CLI contract probe backed by `src/steamer_card_engine/adapters/fixture_exchange.py`.

Topology/config/cron impact: unchanged. The probe performs no broker SDK import, no network call, no credential/env/certificate read, no `/workspace/steamer` access, no operator posture/receipt write, and no runtime topology mutation.

## Stage 1 fixture adapter contract topology note (2026-05-02)

Added read-only fixture contract surfaces:

- `steamer-card-engine adapter explain --adapter fixture-paper-only --json`
- `steamer-card-engine adapter contract check --adapter fixture-paper-only --fixtures examples/probes/adapter_contract --json`

Topology/config/cron impact: unchanged. These commands load local sanitized fixtures only, emit deterministic JSON, and perform no broker SDK import, no network call, no credential/env/certificate read, no `/workspace/steamer` access, no operator posture/receipt write, and no runtime topology mutation.
