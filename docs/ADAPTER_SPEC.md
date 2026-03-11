# Adapter Specification

## Purpose

Adapters isolate the runtime from a specific market-data, broker, or account-service implementation.

v0.1 is still anchored to Taiwan stock intraday needs, but the runtime should not assume one permanent vendor shape.

## Adapter families

### Auth / Session surfaces
A shared `AuthSessionManager` coordinates login/session state across marketdata + trading/account surfaces.

### MarketDataAdapter
Transforms external market-data APIs into normalized runtime events.

### BrokerAdapter
Transforms runtime-approved execution requests into broker API calls and lifecycle updates.

## Shared auth/session model

### Supported login modes for v0.1 docs

The product should explicitly support at least these common credential shapes:

1. `account + password + cert + cert password`
2. `account + API key + cert + cert password`

### Safety boundary for agent-assisted workflows

Mode 2 is operationally useful because some broker environments let the API key carry narrower permissions.

That allows a practical pattern:

- operators can provision credentials for setup/validation/replay work
- trade permission can remain disabled on the API key when appropriate
- agents can assist within that reduced-permission boundary
- live trading still requires stronger operator approval and capability checks

The docs should treat this as a real safety boundary, not a footnote.

### Session manager responsibilities

```python
class AuthSessionManager(Protocol):
    def login(self, profile: LoginProfile) -> SessionContext: ...
    def refresh(self) -> SessionContext: ...
    def current(self) -> SessionContext | None: ...
    def logout(self) -> None: ...
```

`SessionContext` should carry structured facts such as:

- `session_id`
- `account_no`
- `auth_mode`
- `trade_enabled`
- `marketdata_enabled`
- `account_query_enabled`
- `expires_at` or renewal hints
- `capabilities`
- `health_status`

If the vendor cannot literally share one token/session across all surfaces, the manager should still expose one logical runtime session and capability envelope.

## MarketDataAdapter responsibilities

- connect / disconnect transport
- subscribe / unsubscribe symbols or channels
- accept subscription plans derived from deck scope + enabled card symbol pools
- normalize timestamps and event types
- surface connection health and recoverable errors
- provide recordable and replay-compatible event schema where possible
- model connection limits / subscription limits explicitly

### Minimum interface sketch

```python
class MarketDataAdapter(Protocol):
    def connect(self, session: SessionContext) -> None: ...
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
- surface order acknowledgements, fills, cancels, replaces, rejects, and active-order reports
- normalize broker-side errors and statuses
- avoid leaking vendor-specific oddities into card code
- preserve account and routing identity so mixed lifecycle events do not bleed across cards or accounts

### Minimum interface sketch

```python
class BrokerAdapter(Protocol):
    def submit(self, request: ExecutionRequest) -> BrokerReceipt: ...
    def cancel(self, order_id: str) -> BrokerReceipt: ...
    def replace(self, order_id: str, request: ExecutionRequest) -> BrokerReceipt: ...
    def positions(self) -> list[PositionSnapshot]: ...
    def iter_order_events(self) -> Iterator[OrderLifecycleEvent]: ...
```

### Order lifecycle normalization requirements

At minimum, normalized order lifecycle events should expose:

- `event_id`
- `event_type`
- `ts_broker`
- `account_no`
- `order_no`
- `symbol`
- `status`
- `filled_qty`
- `filled_price`
- `user_def`
- `source`
- `raw_ref`

### Required routing rule

Order changes, cancels, fills, and active reports may arrive interleaved.

The runtime must therefore filter and route them using **both**:

- the active account number
- `user_def` (or equivalent broker-side user marker)

This is a concrete migration lesson from the current Steamer implementation and should be treated as a required contract assumption for v0.1.

## Compatibility stance

The product should target **contract compatibility**, not perfect feature parity.

That means:

- adapters may expose capability flags
- runtime policy may reject unsupported features
- cards should not branch on broker-specific details
- auth/session sharing may vary by vendor, but the runtime contract stays stable

## v0.1 assumptions

- Taiwan cash session model
- single active broker adapter
- single active market-data adapter
- shared logical auth/session boundary
- session/day lifecycle matters more than cross-venue routing
- day-trading latency matters more than abstract elegance

## Required operational metadata

Each adapter should expose:

- `adapter_id`
- `vendor`
- `version`
- `capabilities`
- `session_status`
- `health_status`
- `connection_limits`
- `rate_limit_policy`

## Failure semantics

Adapters must classify failures into at least:

- transient transport error
- auth/config error
- rate limit / throttling
- capability mismatch
- permanent unsupported action
- rejected order / business rule failure
- stale or ambiguous session state

The runtime should consume these as structured states, not stringly-typed surprises.

## Anti-goals

- Adapters are not strategy hosts.
- Adapters are not where risk policy should live.
- Adapters should not own multi-card scheduling decisions.
- Adapters should not hide mixed account / `user_def` routing ambiguity from the runtime.
