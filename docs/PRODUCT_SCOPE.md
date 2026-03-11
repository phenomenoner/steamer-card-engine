# Product Scope

## Thesis

Build a product-shaped runtime for **card-based intraday strategy operations** on Taiwan cash equities.

The runtime should let researchers and agents author cards, organize decks, and manage configuration through a CLI, while keeping live execution and risk governance under experienced operators.

## Product promise

1. **One shared market-data connection model** rather than one feed per strategy card.
2. **Many strategy cards per engine/deck**, with explicit identity, parameters, and auditability.
3. **Intent-first design**: cards express intent; the runtime governs whether that intent becomes a broker action.
4. **Adapter-swappable I/O** so the runtime is not permanently fused to one broker or market-data API.
5. **Replay-first productization** so contracts can harden before live control expands.

## Primary users

### 1. Operator
Owns live permissions, risk limits, runtime health, and deployment posture.

### 2. Researcher / strategist
Creates and iterates cards, variants, thresholds, and deck composition.

### 3. Agent-assisted workflow
Helps draft cards, specs, config, and replay jobs, but does not automatically receive unrestricted live execution authority.

## v1 scope

- Taiwan cash intraday only
- Shared market-data hub
- Single runtime instance / single deck at a time
- Multiple cards and card variants inside the deck
- CLI-managed card/deck/global config
- Replay runner and dry-run path as first-class features
- Audit-friendly event and intent flow
- Replaceable `MarketDataAdapter` and `BrokerAdapter` interfaces

## Non-goals for v1

- Futures/options support
- Smart order routing across multiple brokers
- Fully dynamic plugin loading without operator controls
- Autonomous live trading authority for arbitrary agents
- Portfolio management across multiple independent engines
- Claiming production-grade reliability before replay and dry-run contracts are proven

## Product boundaries

### Included
- Contracts
- CLI surface
- Core runtime decomposition
- Adapter interfaces
- Migration plan from the current engine

### Deliberately deferred
- Deep strategy library
- GUI/dashboard
- Hosted multi-tenant service
- Real broker credential workflow in this repo

## Success criteria for the seed repo

- A new contributor can understand the product shape in under 15 minutes.
- The repo makes the difference between **card authoring** and **execution governance** obvious.
- The CLI vocabulary is stable enough to guide future implementation.
- Migration from the current `sdk_manager_async.py` + `strategy_async.py` world is phased, not hand-wavy.
- Nothing in the docs over-claims live readiness.

## Risks to manage early

- Over-fitting the product model to a single current strategy implementation
- Letting cards bypass risk and execution governance
- Conflating replay behavior with live behavior
- Locking adapter contracts too tightly to one broker SDK
- Creating a plugin model that is too open before governance exists
