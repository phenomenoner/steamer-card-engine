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
│   ├── SIM_ARTIFACT_SPEC.md
│   ├── SCENARIO_SPEC.md
│   ├── CONSULTANT_REVIEW_COPILOT.md
│   └── articles/
│       └── 2026-03-12-steamer-card-engine-overview/
├── examples/
│   ├── cards/     # example card manifests (TOML)
│   ├── decks/     # example deck manifests (TOML)
│   ├── config/    # example global engine config (TOML)
│   └── profiles/  # example auth profiles (TOML)
├── src/steamer_card_engine/
│   ├── cli.py
│   ├── manifest.py
│   ├── models.py
│   ├── sim_compare.py         # M1 baseline normalizer + comparator skeleton
│   ├── adapters/base.py
│   ├── cards/base.py
│   └── runtime/components.py
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
- `docs/SCENARIO_SPEC.md` — shared scenario identity contract for baseline-vs-candidate comparability

### Executable seed (v0.1)

- `src/steamer_card_engine/manifest.py`
  - TOML loading + validation for: auth profile / card / deck / global
- `src/steamer_card_engine/sim_compare.py`
  - M1 foundation tooling:
    - baseline artifact normalizer (`sim normalize-baseline`)
    - comparator skeleton (`sim compare`) with hard gates + scaffold report outputs
- `src/steamer_card_engine/cli.py`
  - validate/inspect CLI for manifests + M1 sim normalization/comparison commands
- `tests/test_cli.py`, `tests/test_manifests.py`, `tests/test_sim_compare.py`
  - pin current CLI behaviors, validation rules, and M1 comparator hard-gate behavior

### Intentional placeholders (not yet “real runtime”)

- `src/steamer_card_engine/runtime/components.py`
  - **names** the future components, but does not implement conflict resolution / risk / execution
- `steamer-card-engine replay run ...`
  - placeholder output only (no receipts/artifacts yet)
- `steamer-card-engine operator ...`
  - placeholder output only (no runtime attached yet)

## Sharp edges / known deltas

1. **Docs are richer than current models**
   - The docs describe `Intent` / `ExecutionRequest` / `OrderLifecycleEvent` shapes that are not fully represented in `src/steamer_card_engine/models.py` yet.
   - This is expected at v0.1, but it means: treat docs as the target contract; treat code as seed scaffolding.

2. **Overlay semantics are not yet frozen**
   - Card vs deck vs global policy merge/precedence rules (tighten vs widen) are described conceptually but not fully specified as executable semantics.

3. **Replay credibility depends on receipts**
   - `docs/SIM_ARTIFACT_SPEC.md` now defines the target artifact contract (event/feature/intent/risk/execution + checksums).
   - Runtime emission is still partial/placeholder, so replay remains a contract-first path rather than a complete capability.
   - M1 baseline normalization is now implemented, but currently uses conservative placeholders for unknown legacy fields (for example qty/fill/position details when baseline artifacts do not expose them).

4. **Scenario identity is now defined, but not yet enforced by runtime**
   - `docs/SCENARIO_SPEC.md` defines the shared identity shape needed for baseline-vs-candidate comparisons.
   - M1 SIM-comparability evidence runs require `scenario-spec.json` + `scenario_fingerprint`, but enforcement is not implemented yet.
   - Current CLI/runtime paths may still accept loosely specified replay inputs; strict ScenarioSpec validation is a next-step implementation item.

5. **Authority states need executable posture**
   - Docs strongly assert operator-governed live authority.
   - The actual state machine (disarmed / replay-only / live-sim / armed-live / degraded-session) is not implemented yet.
   - Until then, any sim attachment must remain explicitly `trade_enabled=false` with simulated execution disclosed in artifacts.

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
- Migration sequencing: `docs/MIGRATION_PLAN.md`
- SIM artifact contract: `docs/SIM_ARTIFACT_SPEC.md`
- Scenario identity contract: `docs/SCENARIO_SPEC.md`
- Copilot consultant critique: `docs/CONSULTANT_REVIEW_COPILOT.md`
