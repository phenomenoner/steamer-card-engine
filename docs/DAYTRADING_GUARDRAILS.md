# Day-Trading Guardrails

## Why this deserves first-class treatment

Day trading is where beautiful abstractions go to die if the exit path is vague.

This repo is still docs-first, but the docs should already encode the guardrails that the eventual runtime must respect.

## Core stance

- **Low latency is first-class.**
- **Emergency exits are architecture concerns, not just config decoration.**
- **Replay sim, live sim, and live should share the same intent/risk vocabulary even when their execution behavior differs.**

## Guardrail categories

### 1. Emergency stop-loss

Cards and/or deck policy should be able to define emergency stop behavior such as:

- percent from open
- percent from entry
- `n` ticks from current limit price
- hard notional loss limit

The runtime should treat this as latency-sensitive.

### Short-side warning: upper-limit lock risk

For short-side intraday strategies, there is a specific ugly scenario:

- the instrument runs toward or into the upper limit
- liquidity disappears or becomes one-sided
- the strategy may not be able to cover when it wants to

That means an emergency stop is not just a nice rule on paper. It may need fast evaluation, aggressive flatten intent generation, and explicit operator awareness that the market can still outrun the system.

The docs should say this out loud.

### 2. Intraday forced exit

Cards should be able to define a forced-exit start window if take-profit / stop-loss conditions have not resolved the position.

Example questions the config should answer:

- when does the card start flattening?
- does it exit all at once or in stages?
- what price aggressiveness is allowed?
- does behavior differ in replay sim vs live sim vs live?

### 3. Final-auction flatten mode

Global config may enable an operator-governed flatten mode around the close, for example:

- Asia/Taipei `13:25–13:30`
- reverse-side limit / ROD orders
- flatten remaining intraday inventory before the session ends

This should be explicit in policy, not hidden in ad hoc code branches.

### 4. Capital controls

Cards and/or deck policy should be able to express:

- per-order amount limits
- max daily notional spend
- max concurrent positions
- max symbol concentration
- max add-on count per symbol

Cards may declare these, but the runtime and operator policy retain final authority.

### 5. Order-event routing hygiene

Order changes, cancels, fills, and active reports may arrive mixed together.

The runtime must filter them using:

- active account number
- `user_def` (or equivalent routing marker)

Without that, one card can misread another card's lifecycle activity, or one account can contaminate another.

This is not optional.

### 6. Market-day gating (non-trading days / holidays)

The runtime must be able to refuse to run **live** or **live sim** when the exchange is closed.

Minimum contract:
- treat `is_trading_day=false` as a hard gate: do not arm live authority and do not start live-data capture chains
- use an **official** market calendar source (for TW, TWSE holiday calendar) rather than ad hoc manual skip lists
- make the reason operator-inspectable (status surface: closed-day verdict + source)
- safe default is **skip**, not “run anyway”

Related upstream hardening note:
- `/root/.openclaw/workspace/StrategyExecuter_Steamer-Antigravity/projects/steamer/TECH_NOTES/2026-04-06_steamer_market-day-gating_twse-official-holiday-json.md`

## Live sim and replay sim expectations

The engine should support at least two bounded non-live execution modes:

### Replay sim
Uses recorded/historical market events and simulated execution outcomes.

### Live sim
Uses live market data but does not submit live broker orders.

For the session-phase reconciliation line, replay sim and live sim may differ at the **event-source adapter edge**, but they should share the same downstream **session-phase classifier / intent / risk / execution truth**. The product should not quietly fork phase semantics by mode.

These modes matter because they let the product validate:

- emergency stop behavior
- forced-exit timing
- feature/synthesizer parity
- order-event receipts and reporting shape

before expanding live authority.

## Operational implications for architecture

To support these guardrails, the runtime architecture should already assume:

- shared recorder/audit path
- deterministic enough replay contracts
- structured risk policies
- low-overhead hot-path evaluation
- explicit session/account identity
- explicit capability and permission checks

## What this document is not claiming

This document does **not** claim the repo already implements production-grade day-trading controls.

It defines the guardrail contract the implementation should be measured against.
