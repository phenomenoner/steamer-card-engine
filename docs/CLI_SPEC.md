# CLI Specification

## Goal

The CLI is the primary management surface for cards, decks, auth profiles, replay/live-sim jobs, and operator controls.

It should be friendly to humans and automation, including agent-assisted workflows.

## Command families

### 1. Auth / Session commands

Used for validating auth profiles and inspecting logical session posture without inventing hidden state.

Examples:

```bash
steamer-card-engine auth validate-profile ./profiles/fubon.paper.toml
steamer-card-engine auth inspect-profile ./profiles/fubon.paper.toml
steamer-card-engine auth inspect-session --json
```

Responsibilities:

- validate login mode shape
- show capability expectations (market data only, trade enabled, etc.)
- inspect current logical session and health status
- help operators confirm the intended safety boundary before live expansion

### 2. Authoring commands

Used for creating and validating product artifacts.

Examples:

```bash
steamer-card-engine author init-card gap-reclaim
steamer-card-engine author validate-card ./cards/gap_reclaim.toml
steamer-card-engine author validate-deck ./decks/tw_cash_intraday.toml
steamer-card-engine author validate-global ./config/global.toml
steamer-card-engine author inspect-card ./cards/gap_reclaim.toml
steamer-card-engine author inspect-deck ./decks/tw_cash_intraday.toml --cards-dir ./cards
steamer-card-engine author inspect-global ./config/global.toml
```

Responsibilities:

- create scaffolds
- validate manifests
- inspect card metadata
- verify symbol-pool, capital-control, and feature-requirement shape
- package reproducible card/deck specs

### 3. Replay / Sim commands

Used for replay evaluation and live-sim execution paths with shared runtime contracts.

Examples:

```bash
steamer-card-engine replay run --deck ./examples/decks/tw_cash_intraday.toml --date 2026-03-11 --baseline-dir /path/to/legacy/baseline/day --scenario-spec ./scenarios/tw-gap-reclaim-20260311.json
steamer-card-engine replay inspect run-20260311-01
steamer-card-engine sim run-live --deck ./examples/decks/tw_cash_intraday.toml --dry-run --scenario-id tw-gap-reclaim.twse.2026-03-11.full-session
```

Responsibilities:

- submit replay jobs
- run live-sim sessions without live broker execution
- inspect replay/live-sim outputs
- compare card variants
- capture and echo ScenarioSpec identity (`scenario_id` + core scenario knobs)
- export decision receipts

### 4. SIM comparability commands (M1 foundation)

Used for baseline normalization and baseline-vs-candidate bundle comparison in the sim-only M1 lane.

Examples:

```bash
steamer-card-engine sim normalize-baseline \
  --baseline-dir /path/to/legacy/baseline/day \
  --output-dir /tmp/baseline-bundle \
  --session-date 2026-03-13 \
  --scenario-id tw-paper-sim.twse.2026-03-13.full-session

steamer-card-engine sim compare \
  --baseline /tmp/baseline-bundle \
  --candidate /tmp/candidate-bundle \
  --output-dir /tmp/compare
```

Responsibilities:

- normalize legacy baseline artifacts (`decisions.jsonl` + tick/trade sources) into a v1-shaped bundle
- keep capability posture explicit (`trade_enabled=false`)
- emit comparator hard-fail reasons for scenario/execution-model mismatches
- write scaffold compare outputs (`compare-manifest.json`, `diff.json`, `summary.md`)

### 5. Operator commands

Used for controlled runtime and live-adjacent governance.

Examples:

```bash
steamer-card-engine operator status
steamer-card-engine operator arm-live --deck approved_tw_cash_main
steamer-card-engine operator disarm-live
steamer-card-engine operator flatten --mode final-auction
```

Responsibilities:

- inspect runtime health
- view active deck, auth/session state, and adapter state
- arm/disarm live mode
- inspect recent intents, blocks, and execution receipts
- trigger guarded flatten workflows when policy allows

## Governance rules

- Authoring commands can be widely available.
- Replay and live-sim commands are broader, but still audited.
- Operator commands require stronger permissions and should map to explicit approvals.
- Auth/session inspection should expose capability boundaries clearly enough that a user can see whether trade permission is present.

## Output conventions

The CLI should support:

- concise human-readable output by default
- structured JSON output for automation
- stable exit codes

### Exit codes (current + recommended)

- `0`: success
- `1`: CLI usage error / unhandled command / general failure
- `2`: validation/normalization failure (manifest or sim command input/schema errors)
- `3`: comparison completed but failed hard gates (`sim compare` status=`fail`)

(Tests already assert `2` for validation errors; keep this stable.)

Suggested flags:

- `--json`
- `--verbose`
- `--dry-run`
- `--strict`
- `--profile`

## State handling

The CLI should avoid magical hidden state.

Preferred inputs:

- explicit file paths
- explicit deck names
- explicit auth/profile selection
- explicit mode selection (`replay-sim`, `live-sim`, `live`)

The CLI should never make live authority ambiguous.

## Scenario identity inputs (contract target)

Replay/live-sim submissions should eventually accept one of:

- `--scenario-spec <path>` (preferred)
- explicit identity flags that can be converted into ScenarioSpec-equivalent fields

At minimum, submitted job metadata should carry:

- `scenario_id`
- symbol set identity
- session date/slice
- event source identity
- timezone/calendar
- execution/cost model knobs
- determinism posture + seed

Reference contract: `docs/SCENARIO_SPEC.md`.

Current reality: this is a docs-level target; strict runtime enforcement is not complete yet.

## v0.1 implementation notes

Current implementation status:

- ✅ `auth validate-profile` / `auth inspect-profile`
- ✅ `author validate-card` / `author inspect-card`
- ✅ `author validate-deck` / `author inspect-deck`
- ✅ `author validate-global` / `author inspect-global`
- ✅ `sim normalize-baseline` (legacy baseline → v1-shaped M1 bundle)
- ✅ `sim compare` (hard-fail gates + scaffold compare report)
- ✅ `replay run` emits candidate v1 bundles (legacy-bridge emitter for M1, with explicit provenance)
- ⏳ operator execution remains placeholder

Next evolution order remains:

1. launch replay jobs
2. inspect replay/live-sim receipts
3. expose guarded operator actions

## Suggested stable artifacts

Replay and live-sim jobs should converge on a stable artifact set such as:

- run manifest
- event source identity
- feature/synthesizer versions
- intent receipts
- risk/execution receipts
- summary metrics

That keeps agent-assisted workflows reviewable instead of theatrical.
