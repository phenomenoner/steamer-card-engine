# 2026-04-30 — steamer-card-engine real trade gate plan

## Status
- plan-only
- unexecuted
- topology: unchanged
- boundary: this packet does **not** authorize live trading, broker login, credential storage, or order submission by itself

## Verdict
The `real trade gate` should close in two stages, not one:

1. **Stage 1: real broker path smoke with a fake/time-driven round-trip card** — prove broker-connected submit/ack/fill-or-terminal/cancel-or-flatten lifecycle and safety controls with the smallest acceptable real exposure.
2. **Stage 2: real strategy upgrade (`dt3`)** — only after Stage 1 has clean receipts, run a bounded dt3 live candidate under the same guardrail envelope.

Success means execution-path truth, safety envelope truth, and receipt quality are all proven. It does **not** mean strategy alpha is proven or broad live autonomy is approved.

## Whole-picture promise
Close the last production-facing gap identified in `docs/receipts/2026-04-17_live_trade_ready_validation_closure.md`: non-cash proof is already strong, but the repo has not yet proven real broker submission/fill lifecycle and real flatten/disarm recovery.

This packet turns that gap into a controlled ladder:

- preflight/read-only live attach
- one fake/time-driven live round trip
- repeated clean Stage 1 evidence, if CK wants a soak
- one bounded dt3 live pass
- closure bundle with complete evidence and explicit failure branches

## Contract / boundaries
Hard boundaries for both stages:

- CK must explicitly provide the formal live environment and day-of go; credentials stay out of git and docs.
- Dedicated account/profile only; account id must be allowlisted in config and visible in receipts.
- One symbol allowlist per run; no dynamic universe expansion during gate tests.
- Smallest broker-supported quantity and notional; record exact symbol / quantity / side before arming.
- Bounded session window only: avoid open auction, pre-open, final minutes, and unusual liquidity conditions.
- Operator-attended only for Stage 1 and first dt3 live run.
- `armed_live=false` is the default; live authority requires explicit bounded `operator arm-live` with TTL.
- Success must return to `armed_live=false` and a provably flat target position.
- If broker behavior, lifecycle receipts, or flatten semantics diverge, stop and preserve the truthful failure branch; do not improvise live.

## Stage 0 — live read-only preflight
Purpose: prove credentials/session/account surfaces without sending orders.

Required checks:

1. `auth inspect-session --json` sees the intended live profile and account posture.
2. `operator probe-session --json` reports fresh broker/session health.
3. `operator preflight-smoke --json` is `ready`, not stale/fixture-only.
4. Pull account baseline: cash/buying power, holdings, open orders, day-trade permission/capability if exposed.
5. Confirm no unexpected open orders or target-symbol positions unless intentionally part of the plan.
6. Confirm clock/NTP sanity; alert on meaningful skew.
7. Confirm notification channel and out-of-band kill path are live.

Gate: no order can be submitted from Stage 0. Any mismatch means hold and fix preflight truth first.

## Stage 1 — fake/time-driven real round-trip card
### Recommended shape
Use a dedicated `time_round_trip_smoke` card/deck whose only job is to test the real broker path.

Recommended default:

- **Use SELL -> BUY/COVER as the preferred Stage 1 smoke**, because CK's gate is day-trade capability: a symbol that can be sold first is materially more likely to be eligible for the intended intraday round-trip, while buy-first can accidentally pass on a non-daytrade-capable symbol.
- Sell-first is only allowed after an explicit shortable/daytrade-capable symbol allowlist check; without that proof the plan gate must refuse before arming.
- Entry: submit exactly one minimal sell order after arming.
- Wait condition: start the exit timer only after confirmed fill or partial-fill, not merely after submit.
- Exit: submit exactly one buy/cover order for the filled quantity after 10–30 seconds, or a slightly longer operator-approved interval if broker/market latency makes 10 seconds too tight.
- No-fill branch: cancel at timeout, disarm, record `no-fill terminal`; do **not** force a fill to make the story pretty.
- Partial-fill branch: exit only the filled quantity; cancel remainder; record partial branch explicitly.
- End condition: after one round trip or terminal no-fill/cancel branch, halt for review.

