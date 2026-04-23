# Execution packet — steamer-card-engine observer private bridge v0

## Objective

Advance the observer sidecar from a mock-only surface to a **private-adapter-ready bridge boundary** without leaking private mapping logic into the public-safe repo surface.

The proof for this slice is:

> the repo contains a reusable read-only observer projection bridge that can ingest sanitized observer events and rebuild bootstrap state deterministically, so a future private adapter only needs to emit the contract rather than re-decide projection rules in the UI layer.

## In scope
- public-safe observer bridge contract
- read-only projection logic from observer events to bootstrap/timeline state
- in-memory projection store shape suitable for one-session demo/runtime
- mock path refactored to use the bridge instead of duplicating presentation state by hand
- focused tests for projection/rebuild invariants

## Out of scope
- real private adapter wiring
- broker/runtime/engine integration
- auth/network/deploy hardening
- multi-session fanout infra
- write/control surfaces

## Boundary rules
- no private field mapping or engine-grade object shapes land in this repo slice
- bridge consumes only sanitized observer events
- projection remains read-only and presentation-grade
- browser payload contract must stay compatible with the existing observer UI slice

## First artifact expected
- `src/steamer_card_engine/observer/bridge.py` with deterministic projection helpers
- mock observer bundle rebuilt through the bridge
- verifier proving snapshot rebuild from events is stable

## Verifier plan
- targeted bridge unit tests
- `pytest tests/test_dashboard.py -q`
- frontend production build still succeeds

## Stop-loss
Stop and report if:
- the bridge starts pulling engine/broker concerns into the public repo
- projection logic expands into hidden strategy explainability/state internals
- the slice requires real payload captures to keep moving

## WAL / closure
- checkpoint note if projection boundary changes
- private ledger note only when milestone truth changes
- public push remains intentionally gated
