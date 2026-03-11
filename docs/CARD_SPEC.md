# Card Specification

## Definition

A **Card** is the smallest strategy authoring unit exposed by the product.

A card reads normalized runtime context plus derived feature snapshots and emits one of:

- no intent
- one or more `Intent` objects
- diagnostics for replay/audit

A card does **not** directly place or manage broker orders.

## Required properties

Each card should have stable identity and governance metadata:

- `card_id`
- `name`
- `version`
- `strategy_family`
- `instrument_scope`
- `status` (`draft`, `replay-only`, `operator-approved`, `retired`)
- `owner` or provenance metadata
- `entry_module`
- `parameters`
- `symbol_pool`
- `capital_controls`
- `risk_policy`
- `feature_requirements`

## Minimal manifest shape

```toml
card_id = "gap-reclaim-v1"
name = "Gap Reclaim"
version = "0.1.0"
strategy_family = "open-drive-reversal"
instrument_scope = ["TW_EQUITY"]
status = "replay-only"
entry_module = "cards.gap_reclaim:build_card"

symbol_pool = ["2330", "2454", "3017"]
feature_requirements = [
  "bars.1m",
  "indicator.macd.12_26_9",
]

[parameters]
min_gap_pct = 2.5
max_chase_pct = 1.2
reclaim_window_seconds = 420

[capital_controls]
max_order_notional = 150000
max_daily_notional = 500000
max_open_positions = 2

[risk_policy.stop_loss]
mode = "percent_from_open"
value = 1.8

[risk_policy.take_profit]
mode = "risk_reward_multiple"
value = 1.5

[risk_policy.forced_exit]
start_time = "13:18:00"
end_time = "13:25:00"

[metadata]
owner = "research"
```

## Runtime contract

Conceptual Python interface:

```python
class Card(Protocol):
    card_id: str
    version: str

    def on_event(self, context: CardContext) -> list[Intent]:
        ...
```

`CardContext` should expose:

- current normalized market event
- relevant derived features / synthesizer outputs
- card parameters
- deck/global policy overlays relevant to the card
- replay/live-sim/live mode hint
- card-local state handle

## Intent contract

An `Intent` should be descriptive, not imperative.

Required fields:

- `intent_id`
- `timestamp`
- `card_id`
- `card_version`
- `deck_id`
- `symbol`
- `side` (`buy`, `sell`, `cover`, `reduce`, `exit`)
- `intent_type` (`enter`, `exit`, `adjust`, `cancel_request`)
- `confidence` (bounded float or enum)
- `size_hint`
- `time_horizon`
- `reason`

Optional fields:

- `price_reference`
- `urgency`
- `tags`
- `risk_notes`
- `evidence_snapshot`
- `requested_user_def_suffix`

## Card behavior rules

1. **No direct broker calls**
2. **No credential access**
3. **No mutation of global runtime policy**
4. **Deterministic under replay given the same event stream and feature versions, where feasible**
5. **Explicit versioning when logic changes materially**
6. **Cards may declare symbol pools, but do not manage transport subscriptions directly**
7. **Reusable indicator/time-series synthesis should be requested via `feature_requirements`, not reimplemented ad hoc inside every card**

## Card scope

A card is expected to cover more than just entry gating. It should be able to declare or contribute:

- entry conditions
- stop-loss logic
- take-profit logic
- intraday forced-exit behavior
- symbol pool
- capital-control hints and ceilings
- required features / synthesizers

That does **not** mean cards own final execution authority. It means the strategy unit is rich enough to be replayed, inspected, and governed as a product artifact.

## Symbol-pool semantics

Cards may define their own `symbol_pool`.

When a card is enabled:

- its symbol pool becomes an input into connection/subscription planning
- the runtime merges card-level pools with deck/global scope rules
- operator or deck policy may narrow, expand, or reject the final subscription set

This supports cases where each strategy card watches a different tradable universe while still using shared market-data infrastructure.

## Feature / synthesizer model

Recommended design:

- cards declare `feature_requirements`
- platform synthesizers build those views from normalized events
- cards consume the resulting snapshots

Why this is the default:

- fewer duplicated indicator calculations
- cleaner replay/live parity
- clearer provenance when diagnosing a decision
- lower risk of hidden per-card divergence

Cards may still keep small ephemeral state, but reusable time-series synthesis belongs in the platform layer.

## Deck interaction

A card may be included in multiple decks, but deck policy decides:

- whether it is enabled
- symbol scope overrides or allowlists
- capital/risk ceilings
- conflict priority relative to sibling cards
- whether card-defined forced-exit windows are accepted or tightened

## Card lifecycle states

### draft
Not eligible for live usage.

### replay-only
Allowed in replay and live-sim only.

### operator-approved
Eligible for inclusion in operator-approved live decks, subject to deck/global policy.

### retired
Kept for history and reproducibility, not active.

## Replay expectations

Replay should capture:

- input event stream identity
- feature snapshot hash or summary
- card parameters and version
- emitted intents
- reasons / diagnostics
- final disposition after aggregation and risk checks

If card outputs are not inspectable, the product drifts back into opaque scripts wearing nicer clothes.
