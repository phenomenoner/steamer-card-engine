# Migration Plan

## Why a migration plan exists

The current stack already has real value. It would be a mistake to throw that away and pretend a greenfield rewrite is safer.

This migration plan treats the existing codebase as the execution reality we are productizing.

## Current reference points

From the existing `StrategyExecuter_Steamer-Antigravity` repo:

- `sdk_manager_async.py` = connection, auth, websocket, and market-data/session plumbing
- `strategy_async.py` = strategy engine, state accumulation, order lifecycle, and risk-heavy execution behavior
- `magicbox/*` = strategy gate logic, config, recorder support

## Productization move

We are pulling those concerns apart into clearer product contracts.

### Current -> target mapping

- `sdk_manager_async.py`
  - **current role:** vendor SDK orchestration and shared websocket handling
  - **target role:** early implementation reference for `MarketDataAdapter` and connection lifecycle within `MarketDataHub`

- `strategy_async.py`
  - **current role:** combined card logic host + intent decision + execution + risk + order management
  - **target role:** source material to separate into `CardRuntime`, `IntentAggregator`, `RiskGuard`, and `ExecutionEngine`

- `magicbox/gates.py`
  - **current role:** strategy gates
  - **target role:** conceptual ancestor of productized `Card` units

- `magicbox/config.py`
  - **current role:** mixed runtime and strategy configuration
  - **target role:** split into `Global Config`, deck config, and card parameters

## Phased migration

### Phase 0 — Product boundary freeze

Deliverables:

- product scope
- architecture spec
- card/adapter/CLI contracts
- migration checkpoints

Exit criteria:

- repo shape is understandable
- no fake claims about live readiness

### Phase 1 — Replay-shaped contracts

Deliverables:

- normalized market event schema
- card manifest format
- deck/global config format
- replay runner skeleton

Practical source material:

- existing recorder outputs
- existing gate inputs/state snapshots

Exit criteria:

- one or more existing strategy ideas can be expressed as card definitions for replay
- replay data path can be validated without touching live order flow

### Phase 2 — Adapter shim from current stack

Deliverables:

- TW cash market-data adapter shim informed by `sdk_manager_async.py`
- broker adapter shim informed by current order lifecycle code
- structured capability metadata

Exit criteria:

- adapter contracts are strong enough that runtime code no longer needs direct vendor conditionals everywhere

### Phase 3 — Intent / risk / execution split

Deliverables:

- cards emit intents only
- intent aggregation logic separated from broker requests
- risk checks extracted into explicit policy layer
- execution engine owns broker-side state transitions

Exit criteria:

- a card cannot directly place an order even by accident
- replay and dry-run can share the same intent boundary

### Phase 4 — Controlled operator workflow

Deliverables:

- operator CLI commands for status, arm/disarm, and inspection
- approval and audit hooks
- dry-run session proving path

Exit criteria:

- live control remains operator-governed
- agent workflows assist authoring/replay but do not silently gain live authority

## What should not happen during migration

- big-bang rewrite of everything at once
- mixing new card abstractions directly into legacy execution code without contracts
- promising multi-broker portability before adapter contracts are proven on one bounded path
- letting replay-only cards leak into live usage without lifecycle state and approval

## Suggested first implementation slices after this seed repo

1. Define concrete `MarketEvent`, `Intent`, and `ExecutionRequest` models.
2. Express one existing strategy idea as a replay-only card.
3. Build a minimal replay runner that consumes recorded events.
4. Wrap the current shared market-data behavior behind a first `MarketDataAdapter` shim.
5. Split risk decisions from execution requests before touching live controls.
