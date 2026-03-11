# Card Specification

## Definition

A **Card** is the smallest strategy authoring unit exposed by the product.

A card reads normalized runtime context and emits one of:

- no intent
- one or more `Intent` objects
- diagnostics for replay/audit

A card does **not** directly place or manage broker orders.

## Required properties

Each card should have stable identity metadata:

- `card_id`
- `name`
- `version`
- `strategy_family`
- `instrument_scope`
- `parameters`
- `owner` or provenance metadata
- `status` (`draft`, `replay-only`, `operator-approved`, `retired`)

## Minimal manifest shape

```toml
card_id = "gap-reclaim-v1"
name = "Gap Reclaim"
version = "0.1.0"
strategy_family = "open-drive-reversal"
instrument_scope = ["TW_EQUITY"]
status = "replay-only"
entry_module = "cards.gap_reclaim:build_card"

[parameters]
min_gap_pct = 2.5
max_chase_pct = 1.2
reclaim_window_seconds = 420
```

## Runtime contract

Conceptual Python interface:

```python
class Card(Protocol):
    card_id: str
    version: str

    def on_event(self, context: MarketContext) -> list[Intent]:
        ...
```

## Intent contract

An `Intent` should be descriptive, not imperative.

Required fields:

- `intent_id`
- `timestamp`
- `card_id`
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

## Card behavior rules

1. **No direct broker calls**
2. **No credential access**
3. **No mutation of global runtime policy**
4. **Deterministic under replay given the same event stream and parameters, where feasible**
5. **Explicit versioning when logic changes materially**

## Deck interaction

A card may be included in multiple decks, but deck policy decides:

- whether it is enabled
- symbol scope overrides
- capital/risk ceilings
- conflict priority relative to sibling cards

## Card lifecycle states

### draft
Not eligible for live usage.

### replay-only
Allowed in replay and dry-run.

### operator-approved
Eligible for inclusion in operator-approved live decks, subject to deck policy.

### retired
Kept for history and reproducibility, not active.

## Replay expectations

Replay should capture:

- card input context hash or summary
- emitted intents
- reasons / diagnostics
- final disposition after aggregation and risk checks

This matters more than elegant abstractions. If card outputs are not inspectable, the product will drift into theater.
