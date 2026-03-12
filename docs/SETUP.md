# Setup Guide (Human + Agent)

## Reality check first

`steamer-card-engine` is a **docs-first seed runtime**.

What is working today:

- manifest loading + validation (`auth`, `card`, `deck`, `global`)
- manifest inspection summaries (`inspect-*`)
- basic test coverage for those CLI surfaces

What is still placeholder/stub:

- `replay run` (placeholder output)
- `operator status/inspect` (placeholder output)
- runtime component split is mostly structural naming, not full execution behavior

Do not present this repo as live-trading ready.

## Prerequisites

- Python `>=3.13` (see `pyproject.toml`)
- [`uv`](https://docs.astral.sh/uv/) installed
- Git (for normal dev workflow)

## Install / bootstrap

From repo root:

```bash
uv sync --dev
```

This creates `.venv`, installs the package, and installs dev dependencies (`pytest`, `ruff`).

Sanity checks:

```bash
uv run steamer-card-engine --help
uv run python -m steamer_card_engine --help
```

## Validate and inspect manifests (current stable workflow)

### Validate

```bash
uv run steamer-card-engine auth validate-profile examples/profiles/tw_cash_agent_assist.toml
uv run steamer-card-engine author validate-card examples/cards/gap_reclaim.toml
uv run steamer-card-engine author validate-deck examples/decks/tw_cash_intraday.toml
uv run steamer-card-engine author validate-global examples/config/global.toml
```

### Inspect (human-readable)

```bash
uv run steamer-card-engine auth inspect-profile examples/profiles/tw_cash_agent_assist.toml
uv run steamer-card-engine author inspect-card examples/cards/gap_reclaim.toml
uv run steamer-card-engine author inspect-deck examples/decks/tw_cash_intraday.toml --cards-dir examples/cards
uv run steamer-card-engine author inspect-global examples/config/global.toml
```

### Inspect (agent/automation-friendly JSON)

```bash
uv run steamer-card-engine auth inspect-profile examples/profiles/tw_cash_agent_assist.toml --json
uv run steamer-card-engine author inspect-card examples/cards/gap_reclaim.toml --json
uv run steamer-card-engine author inspect-deck examples/decks/tw_cash_intraday.toml --cards-dir examples/cards --json
uv run steamer-card-engine author inspect-global examples/config/global.toml --json
```

## Dev checks

```bash
uv run pytest
uv run ruff check .
```

## Where contracts live

If behavior, semantics, and implementation seem to disagree, treat these docs as the contract target:

- `docs/ARCHITECTURE.md`
- `docs/CARD_SPEC.md`
- `docs/ADAPTER_SPEC.md`
- `docs/CLI_SPEC.md`
- `docs/AUTH_AND_SESSION_MODEL.md`
- `docs/DAYTRADING_GUARDRAILS.md`
- `docs/SIM_ARTIFACT_SPEC.md`
- `docs/SCENARIO_SPEC.md`
- `docs/MIGRATION_PLAN.md`
- `docs/TOPOLOGY.md`

## Agent-safe operating posture

Agents can safely:

- draft/edit card/deck/global/auth manifests
- run `validate-*` and `inspect-*` commands
- update docs/spec wording and examples
- run tests/lint and report receipts

Agents should **not** claim yet:

- live execution readiness
- real replay artifact generation from runtime
- operator governance state machine completeness
- broker-integrated execution behavior

Keep credentials/session secrets out of repo files and examples.
