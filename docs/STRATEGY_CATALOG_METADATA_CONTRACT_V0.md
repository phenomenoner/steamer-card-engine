# Strategy catalog metadata contract v0

This document defines a **thin, discovery-only** metadata layer that sits *above* `steamer-card-engine` card manifests.

It is intentionally **not** part of the runtime execution contract.
The purpose is to make cards easier to *find*, *group*, and *inspect* (by humans and tooling) without diluting existing card/deck/executor ownership.

## Goals

- Provide a lightweight catalog/index that can answer questions like:
  - “Which cards are relevant under this market regime?”
  - “What are the common aliases people use for this card?”
  - “What evidence/tools are expected before we treat this card as ready for operator review?”
- Keep metadata **outside** card manifests so the execution boundary stays strict.

## Hard boundaries (non-goals)

- **No execution semantics** (no enable/disable, no routing, no order placement, no risk gating).
- **No runtime authority changes**: `StrategyExecuter_Steamer-Antigravity` ownership is unchanged.
- This catalog is **advisory / discovery** only.

## Contract surface

### Catalog file

- **Format:** TOML (built-in `tomllib`, no new dependencies)
- **Schema version (required):** `schema_version = "strategy_catalog_metadata.v0"`
- **Entries:** array-of-tables at `[[strategies]]`

Recommended (optional) top-level fields:

- `catalog_id` (string)
- `updated_at` (string, ISO-8601 timestamp)
- `notes` (string)

### Strategy entry (`[[strategies]]`)

Required:

- `card_id` (string)
  - Must match the card manifest `card_id` exactly.

Discovery-only fields (in scope for v0):

- `display_name` (string, optional)
  - Human-friendly name for discovery surfaces. (May mirror the card manifest `name`, but does not have to.)
- `aliases` (`list[str]`, optional)
  - Alternative search terms / nicknames.
- `default_priority` (int, optional)
  - Ordering hint for *lists* only. Higher means “show earlier”.
- `market_regimes` (`list[str]`, optional)
  - Descriptive tags such as `open-drive`, `trend`, `range`, `high-vol`, `low-liquidity`.
  - **Not** a gating mechanism.
- `required_evidence` (`list[str]`, optional)
  - Human-readable evidence expectations (e.g. replay bundle counts, slippage checks).
- `required_tools` (`list[str]`, optional)
  - Human-readable tool expectations (commands, notebooks, dashboards).

Validation rules (minimum):

- `card_id` must be unique across entries.
- `aliases`, `market_regimes`, `required_evidence`, `required_tools` must be arrays of non-empty strings.
- No duplicates inside any list field.

## Example

See: `examples/catalog/strategy_catalog_metadata.v0.toml`

```toml
schema_version = "strategy_catalog_metadata.v0"
catalog_id = "steamer-card-engine.sample"
updated_at = "2026-03-27T00:00:00Z"
notes = "Sample catalog metadata. Discovery-only; not used for execution."

[[strategies]]
card_id = "gap-reclaim-v1"
display_name = "Gap Reclaim"
aliases = ["gap reclaim", "gap-reclaim", "reclaim"]
default_priority = 50
market_regimes = ["open-drive", "mean-revert", "high-vol"]
required_evidence = ["replay_bundle>=20_sessions", "slippage_check"]
required_tools = ["steamer-card-engine replay run", "steamer-card-engine sim compare"]
```

## Implementation posture

v0 is expected to land as:

1. a sample catalog file under `examples/`
2. a read-only loader + minimal CLI inspect/query surface

Any future “execution-relevant” metadata MUST be a separate contract and should not be smuggled into this discovery catalog.
