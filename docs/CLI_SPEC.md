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
steamer-card-engine author inspect-card ./cards/gap_reclaim.toml
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
steamer-card-engine replay run --deck ./examples/decks/tw_cash_intraday.toml --date 2026-03-11 --mode replay-sim
steamer-card-engine replay inspect run-20260311-01
steamer-card-engine sim run-live --deck ./examples/decks/tw_cash_intraday.toml --dry-run
```

Responsibilities:

- submit replay jobs
- run live-sim sessions without live broker execution
- inspect replay/live-sim outputs
- compare card variants
- export decision receipts

### 4. Operator commands

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

## v0.1 implementation notes

This repo currently includes a small placeholder CLI to lock in vocabulary and package layout. It does not yet implement replay, session management, or operator control.

The placeholder should evolve in this order:

1. validate auth/card/deck manifests
2. inspect cards/decks/profiles in human + JSON form
3. validate symbol-pool and feature requirements
4. launch replay jobs
5. inspect replay/live-sim receipts
6. expose guarded operator actions

## Suggested stable artifacts

Replay and live-sim jobs should converge on a stable artifact set such as:

- run manifest
- event source identity
- feature/synthesizer versions
- intent receipts
- risk/execution receipts
- summary metrics

That keeps agent-assisted workflows reviewable instead of theatrical.
