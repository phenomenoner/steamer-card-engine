# Migration Plan

## Why a migration plan exists

The current stack already has real value. Throwing it away and pretending a greenfield rewrite is safer would be fiction.

This migration plan treats the existing Steamer stack as the execution reality we are productizing.

## Current reference points

From the existing `StrategyExecuter_Steamer-Antigravity` repo:

- `sdk_manager_async.py` = login/session handling, websocket orchestration, subscription distribution, reconnect behavior
- `strategy_async.py` = strategy engine, state accumulation, order lifecycle handling, recorder integration, and risk-heavy execution behavior
- `magicbox/gates.py` = strategy gating logic
- `magicbox/config.py` = mixed runtime / strategy configuration
- `magicbox/recorder.py` = non-blocking recording path for ticks, decisions, and order events

## Migration insights worth preserving

The new repo should explicitly learn from the old one without pretending those behaviors are already implemented here.

Important carry-over lessons:

1. **Shared connection management matters.** The current stack already does websocket load-balancing and resubscription work.
2. **Account selection matters.** Active account routing is not cosmetic.
3. **`user_def` matters.** Mixed order-change / fill / active-order streams need a routing marker to avoid cross-card confusion.
4. **Recorder behavior matters.** Non-blocking tick/decision/order recording is part of making replay credible.
5. **Rate limits and connection limits matter.** Day-trading systems do not get to ignore them.
6. **Latency matters.** Emergency stop and flatten behavior are architecture concerns, not just config fields.

## Productization move

We are pulling those concerns apart into clearer product contracts.

### Current -> target mapping

- `sdk_manager_async.py`
  - **current role:** vendor SDK orchestration, login, reconnect, shared websocket handling
  - **target role:** source material for `AuthSessionManager`, `MarketDataAdapter`, and market-data connection planning inside `MarketDataHub`

- `strategy_async.py`
  - **current role:** combined card host + intent decision + execution + risk + order lifecycle routing
  - **target role:** source material to separate into `CardRuntime`, `IntentAggregator`, `RiskGuard`, and `ExecutionEngine`

- `magicbox/gates.py`
  - **current role:** strategy gates
  - **target role:** conceptual ancestor of productized `Card` units

- `magicbox/config.py`
  - **current role:** mixed runtime and strategy configuration
  - **target role:** split into `Global Config`, deck config, auth profile config, and card parameters

- `magicbox/recorder.py`
  - **current role:** asynchronous recording of runtime activity
  - **target role:** input model for recorder/audit contracts and replay artifacts

## Phased migration

### Phase 0 — Public boundary freeze

Deliverables:

- product scope
- architecture spec
- card/adapter/CLI contracts
- auth/session model
- day-trading guardrail spec
- migration checkpoints

Exit criteria:

- repo shape is understandable
- no fake claims about live readiness
- public-facing positioning is honest and product-shaped

### Phase 1 — Contracted manifests and session model

Deliverables:

- card manifest schema with symbol pool, capital control, stop/take-profit, forced-exit fields
- deck/global config schema with policy overlays
- auth profile schema for the two supported login modes
- logical `SessionContext` model

Exit criteria:

- manifest validation can catch missing or malformed policy sections
- session capabilities are inspectable before any live-adjacent action

### Phase 2 — Recordable market data and replay/live-sim path

This phase should **freeze the core artifact / receipt contracts first** (events, features, intents, risk decisions, execution receipts).

Only after those contracts are stable should we invest in adapter shims, otherwise we risk encoding legacy behavior into unstable schemas.

Concrete acceptance target for this phase:
- Milestone M1 — SIM comparability (replay-sim first, then live-sim-attached): `docs/MILESTONE_M1_SIM_COMPARABILITY.md`

Deliverables:

- ScenarioSpec contract freeze for cross-lane identity (`docs/SCENARIO_SPEC.md`)
- normalized market event schema
- recorder contract for market data, decisions, and order lifecycle events
- replay runner skeleton
- live-sim execution path using the same intent/risk/execution contracts where possible
- feature/synthesizer pipeline skeleton

Practical source material:

- existing recorder outputs
- current replay artifacts
- existing gate inputs/state snapshots

Exit criteria:

- one or more existing strategy ideas can be expressed as replayable cards
- market data can be recorded and replayed with stable contracts
- baseline and candidate lanes can declare the same ScenarioSpec identity for a test run
- comparisons fail fast unless ScenarioSpec fingerprint and `execution_model` disclosure match
- replay sim and live sim are clearly differentiated from live

### Phase 3 — Adapter shim from current stack

Deliverables:

- TW cash market-data adapter shim informed by `sdk_manager_async.py`
- broker adapter shim informed by current order lifecycle code
- session/auth integration across marketdata + trading/account surfaces
- structured capability, connection-limit, and rate-limit metadata

Exit criteria:

- runtime code no longer needs direct vendor conditionals everywhere
- connection and subscription behavior become inspectable product contracts

### Phase 4 — Intent / risk / execution split

Deliverables:

- cards emit intents only
- feature synthesis separated from card implementation by default
- intent aggregation logic separated from broker requests
- risk checks extracted into explicit policy layer
- execution engine owns broker-side state transitions and event routing

Exit criteria:

- a card cannot directly place an order even by accident
- order changes / fills / active reports are filtered by active account + `user_def`
- replay and live-sim can share the same intent boundary

### Phase 5 — Controlled operator workflow

Deliverables:

- operator CLI commands for status, arm/disarm, flatten, and inspection
- approval and audit hooks
- emergency stop, forced-exit, and final-auction flatten controls
- dry-run/live-sim session proving path

Exit criteria:

- live control remains operator-governed
- agent workflows assist authoring/replay/setup but do not silently gain live authority
- the operator can reason about latency-sensitive exit behavior before trusting live use

## What should not happen during migration

- big-bang rewrite of everything at once
- mixing new card abstractions directly into legacy execution code without contracts
- promising multi-broker portability before adapter contracts are proven on one bounded path
- letting replay-only cards leak into live usage without lifecycle state and approval
- treating auth/session differences across vendors as an implementation detail to ignore

## Suggested first implementation slices after this seed repo

1. Define concrete `MarketEvent`, `FeatureSnapshot`, `Intent`, `ExecutionRequest`, and `OrderLifecycleEvent` models.
2. Add manifest validation for card/deck/auth profile files.
3. Express one existing strategy idea as a replay-only card with symbol pool + stop/take-profit policy.
4. Build a minimal replay runner that consumes recorded events and produces receipts.
5. Wrap the current shared market-data/login behavior behind `AuthSessionManager` + first adapter shims.
6. Split order-event routing, risk decisions, and execution requests before touching live controls.
