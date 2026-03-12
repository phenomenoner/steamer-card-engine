# Topology

This document is a **structure + boundaries map** for `steamer-card-engine`.

It’s intentionally practical: where things live, which files are contracts vs placeholders, and what the sharp edges are right now.

## Repo map (today)

```text
steamer-card-engine/
├── README.md
├── pyproject.toml
├── uv.lock
├── docs/
│   ├── PRODUCT_SCOPE.md
│   ├── ARCHITECTURE.md
│   ├── CARD_SPEC.md
│   ├── ADAPTER_SPEC.md
│   ├── CLI_SPEC.md
│   ├── AUTH_AND_SESSION_MODEL.md
│   ├── DAYTRADING_GUARDRAILS.md
│   ├── MIGRATION_PLAN.md
│   ├── SIM_ARTIFACT_SPEC.md
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
│   ├── adapters/base.py
│   ├── cards/base.py
│   └── runtime/components.py
└── tests/
    ├── test_cli.py
    ├── test_manifests.py
    └── fixtures/
```

## “Docs-first” boundary (what is contract vs stub)

### Contracts (source of truth for semantics)

- `docs/ARCHITECTURE.md` — planes, boundaries, intended components
- `docs/CARD_SPEC.md` — card + intent contract (fields + behavior rules)
- `docs/ADAPTER_SPEC.md` — market/broker normalization + routing expectations
- `docs/AUTH_AND_SESSION_MODEL.md` — logical session + capability posture
- `docs/DAYTRADING_GUARDRAILS.md` — emergency stop / forced exit / flatten policy
- `docs/CLI_SPEC.md` — intended CLI families + governance stance
- `docs/MIGRATION_PLAN.md` — phase slicing and dependency ordering
- `docs/SIM_ARTIFACT_SPEC.md` — simulation run artifacts, provenance, and checksum/index contract

### Executable seed (v0.1)

- `src/steamer_card_engine/manifest.py`
  - TOML loading + validation for: auth profile / card / deck / global
- `src/steamer_card_engine/cli.py`
  - validate/inspect CLI for those manifests (plus placeholders for replay/operator)
- `tests/test_cli.py`, `tests/test_manifests.py`
  - pin current CLI behaviors and validation rules

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

4. **Authority states need executable posture**
   - Docs strongly assert operator-governed live authority.
   - The actual state machine (disarmed / replay-only / live-sim / armed-live / degraded-session) is not implemented yet.

## Where to put new work (when v0.2 starts)

- **Contract models** → `src/steamer_card_engine/models.py`
- **Schema validation & merge semantics** → `src/steamer_card_engine/manifest.py` (+ tests)
- **Replay artifacts** → new module (likely `src/steamer_card_engine/replay/`)
- **Adapters** → `src/steamer_card_engine/adapters/` (expand beyond `base.py`)
- **Runtime components** → expand `src/steamer_card_engine/runtime/` (keep execution hot-path concerns explicit)
- **CLI surface** → `src/steamer_card_engine/cli.py` and tests in `tests/test_cli.py`

## Cross-links

- Architecture overview: `docs/ARCHITECTURE.md`
- Migration sequencing: `docs/MIGRATION_PLAN.md`
- SIM artifact contract: `docs/SIM_ARTIFACT_SPEC.md`
- Copilot consultant critique: `docs/CONSULTANT_REVIEW_COPILOT.md`
