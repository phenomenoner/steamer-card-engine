# Product Scope

## Thesis

Build a product-shaped runtime for **card-based Taiwan stock intraday strategy operations**.

The runtime should let researchers and agents author cards, organize decks, validate manifests, and run replay/live-sim workflows through a stable CLI, while keeping live execution authority and risk governance under explicit operator control.

## Product promise

1. **One shared auth/session and market-data connection model** rather than one login/feed stack per strategy card.
2. **Many strategy cards per engine/deck**, each with explicit identity, symbol pool, parameters, and auditability.
3. **Intent-first design**: cards express intent and policy hints; the runtime governs whether those intents become broker actions.
4. **Low-latency by design** for day trading, especially around stop and forced-exit paths.
5. **Replay-first productization** so contracts harden before live control expands.
6. **Adapter-swappable I/O** so the runtime is not permanently fused to one broker or market-data API.
7. **Recordable and replayable market data**, with both replay sim and live sim as first-class execution modes.

## Primary users

### 1. Operator
Owns live permissions, session posture, risk limits, runtime health, active account selection, and deployment posture.

### 2. Researcher / strategist
Creates and iterates cards, variants, thresholds, symbol pools, and deck composition.

### 3. Agent-assisted workflow
Helps draft cards, validate configs, prepare replay jobs, and assist configuration setup. Agent assistance does **not** imply unrestricted live trading authority.

## v0.1 scope

- Taiwan stock intraday only
- Shared auth/session module for marketdata + trading/account surfaces where supported
- Shared market-data hub with subscription planning
- Single runtime instance / single deck at a time
- Multiple cards and card variants inside the deck
- Card-level symbol pools contributed into connection management when enabled
- Card-level entry, exit, capital control, and required feature declarations
- Separate feature/synthesizer pipeline for time-series and indicators
- CLI-managed card/deck/global config and auth profiles
- Replay runner and live-sim path as first-class features
- Read-only browser Mission Control observability over replay/live-sim artifacts
- Audit-friendly event, intent, risk, and execution receipts
- Replaceable `MarketDataAdapter` and `BrokerAdapter` interfaces
- Day-trading guardrails: emergency stop-loss, forced exit, final-auction flatten controls

## Non-goals for v0.1

- Futures/options support
- Smart order routing across multiple brokers
- Fully dynamic plugin loading without operator controls
- Autonomous live trading authority for arbitrary agents
- Portfolio management across multiple independent engines
- Claiming production-grade reliability before replay/live-sim contracts are proven
- Hiding broker/session complexity behind fake abstractions

## Product boundaries

### Included
- Contracts
- CLI surface
- Core runtime decomposition
- Auth/session model
- Day-trading risk model
- Adapter interfaces
- Migration plan from the current engine

### Deliberately deferred
- Deep strategy library
- Broker-connected or operator-authoritative GUI/control plane
- Hosted multi-tenant service
- Real credential storage implementation in this repo
- Multi-market abstraction beyond Taiwan cash

## Safety and authority stance

The product is intentionally **agent-assisted, operator-governed**.

That includes a practical safety boundary for some broker ecosystems:

- support login mode with `account + API key + cert + cert password`
- allow operators to provision API keys without trade permission when appropriate
- let agents help with config/replay/validation inside that boundary
- require stronger operator control before expanding into live trading authority

## Success criteria for the seed repo

- A new contributor can understand the product shape in under 15 minutes.
- The repo makes the difference between **card authoring**, **feature synthesis**, **risk governance**, and **execution** obvious.
- The CLI vocabulary is stable enough to guide future implementation.
- Migration from the current `sdk_manager_async.py` + `strategy_async.py` world is phased, not hand-wavy.
- The docs explain why latency matters for day-trading stops and forced exits.
- Nothing in the repo over-claims live readiness.

## Risks to manage early

- Over-fitting the product model to one current strategy implementation
- Letting cards bypass risk and execution governance
- Recomputing indicators independently inside many cards and losing replay/live parity
- Conflating replay behavior, live-sim behavior, and live behavior
- Locking adapter contracts too tightly to one broker SDK
- Failing to filter mixed order lifecycle events by active account and `user_def`
- Underestimating latency-sensitive exit behavior in short-side day trading
