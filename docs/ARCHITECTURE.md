# Architecture

## Design stance

The architecture separates **authoring / management** concerns from **execution** concerns.

That split is not cosmetic. It is the main safety boundary of the product.

A second stance is equally important: **low latency is first-class for day trading**. The hot path should avoid unnecessary blocking I/O, duplicated feature computation, and ambiguous ownership of order lifecycle state.

## Two planes

### 1. Authoring / Management Plane

Responsible for:

- card manifests
- deck composition
- global configuration
- auth profile validation
- replay orchestration
- versioning and packaging
- operator-reviewed activation changes

Interfaces:

- CLI commands
- config files
- replay artifacts
- audit logs and reports

### 2. Execution Plane

Responsible for:

- authenticating once and distributing usable session context
- ingesting market data
- normalizing market events
- synthesizing derived features / time-series views
- evaluating cards
- aggregating intents
- applying risk policy
- producing execution requests
- interacting with broker adapters

The execution plane must remain governed, observable, and bounded.

## Core concepts

### Card
A strategy unit that consumes normalized runtime context plus derived features and emits `Intent` objects.

A card:

- can be parameterized
- can be enabled/disabled
- can have variants
- can declare its own symbol pool
- can declare its own stop / take-profit / forced-exit logic
- can declare capital-control hints within bounded contracts
- cannot submit broker orders directly

### Deck
A runtime bundle of cards plus ordering, precedence, policy overrides, and shared governance settings.

### Global Config
Engine-wide settings for:

- session calendar
- auth/session posture
- instrument universe
- capital and exposure
- risk gates
- adapters
- replay/live-sim behavior
- operator permissions

### Policy overlays (draft tighten/widen rules)

Deck and global config exist largely to **govern** cards.

Recommended default rule (safety-first): **cards may propose; deck/global/operator may tighten; widening requires explicit operator intent** (future).

| Policy area | Card declares | Deck may | Global may | Operator may |
|---|---|---|---|---|
| Symbol universe | `symbol_pool` (proposal) | allow/deny + merge rules | set market-wide scope/ceilings | clamp / override |
| Capital controls | max notional/positions (proposal) | tighten ceilings | set global ceilings | tighten / flatten |
| Risk policy | stop/take-profit/forced-exit (proposal) | tighten / reject | emergency stop + global gates | tighten + trigger guardrails |
| Feature requirements | `feature_requirements` | add shared requirements | define available pipelines | (governance only) |
| Live authority | (none) | select deck + intended posture | `live_enabled`, `dry_run` guardrails | arm/disarm / approve activation |

This is still a doc-level rule at v0.1 (not fully implemented); it exists to prevent “policy merge” becoming implicit and unsafe later.

### AuthSessionManager
A shared login/session module that authenticates once and shares session context across marketdata + trading/account surfaces where supported.

When the underlying vendor does **not** truly support a single session object, the manager still provides one logical session boundary and capability model for the rest of the runtime.

### FeaturePipeline / Synthesizers
A platform-owned layer that transforms raw events into reusable derived features, such as:

- rolling bars
- VWAP windows
- session highs/lows
- MACD or other indicators
- custom time-series views needed by cards

**Recommended design:** synthesizers belong in a separate platform module, not embedded independently inside every card.

Why:

- keeps card logic small and inspectable
- preserves replay/live parity
- avoids duplicate hot-path computation across cards
- makes feature provenance versionable and auditable

Cards may still keep tiny local state, but reusable time-series synthesis should live here.

### MarketDataAdapter
Normalizes external market-data streams into runtime events.

### BrokerAdapter
Translates runtime-approved execution requests into broker API calls and lifecycle updates.

## Runtime layers

```text
AuthSessionManager
  ├── MarketDataAdapter -> MarketDataHub -> FeaturePipeline -> CardRuntime
  └── Broker/Account surfaces -------------------------------> ExecutionEngine

CardRuntime
  -> IntentAggregator
      -> RiskGuard
          -> ExecutionEngine
              -> BrokerAdapter

Recorder / Audit Trail spans the full chain.
ReplayRunner and LiveSim reuse the same event, feature, intent, and execution contracts where possible.
```

## Component responsibilities

### AuthSessionManager