### Why not “loop until it works”
Stage 1 is a gate proof, not a strategy. It must have a one-shot latch:

- `max_entry_orders_per_run = 1`
- `max_exit_orders_per_run = 1`
- `max_total_strategy_orders_per_run = 2` plus explicit emergency cancel/flatten actions
- `max_round_trips_per_day = 1` until CK explicitly widens the envelope

## Stage 2 — dt3 real-strategy upgrade
Only unlock Stage 2 after Stage 1 has a clean receipt bundle and CK accepts the remaining risk.

Recommended first dt3 live run:

- use the same account/profile/operator-control lane as Stage 1
- one symbol or one tiny allowlisted symbol set, not the full production universe
- smallest truthful quantity/notional
- no add-ons / pyramiding / repeated entries on first live dt3 pass
- strategy emits live intent, but risk governor owns final send/hold/reject decisions
- dt3 run must inherit the same idempotency, max-order, alert, and kill-switch controls from Stage 1
- first success criterion is safe lifecycle closure, not PnL

Stage 2 closes the `real trade gate` only if:

- dt3 produced a real intent under production-like data conditions
- risk governor accepted or rejected it with inspectable reasons
- any accepted order traversed broker lifecycle with stable identifiers
- final posture is disarmed
- final target exposure is flat or intentionally held with written operator approval
- receipt bundle is complete enough for third-party reconstruction

## Insurance / safety mechanisms
### 1. No repeated-order loop
Implement a persistent order-intent journal/outbox:

- Persist `intent_id`, `run_id`, `strategy_id`, `deck_hash`, `config_hash`, `symbol`, `side`, `quantity`, `created_at`, and state **before** sending.
- Derive broker `client_order_id` / `user_def` deterministically from `run_id + intent_id + leg` where the broker supports it.
- On restart, reconcile broker open orders/positions before sending anything new.
- Never resend an intent from local `created/submitted` state without querying broker state first.
- Inflight guard: no second order for the same symbol/side/run while a prior order is unresolved unless the action is explicit cancel/flatten.

### 2. No oversized order
Hard rejects, not warnings:

- per-order quantity cap
- per-order notional cap
- daily notional cap
- max open position cap including pending/inflight orders
- symbol allowlist
- account allowlist
- price-deviation/slippage band vs. reference price
- environment checksum: live config must be explicitly marked and signed/hashed; a swapped env var should not silently enable live

### 3. No missed buy/sell / unresolved leg
Round-trip watchdog:

- if entry fills and exit is not submitted within the configured window, alert and trigger emergency flatten path
- if exit submits but no terminal state arrives by abort timestamp, cancel/flatten/disarm according to policy
- if strategy/controller heartbeat is stale, halt new orders and page
- if end-of-run position is non-flat unexpectedly, page and keep kill/flatten path active until reconciled

### 4. State machine
Minimal state machine for each smoke run:

```text
PRECHECK -> ARMED -> ENTRY_INTENT_PERSISTED -> ENTRY_SUBMITTED -> ENTRY_ACKED
  -> ENTRY_FILLED | ENTRY_PARTIAL | ENTRY_NO_FILL_CANCELLED | ENTRY_REJECTED
  -> EXIT_INTENT_PERSISTED -> EXIT_SUBMITTED -> EXIT_ACKED
  -> EXIT_FILLED | EXIT_PARTIAL | EXIT_REJECTED | EMERGENCY_FLATTEN
  -> FINAL_RECONCILED -> DISARMED -> CLOSED
```

Any illegal transition halts new orders and raises an alert.

## Real-time anomaly alerting
Alert on these families at minimum:

- order send failure or unknown broker response
- duplicate intent/order id
- order-rate spike or second entry attempt in a one-shot run
- quantity/notional cap rejection
- market-data staleness
- broker/session disconnect
- lifecycle timeout: submit without ack, fill without matching local intent, exit not emitted after fill, terminal state missing by abort time
- unexpected open position / non-flat close
- PnL/slippage outside configured smoke tolerance
- clock skew beyond threshold
- operator posture remains armed after TTL or run close

Delivery policy:

