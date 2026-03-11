# CLI Specification

## Goal

The CLI is the primary management surface for cards, decks, replay jobs, and operator controls.

It should be friendly to humans and automation, including agent-assisted workflows.

## Command families

### 1. Authoring commands

Used for creating and validating product artifacts.

Examples:

```bash
steamer-card-engine author init-card gap-reclaim
steamer-card-engine author validate-card ./cards/gap_reclaim.toml
steamer-card-engine author build-deck ./decks/tw_cash_intraday.toml
```

Responsibilities:

- create scaffolds
- validate manifests
- inspect card metadata
- package reproducible card/deck specs

### 2. Replay commands

Used for backtesting-like evaluation with shared runtime contracts.

Examples:

```bash
steamer-card-engine replay run --deck ./examples/decks/tw_cash_intraday.toml --date 2026-03-11
steamer-card-engine replay inspect run-20260311-01
```

Responsibilities:

- submit replay jobs
- inspect replay outputs
- compare variants
- export decision receipts

### 3. Operator commands

Used for controlled runtime and live-adjacent governance.

Examples:

```bash
steamer-card-engine operator status
steamer-card-engine operator arm-live --deck approved_tw_cash_main
steamer-card-engine operator disarm-live
```

Responsibilities:

- inspect runtime health
- view active deck and adapter state
- arm/disarm live mode
- inspect recent intents, blocks, and execution receipts

## Governance rules

- Authoring commands can be widely available.
- Replay commands are broader, but still audited.
- Operator commands require stronger permissions and should map to explicit approvals.

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

## State handling

The CLI should avoid magical hidden state.

Preferred inputs:

- explicit file paths
- explicit deck names
- explicit environment/profile selection

## v1 implementation notes

This repo currently includes a small placeholder CLI to lock in vocabulary and package layout. It does not yet implement replay or operator control.

The placeholder should evolve in this order:

1. validate manifests
2. inspect cards/decks
3. launch replay jobs
4. inspect runtime receipts
5. expose guarded operator actions
