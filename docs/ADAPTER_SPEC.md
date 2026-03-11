# Adapter Specification

## Purpose

Adapters isolate the runtime from a specific market-data or broker implementation.

v1 is still anchored to Taiwan cash intraday needs, but the runtime should not assume one permanent vendor shape.

## Adapter families

### MarketDataAdapter
Transforms external market-data APIs into normalized runtime events.

### BrokerAdapter
Transforms runtime-approved execution requests into broker API calls and lifecycle updates.

## MarketDataAdapter responsibilities

- connect / disconnect transport
- subscribe / unsubscribe symbols or channels
- normalize timestamps and event types
- surface connection health and recoverable errors
- provide replay-compatible event schema where possible

### Minimum interface sketch

```python
class MarketDataAdapter(Protocol):
    def connect(self) -> None: ...
    def close(self) -> None: ...
    def subscribe(self, symbols: list[str]) -> None: ...
    def unsubscribe(self, symbols: list[str]) -> None: ...
    def iter_events(self) -> Iterator[MarketEvent]: ...
```

### Normalized market event fields

- `event_id`
- `ts_exchange`
- `ts_adapter`
- `symbol`
- `event_type`
- `last_price`
- `bid`
- `ask`
- `volume`
- `source`

## BrokerAdapter responsibilities

- translate approved execution requests into broker operations
- surface order acknowledgements, fills, cancels, rejects
- normalize broker-side errors and statuses
- avoid leaking vendor-specific oddities into card code

### Minimum interface sketch

```python
class BrokerAdapter(Protocol):
    def submit(self, request: ExecutionRequest) -> BrokerReceipt: ...
    def cancel(self, order_id: str) -> BrokerReceipt: ...
    def replace(self, order_id: str, request: ExecutionRequest) -> BrokerReceipt: ...
    def positions(self) -> list[PositionSnapshot]: ...
```

## Compatibility stance

The product should target **contract compatibility**, not perfect feature parity.

That means:

- adapters may expose capability flags
- runtime policy may reject unsupported features
- cards should not branch on broker-specific details

## v1 assumptions

- Taiwan cash session model
- single active broker adapter
- single active market-data adapter
- session/day lifecycle matters more than cross-venue routing

## Required operational metadata

Each adapter should expose:

- `adapter_id`
- `vendor`
- `version`
- `capabilities`
- `session_status`
- `health_status`

## Failure semantics

Adapters must classify failures into at least:

- transient transport error
- auth/config error
- rate limit / throttling
- permanent unsupported action
- rejected order / business rule failure

The runtime should consume these as structured states, not stringly-typed surprises.

## Anti-goals

- Adapters are not strategy hosts.
- Adapters are not where risk policy should live.
- Adapters should not own multi-card scheduling decisions.