- Stage 1 should use at least one immediate CK-facing channel plus a local receipt/log.
- First live run should be attended; alerts are backup, not a replacement for the operator.
- Alert payload must include `run_id`, `account alias`, `symbol`, `state`, `last broker order id`, and recommended action.

## Instant kill mechanism
The kill path must be independent enough that a broken strategy loop cannot block it.

Required behavior:

1. `disable-new`: set a durable kill flag / disarm posture so no new order can be sent.
2. `cancel-all`: cancel all open orders in the allowed account/symbol scope.
3. `flatten`: if position remains open, submit reduce-only flatten orders under emergency policy.
4. `verify`: poll broker/account state until terminal flat/open-order-free or operator-declared unresolved.
5. `receipt`: write a kill receipt with commands/actions, order ids, remaining exposure, and final posture.

Recommended surfaces:

- existing operator command family: `operator disarm-live` and `operator flatten --mode emergency`
- one explicit `panic/kill` wrapper can be added later, but it should call the same audited primitives rather than inventing a hidden path
- an out-of-band manual broker UI procedure should be written before first live run, because engine-side kill is not enough if the engine is unhealthy

## Verifier plan
Before first live order:

1. Unit tests for state-machine illegal transitions and max-order caps.
2. Fixture/sandbox test for duplicate `client_order_id` / `user_def` behavior.
3. Sandbox or broker test environment round-trip with the same code path where available.
4. Live read-only Stage 0 receipt.
5. Kill-switch drill without open exposure: disarm + cancel-all no-op + receipt.
6. Dry-run of alert formatting and routing.

During Stage 1:

- capture baseline account/open orders/positions before arming
- capture every intent, broker request, response, ack, fill/cancel/reject event
- capture kill/disarm/flatten receipt even on success, if only as a no-op or final closure primitive
- capture final account/open orders/positions

After Stage 1:

- compare broker statement/lifecycle events against local journal
- mark PASS / HOLD / FAIL / ABORT
- Stage 2 remains locked unless PASS and CK accepts the receipt bundle

## Required receipt bundle
- operator note with exact symbol / quantity / side / window / abort timestamp
- live credential/profile alias only, never secret material
- fresh session/probe/preflight JSON
- account/open-order/position baseline
- arm receipt with TTL and scope
- order intent journal
- broker submit/ack/lifecycle/fill/cancel/reject events with stable order identifiers
- alert/kill-switch drill receipt
- final flat-state/open-order-free proof
- final disarm receipt
- compact run summary

## Handoff target
`steamer-card-engine` implementation work should land as a bounded engineering slice:

1. `time_round_trip_smoke` card/deck + state-machine/outbox guardrails.
2. broker-lifecycle receipt adapter / reconciliation proof.
3. alert + kill wrapper bound to existing operator primitives.
4. dt3 live upgrade packet after Stage 1 closure.

## Tradeoffs / open risks
- A true “一張” may not be low notional depending on symbol; choose the smallest broker-supported quantity and symbol deliberately.
- Sell-first is the correct gate for CK's day-trade-capability proof, but it must be guarded by an explicit shortable/daytrade-capable symbol allowlist and immediate cover/kill path.
- Ten seconds is useful for gate latency, but too short if broker lifecycle events are slow; the timer should start after fill and be operator-configurable.
- A successful Stage 1 proves the gate and controls, not strategy quality.
- Real-time alerts and instant kill reduce risk but do not eliminate exchange/broker latency, limit-lock, partial-fill, or disconnect risk.

## Second-brain review notes
A Claude Opus safety review agreed with the staged shape and highlighted these red flags:

- Claude originally warned that `BUY -> SELL` is simpler, but CK's requirement changes the gate: Stage 1 should be `SELL -> BUY/COVER` with explicit short-capability proof because buy-first can pass on the wrong symbol.
- define explicit soak/success criteria before unlocking dt3
- use deterministic client order ids and persistent outbox/idempotency
- reconcile broker open orders/positions on startup before sending
- drill kill switch during Stage 1
- keep one human owner on pager during first live run

## WAL / topology closure
- topology: unchanged
- durable truth changed: this planning packet defines the next real-trade-gate ladder and safety envelope
- execution status: not started; waits for CK-provided formal live environment and explicit day-of go
