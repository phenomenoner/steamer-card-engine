# Live Execution Gate

This document describes the public contract for bounded live broker execution in `steamer-card-engine`.

It intentionally avoids private account numbers, broker credentials, cloud paths, and operator receipts. Those belong in local operator storage, not public product docs.

## Stance

Live execution is a gated capability, not the default runtime mode.

The safe progression is:

```text
card/deck validation -> replay -> live-sim -> dry-run broker gate -> explicitly armed live gate
```

The product should make each step produce reviewable receipts before the next step expands authority.

## Required live gates

A live execution path must satisfy all of these before submitting broker orders:

1. **Explicit operator arm**
   - live authority is off by default;
   - arm has a bounded TTL;
   - arm is scoped to deck/account/session posture.
2. **Explicit live command posture**
   - command must request live mode;
   - command must include live confirmation;
   - command must point to broker credentials outside the repository.
3. **Account/session match**
   - active account must match the armed account/session posture;
   - mismatch refuses execution before order placement.
4. **Risk and policy gate**
   - symbol, quantity, round-trip count, shortability/day-trade capability, and deck policy must pass;
   - entry filters and exit policies must be present for bounded live tests.
5. **Receipt emission**
   - all decisions, blockers, orders, fills, and final posture must be machine-readable;
   - public reports must redact private identifiers.

## Fill-source contract

Position and P/L calculations must use execution fills, not submitted order prices.

### Primary path: active filled callback

The low-latency primary source is the broker SDK's filled callback, e.g. `set_on_filled(...)` for NeoAPI.

Expected fields include:

- order identifier
- sequence identifier
- fill identifier
- symbol
- side
- filled quantity
- filled average price or filled price
- filled time
- user routing tag

The runtime should dedupe fills using the strongest available key, such as:

```text
order_no + seq_no + filled_no
```

### Safe-net path: periodic readback

The callback path is fast, but production systems should still reconcile periodically with broker readback, e.g. `get_order_results`.

Recommended behavior:

- poll at a modest cadence such as every ~30 seconds while a live position is open;
- compare filled quantity, filled money, order status, and timestamps;
- mark reconciliation deltas explicitly;
- never double-count fills already seen through callbacks;
- if callback data is missing but readback confirms a fill, mark `fill_source=order_results_readback`.

### Forbidden fallback

Do **not** compute entry/exit average from submitted limit prices, limit-up/limit-down prices, or order acknowledgement prices.

Those values are constraints, not execution facts. If fill price is unavailable, the runtime must mark the position unresolved and reconcile before making P/L-based decisions.

## Exit policy contract

A bounded day-trade live test must have a clear exit policy, such as:

- take-profit threshold;
- stop-loss threshold;
- forced-cover / forced-exit time;
- final flatten behavior if applicable.

For short-side day-trading tests, the exit path must assume liquidity can degrade quickly near the upper limit. Forced exits and stop-losses should be treated as latency-sensitive.

## Receipt fields

A live round-trip receipt should include at least:

| Field | Purpose |
|---|---|
| `mode` | proves live/dry-run posture |
| `status` | final execution status, e.g. `round-trip-closed` |
| `account_gate` | account/session match result, redacted in public reports |
| `quote_gate` | broker quote/day-trade capability gate |
| `entry_filter` | policy and observed market quote |
| `active_fill_callback` | whether active fill callback was registered |
| `entry_fill_price.source` | callback vs readback source |
| `exit_trigger.reason` | take-profit, stop-loss, or forced-cover reason |
| `steps[]` | order placement and fill lifecycle |
| `issues[]` | blockers or anomalies |

## Public reporting rule

Public docs may say a bounded one-symbol live validation passed if the public facts are limited to:

- strategy shape;
- guardrails used;
- whether active fill callback was proven;
- whether the round-trip closed;
- whether code/docs were updated.

Public docs must not include:

- account numbers;
- real order numbers;
- personal IDs;
- credential paths;
- private cloud instance IDs or command IDs;
- internal machine paths;
- raw broker receipts.
