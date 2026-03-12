# AGENTS.md — steamer-card-engine contributor protocol

This file is for coding agents and automation assistants working in this repo.

## 1) Mission and current boundary

- Repo type: **docs-first seed runtime** for Taiwan stock intraday card/deck workflows.
- Current reliable surface: manifest contracts (`auth/card/deck/global`) and CLI `validate/inspect` commands.
- Replay/operator/runtime execution is still partial or placeholder.

Do not overclaim runtime completeness.

## 2) First 5 minutes checklist

From repo root:

```bash
uv sync --dev
uv run steamer-card-engine --help
uv run pytest
```

If you touched CLI or manifest behavior, also run:

```bash
uv run ruff check .
```

## 3) Contract-first source of truth

Before changing behavior, read the relevant docs contract:

- architecture/boundaries: `docs/ARCHITECTURE.md`
- CLI behavior: `docs/CLI_SPEC.md`
- card/deck semantics: `docs/CARD_SPEC.md`
- sim/replay identity: `docs/SIM_ARTIFACT_SPEC.md`, `docs/SCENARIO_SPEC.md`
- migration sequencing: `docs/MIGRATION_PLAN.md`
- repo map + placeholder boundary: `docs/TOPOLOGY.md`
- install/dev workflow: `docs/SETUP.md`

If code and docs diverge, either:

1. update code + tests to satisfy contract, or
2. update contract docs intentionally with a clear rationale.

Do not silently drift.

## 4) Safe changes agents can make

- Improve manifest validation and inspect summaries
- Add tests for manifest/CLI behavior
- Improve docs/examples for authoring and governance posture
- Refactor internals without changing safety boundaries

## 5) Changes that need explicit caution

- Anything implying live-trading authority
- Auth/session capability semantics that affect trade enablement
- Risk/flatten semantics
- Replay artifact schema or scenario identity changes

When touching these, include a plain-language note of behavior change and risk impact.

## 6) Claims policy (important)

You may claim:

- this repo is docs-first/spec-first
- manifest validate/inspect commands exist and are tested

You may **not** claim (yet):

- production-ready live trading engine
- fully implemented replay/live-sim artifact emission
- complete operator control plane

## 7) Handoff receipt format

In your final note, include:

- what files changed
- what commands you ran
- what is now true
- what remains placeholder

Keep receipts factual, short, and verifiable.
