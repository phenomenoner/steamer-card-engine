# 2026-05-02 — Stage 5 observe-paper execution packet

## Verdict

Split Stage 5 into two gates:

1. **Stage 5a — fixture/live-shape observation harness**
   - no network
   - no credentials
   - no broker SDK
   - no `/workspace/steamer`
   - paper ledger only
   - proves command, receipt, staleness handling, outage handling, and paper-execution boundary using fixture-shaped "live" market events

2. **Stage 5b — real live market-data observation**
   - requires explicit CK authorization
   - may read market data only
   - still paper execution only
   - no live orders, no broker placement, no operator live arm

Recommended next implementation slice: **Stage 5a only**.

## Whole-picture promise

Stage 5 should prove:

```text
market-data observation
  -> normalized signal / decision
  -> paper-only execution backend
  -> paper ledger receipt
  -> stale/outage fail-closed behavior
```

It must not prove or imply live trading readiness. That remains Stage 6 and must converge with the existing live trade gate.

## CLI proposal

### Stage 5a: no-network fixture live-shape harness

```bash
steamer-card-engine observe paper \
  --adapter fixture-paper-only \
  --market-source fixture-live-shape \
  --fixtures examples/probes/live_observe \
  --execution paper \
  --paper-ledger out/stage5a_live_shape/ledger.sqlite \
  --risk-profile conservative \
  --duration-seconds 60 \
  --stale-market-data-seconds 5 \
  --receipt out/stage5a_live_shape/live-paper.receipt.json \
  --json
```

Hard requirements:
- `--market-source` must be `fixture-live-shape`
- `--execution` must be `paper`
- fixture source only
- no env/credential reads
- no network imports or sockets
- no broker transport
- no operator arm/disarm coupling

### Stage 5b: real live market data, separately authorized

```bash
steamer-card-engine observe paper \
  --adapter fixture-paper-only \
  --market-source live \
  --market-provider <approved-provider> \
  --execution paper \
  --paper-ledger .state/paper/live-observe-ledger.sqlite \
  --risk-profile conservative \
  --duration-seconds 1800 \
  --stale-market-data-seconds 10 \
  --receipt out/live-paper.receipt.json \
  --json
```

Do **not** implement or run Stage 5b without CK's explicit authorization.

## Boundary with Stage 6 / live trade gate

Stage 5 may produce **paper orders only**.

It must not call or share execution authority with:
- `operator arm-live`
- `operator submit-order-smoke`
- `live canary execute`
- broker placement
- live order dispatch
- real account/session mutation

Receipt must include:

```json
{
  "execution_backend": "paper-ledger-only",
  "live_order_route_present": false,
  "broker_order_placement_enabled": false,
  "stage6_live_canary_authority": false,
  "live_readiness_claim": false
}
```

## Receipt contract

Suggested schema: `observe-paper-run/v1`.

Required fields:

```json
{
  "schema_version": "observe-paper-run/v1",
  "mode": "observe-paper",
  "stage": "5a-fixture-live-shape",
  "market_source": {
    "kind": "fixture-live-shape",
    "no_network": true,
    "credential_inspection": "not-performed",
    "provider": "fixture"
  },
  "execution": {
    "backend": "paper-ledger-only",
    "ledger_schema_version": "paper-ledger/v1",
    "broker_native_order_count": 0,
    "place_order_call_count": 0
  },
  "freshness": {
    "decision": "pass|fail",
    "max_staleness_seconds": 5,
    "stale_events": 0,
    "outage_detected": false,
    "fail_closed": true
  },
  "risk": {
    "profile": "conservative",
    "decision": "pass|fail",
    "paper_risk_checked": true
  },
  "summary": {
    "market_events_seen": 0,
    "signals_seen": 0,
    "paper_orders_accepted": 0,
    "paper_orders_rejected": 0,
    "fills": 0
  },
  "no_network": true,
  "topology_changed": false,
  "live_readiness_claim": false
}
```

## Staleness / outage fail-closed

Fail closed if:
- no market event arrives before first decision window
- event timestamp age exceeds `--stale-market-data-seconds`
- event sequence regresses or gaps beyond fixture/provider tolerance
- market source reports `stale`, `degraded`, or `outage`
- adapter emits an order intent without fresh market data evidence

Fail-closed outcome:
- no paper order accepted
- ledger records `risk_rejected` or `market_data_stale`
- receipt exits nonzero or returns `decision=fail`
- no live/broker route touched

## Paper execution backend proof

Stage 5 should reuse Stage 3 paper ledger/audit surfaces.

Required proof:
- shared paper simulator path or equivalent writes to SQLite ledger
- receipt says `execution = paper-ledger-only`
- `broker_native_order_count = 0`
- `place_order_call_count = 0`
- `paper audit` passes after observe run

Stage 5 should compose Stage 3, not invent a second ledger model.

## Tests / verifier plan

```bash
uv run pytest tests/test_observe_paper_cli.py tests/test_observe_paper.py tests/test_paper_cli.py tests/test_paper_simulator.py tests/test_broker_dry_run.py tests/test_cli.py
uv run ruff check src/steamer_card_engine/observe src/steamer_card_engine/paper src/steamer_card_engine/cli.py tests/test_observe_paper_cli.py tests/test_observe_paper.py
```

Counterfactuals:
1. fixture live-shape happy path writes receipt + paper ledger
2. stale event fails closed before order acceptance
3. outage fixture fails closed
4. missing `--execution paper` fails
5. `--market-source live` fails in Stage 5a
6. unknown market source fails
7. broker-native payload in fixture fails
8. monkeypatched secret env vars do not appear in output
9. no `/workspace/steamer` access
10. no cron/runtime/operator state writes
11. `paper audit` passes after successful run
12. receipt has `live_readiness_claim=false`

## Topology / rollback

Stage 5a topology:
- runtime topology changed: no
- cron/scheduler topology changed: no
- broker/account authority changed: no
- `/workspace/steamer` touched: no
- network/credential authority changed: no

Rollback:
- git revert implementation commit
- delete generated `out/stage5a_live_shape/*`
- delete temporary test ledgers

## Exact approval boundary

Pre-approved safe implementation slice:

> Implement Stage 5a fixture/live-shape observe-paper harness only, with no network, no credentials, no broker SDK, no live market provider, no `/workspace/steamer`, no cron/runtime changes, and paper-ledger-only execution.

Requires separate CK approval:

> Implement or run Stage 5b with `--market-source live`, any real market-data provider, network access, credentials, SDK/session inspection, or private runtime path.

Still forbidden without later Stage 6 approval:

> Any live order placement, broker dispatch, account mutation, operator live arm, canary execute, or real trading claim.
