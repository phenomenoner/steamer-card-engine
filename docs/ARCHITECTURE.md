# Architecture

## Design stance

The architecture separates **authoring / management** concerns from **execution** concerns.

That split is not cosmetic. It is the main safety boundary of the product.

## Two planes

### 1. Authoring / Management Plane

Responsible for:

- card manifests
- deck composition
- global configuration
- validation
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

- ingesting market data
- normalizing market events
- evaluating cards
- aggregating intents
- applying risk policy
- producing execution requests
- interacting with broker adapters

The execution plane must remain governed, observable, and bounded.

## Core concepts

### Card
A strategy unit that consumes normalized market context and emits `Intent` objects.

A card:

- can be parameterized
- can be enabled/disabled
- can have variants
- cannot submit broker orders directly

### Deck
A runtime bundle of cards plus ordering, precedence, and shared governance settings.

### Global Config
Engine-wide settings for:

- session calendar
- instrument universe
- capital and exposure
- risk gates
- adapters
- replay behavior
- operator permissions

### MarketDataAdapter
Normalizes external market-data streams into runtime events.

### BrokerAdapter
Translates runtime-approved execution requests into broker-side actions.

## Runtime layers

```text
MarketDataAdapter
  -> MarketDataHub
      -> CardRuntime
          -> IntentAggregator
              -> RiskGuard
                  -> ExecutionEngine
                      -> BrokerAdapter

ReplayRunner sits beside the live path and reuses the same contracts where possible.
Recorder/Audit trail spans the full chain.
```

### MarketDataHub

Responsibilities:

- own the shared market-data connection lifecycle
- fan out normalized events to subscribed cards/components
- maintain subscription state and symbol routing
- expose replay-compatible event shapes

### CardRuntime

Responsibilities:

- load card definitions and parameter sets
- provide card-local state containers
- call card evaluation on each relevant event
- capture emitted intents and reasons

### IntentAggregator

Responsibilities:

- merge intents from multiple cards
- resolve duplicate/conflicting intents
- preserve provenance: which card, which version, which inputs
- produce a reviewable queue for downstream policy checks

### RiskGuard

Responsibilities:

- enforce engine-level and deck-level risk limits
- reject, reduce, or delay intents
- impose operator-defined constraints
- distinguish replay policy from live policy when required

### ExecutionEngine

Responsibilities:

- turn approved intents into execution requests
- manage order lifecycle state
- track fills, cancellations, and session boundaries
- remain decoupled from card logic

### ReplayRunner

Responsibilities:

- feed historical events through the same card/runtime contracts
- support deterministic analysis where feasible
- output comparable artifacts for decision review

## Trust and authority boundaries

### Cards are not trusted with live execution authority

Cards can express:

- entry interest
- exit interest
- urgency
- confidence
- sizing hints within bounded contracts

Cards cannot:

- directly access broker credentials
- directly place, cancel, or replace orders
- override risk policy
- arbitrarily subscribe new transport layers during live runtime

### Operator authority

Operator commands can:

- arm/disarm live mode
- change approved adapters
- approve deck activation
- set or tighten risk envelopes
- inspect runtime health and recent decisions

## Observability model

The runtime should produce receipts for:

- market event ingestion
- card evaluation results
- emitted intents
- risk decisions
- execution actions
- replay run metadata

This is the minimum required to make agent-authored changes reviewable.

## v1 simplifications

- one engine / one deck active at a time
- Taiwan cash intraday only
- no arbitrary runtime plugin discovery
- no broker smart routing
- dry-run and replay before live expansion

## Future extension points

- additional market-data adapters with the same event contract
- additional broker adapters with the same execution contract
- richer intent ranking or portfolio policies
- multiple concurrent decks once governance and resource policy are mature
