# 2026-04-23 — steamer-card-engine observer private bridge v0

## Verdict

Before wiring any real live(sim) source, the repo should own a **deterministic read-only observer projection bridge**.

That lets the future private adapter do only one thing:
- emit sanitized observer events

And lets the public-safe projection layer do one thing:
- rebuild presentation state truthfully from those events

## Why this slice is real progress

Without this bridge, the system risks splitting state logic across:
- private adapter emitters
- ad hoc mock bootstrap assembly
- frontend reconciliation code

That would create drift and make the first real adapter attachment noisy and harder to audit.

## Bounded slice

Build a bridge that:
- accepts sanitized observer events
- applies them in seq order
- rebuilds candles / markers / position / orders / fill / health / timeline
- emits a bootstrap-compatible snapshot

The bridge must stay public-safe and read-only.

## Contract

### Input
- sanitized `ObserverEvent` sequence
- stable session metadata (`session_id`, `engine_id`, `session_label`, `market_mode`, `symbol`, `timeframe`)

### Output
- `ObserverBootstrap`
- timeline slice
- latest seq/freshness state

### Invariants
- seq monotonicity must be preserved
- snapshot rebuilt from events must match the same event stream on reconnect
- marker timestamps must align to bar times
- no strategy internals or broker/raw engine shapes enter the bootstrap surface

## Topology statement

Topology unchanged.
This is a projection-boundary hardening slice only.