Responsibilities:

- validate login mode and credentials profile shape
- authenticate once where vendor capabilities allow it
- distribute session context to marketdata + trading/account surfaces
- classify session capabilities (market data only, trade enabled, account query enabled, etc.)
- manage re-auth / renewal / disconnect recovery
- expose structured session health to operators and CLI tools

### MarketDataHub

Responsibilities:

- own the shared market-data connection lifecycle
- plan subscriptions from global scope, deck scope, and enabled card symbol pools
- submit those subscriptions to connection management
- fan out normalized events to subscribed cards/components
- maintain subscription state and symbol routing
- expose recordable and replay-compatible event shapes

Rule of thumb: cards may **declare** symbol pools, but they do not open transport connections themselves.

### FeaturePipeline

Responsibilities:

- consume normalized market events
- compute shared derived features with stable versioning
- expose deterministic, replay-friendly snapshots to cards
- keep expensive indicator work out of per-card duplication when possible

### CardRuntime

Responsibilities:

- load card definitions and parameter sets
- provide card-local state containers
- route relevant events and feature snapshots to cards
- capture emitted intents and reasons
- preserve card/version/deck identity in downstream provenance

### IntentAggregator

Responsibilities:

- merge intents from multiple cards
- resolve duplicate or conflicting intents
- preserve provenance: which card, which version, which inputs, which feature versions
- produce a reviewable queue for downstream policy checks

### RiskGuard

Responsibilities:

- enforce engine-level, deck-level, and card-level risk limits
- apply day-trading guardrails such as emergency stops and forced exits
- reject, reduce, or delay intents
- distinguish replay policy, live-sim policy, and live policy when required

### ExecutionEngine

Responsibilities:

- turn approved intents into execution requests
- manage order lifecycle state
- track fills, cancellations, replaces, rejects, and session boundaries
- filter mixed broker events by active account number and `user_def`
- keep card-to-order provenance so cross-card confusion is avoided
- remain decoupled from card logic

The explicit `active_account + user_def` filtering rule is a migration lesson from the current Steamer stack, not an optional nicety.

### ReplayRunner / LiveSim

Responsibilities:

- feed historical or recorded events through the same core contracts
- support deterministic analysis where feasible
- simulate execution outcomes without touching live broker flow
- produce comparable receipts and summaries for review

## Trust and authority boundaries

### Cards are not trusted with live execution authority

Cards can express:

- entry interest
- exit interest
- urgency
- confidence
- sizing hints within bounded contracts
- symbol-pool requirements
- feature requirements

Cards cannot:

- directly access broker credentials
- directly place, cancel, or replace orders
- override risk policy
- open arbitrary new transport layers during live runtime
- silently bypass account / `user_def` routing rules

### Operator authority

Operator commands can:

- arm/disarm live mode
- change approved adapters or auth profiles
- approve deck activation
- set or tighten risk envelopes
- trigger or confirm flatten procedures
- inspect runtime health and recent decisions

## Observability model

The runtime should produce receipts for:

- auth/session establishment and capability state
- market event ingestion
- derived feature snapshots or hashes
- card evaluation results
- emitted intents
- risk decisions
- execution actions
- replay/live-sim run metadata

This is the minimum required to make agent-authored changes reviewable.

## Latency posture

The product should assume that some day-trading paths are latency-sensitive by nature.

Examples:

- emergency stop logic in a fast move
- short-side adverse moves near upper-limit lock conditions
- forced flatten near the close / final auction window

That implies:

- recorder/logging should be non-blocking where possible
- feature synthesis should be shared and predictable
- lifecycle routing should be structured, not string-parsed ad hoc
- rate limit and connection limit behavior must be modeled explicitly in adapters

## v0.1 simplifications

- one engine / one deck active at a time
- Taiwan stock intraday only
- one active market-data adapter
- one active broker adapter
- no arbitrary runtime plugin discovery
- no broker smart routing
- replay/live-sim before live expansion

## Future extension points

- additional market-data adapters with the same event contract
- additional broker adapters with the same execution contract
- richer feature pipelines and custom synthesizer packages
- multiple concurrent decks once governance and resource policy are mature
- more granular operator controls around auth/session and execution capabilities
