# Setup Guide (Human + Agent)

## Reality check first

`steamer-card-engine` is a **docs-first seed runtime**.

What is working today:

- manifest loading + validation (`auth`, `card`, `deck`, `global`)
- manifest inspection summaries (`inspect-*`)
- basic test coverage for those CLI surfaces

What is still placeholder/stub:

- `operator status/inspect` (placeholder output)
- runtime component split is mostly structural naming, not full execution behavior
- `replay run` is now available for M1 candidate bundle emission, but still uses a legacy-bridge path (not full native runtime parity)

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

## Steamer Dashboard demo (read-only, committed fixture index)

Truth contract for the local browser demo:

- top-level tabs: `Live Sim` + `Strategy Powerhouse / Strategy Cards`
- strategy tab opens with a thin read-only active-family baton line sourced from local proposal/active plan artifacts
- execution authority remains in `steamer-card-engine`; `strategy-powerhouse` stays research / packaging / control-plane support only

- discovered fixture dates: `2026-03-06`, `2026-03-10`, `2026-03-12`, `2026-03-20`, `2026-03-24`, `2026-03-25`, `2026-03-26`, `2026-03-27`, `2026-03-30`, `2026-03-31`, `2026-04-01`, `2026-04-02`, `2026-04-08`
- hero day: `2026-04-08`
- discovery source: committed compare manifests with one representative comparison bundle per session date
- current selection rule for same-date variants: pass status first, then comparison family priority (`manual-live-paired` > `replay-sim` > `prep` > `phase3` > other), then comparison directory name
- topology: unchanged
- transaction/PnL surfaces: intentionally truthful empty/incomplete panels when fills/orders/positions are empty in the committed artifacts
- still unsupported in the browser surface: showing multiple compare variants for the same session date as separate dashboard entries

Frontend prerequisites:

- Node.js `>=22`
- npm

Install frontend dependencies:

```bash
cd frontend
npm install --include=dev
cd ..
```

Build the browser bundle:

```bash
cd frontend
npm run build
cd ..
```

Launch the local Steamer Dashboard demo inside the container/runtime:

```bash
uv run uvicorn steamer_card_engine.dashboard.api:create_app --factory --host 0.0.0.0 --port 8000
```

### If you want to open it from the parent system browser

Binding `127.0.0.1` **inside the container** is not enough for the parent/host browser.
Use the same topology idea as `pm-dashboard`: run this dashboard as an **outer compose sibling service**.

Authoritative outer compose contract for this environment:

- compose file: `/workspace/docker-compose.yml`
- service name: `steamer-dashboard`
- image build file: `/workspace/steamer-dashboard.Dockerfile`
- host publish: `127.0.0.1:${STEAMER_DASHBOARD_PORT:-8780}:8780`
- runtime mount: `openclaw-config:/root/.openclaw:ro`
- repo root inside container: `/root/.openclaw/workspace/steamer-card-engine`
- import path inside container comes from `steamer-dashboard.Dockerfile` via `PYTHONPATH=/root/.openclaw/workspace/steamer-card-engine/src`

Then open from the parent system:

- `http://127.0.0.1:8780/` for the browser dashboard
- `http://127.0.0.1:8780/api/dates` for the discovered committed fixture index
- `http://127.0.0.1:8780/api/docs` for the read-only API docs

### Outer compose launch

```bash
cd /workspace
docker compose build steamer-dashboard
docker compose up -d steamer-dashboard
docker compose ps steamer-dashboard
```

Health check:

```bash
curl -sS http://127.0.0.1:8780/api/health
```

## M1 evidence-pack operator workflow (sim-only)

Current pre-sprint evidence index:

- `docs/M1_EVIDENCE_PACK_INDEX.md`

Acceptance gate (frozen):

- `docs/M1_EVIDENCE_PACK_ACCEPTANCE_CONTRACT.md`

Minimal workflow to add one new scenario:

```bash
# 1) emit baseline bundle
uv run steamer-card-engine sim normalize-baseline \
  --baseline-dir /abs/path/to/tw-paper-sim/YYYY-MM-DD \
  --output-dir runs/baseline-bot/YYYY-MM-DD/<baseline_run_id> \
  --session-date YYYY-MM-DD \
  --scenario-id tw-paper-sim.twse.YYYY-MM-DD.full-session \
  --run-id <baseline_run_id> \
  --json

# 2) emit candidate bundle (truthful candidate provenance)
uv run steamer-card-engine replay run \
  --deck examples/decks/tw_cash_intraday.toml \
  --date YYYY-MM-DD \
  --scenario-id tw-paper-sim.twse.YYYY-MM-DD.full-session \
  --baseline-dir /abs/path/to/tw-paper-sim/YYYY-MM-DD \
  --output-root runs \
  --run-id <candidate_run_id> \
  --json

# 3) compare (decision-grade outputs)
uv run steamer-card-engine sim compare \
  --baseline runs/baseline-bot/YYYY-MM-DD/<baseline_run_id> \
  --candidate runs/steamer-card-engine/YYYY-MM-DD/<candidate_run_id> \
  --output-dir comparisons/<baseline_run_id>__<candidate_run_id> \
  --json
```

The compare step should materialize:

- `compare-manifest.json` — pass/fail posture + hard-gate reasons
- `diff.json` — machine-readable decision-grade diff payload
- `summary.md` — human review summary

Operator checks before claiming acceptance:

- comparator `status=pass`
- no hard-fail reasons
- scenario identity and execution model are consistent
- candidate manifest keeps `trade_enabled=false`
- per-scenario review note + artifact pointers are written under `docs/receipts/`

Artifact packaging hygiene for committed evidence:

- follow `docs/EVIDENCE_PACKAGING_HYGIENE.md`
- duplicate `event-log.jsonl` payloads may be symlinked to a canonical copy only when content hash is identical
- when exporting a standalone run bundle, use `tar --dereference` so symlinked logs are materialized in the archive

> Note: `/abs/path/to/tw-paper-sim/YYYY-MM-DD` is intentionally a placeholder for your local or mounted baseline artifact root.

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
- full native runtime behavior parity in replay (current path is a legacy-bridge emitter)
- operator governance state machine completeness
- broker-integrated execution behavior

Keep credentials/session secrets out of repo files and examples.
