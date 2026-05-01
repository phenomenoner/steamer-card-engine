# 2026-05-02 — Stage 4a broker dry-run mock packet

## Verdict

Implement Stage 4 as **Stage 4a: broker dry-run shape with mock transport only**.

This slice validates translation, receipt shape, redaction, and fail-closed no-place-orders behavior. It is not real broker connectivity, not credential/session inspection, not account readiness, and not live readiness.

## Proposed CLI

```bash
steamer-card-engine broker preflight \
  --broker mock-fixture \
  --mode dry-run \
  --no-place-orders \
  --mock-transport fixture \
  --fixtures examples/probes/broker_dry_run \
  --receipt out/broker-preflight.receipt.json \
  --json

steamer-card-engine broker redact-check \
  --receipt out/broker-preflight.receipt.json \
  --json
```

## Fail-closed rules

- `--no-place-orders` is required.
- `--mode` must be exactly `dry-run`.
- `--mock-transport fixture` is the only accepted transport in this slice.
- `--broker` must be `mock-fixture` or another explicitly mocked id.
- Any real broker name, unknown broker, missing guard, or non-dry-run mode exits nonzero before fixture read/translation.
- No env/credential/cert/account/session path flags exist in this slice.

## Mock transport contract

Suggested module:

```text
src/steamer_card_engine/broker_dry_run/
  __init__.py
  transport.py      # mock transport protocol + fixture implementation
  translator.py     # normalized intent -> dry-run operation shape
  receipts.py       # preflight receipt + redaction helpers
```

Mock transport exposes only:

```python
class MockBrokerDryRunTransport(Protocol):
    transport_id: str
    no_network: Literal[True]

    def preflight(self) -> MockTransportHealth: ...
    def translate_order(self, request: ExecutionRequest) -> DryRunTranslation: ...
```

It must not expose `submit`, `place_order`, `send_order`, `login`, `connect`, `positions`, or `balances`.

Public transport health:

```json
{
  "transport_id": "mock-fixture",
  "transport_kind": "mock",
  "connectivity": "mock-verified",
  "no_network": true,
  "credential_inspection": "not-performed",
  "account_inspection": "not-performed"
}
```

## No-place-orders invariant

Required receipt fragment:

```json
{
  "order_placement": {
    "enabled": false,
    "guard": "no-place-orders",
    "guard_required": true,
    "guard_present": true,
    "place_order_call_count": 0,
    "broker_native_order_count": 0
  }
}
```

Implementation guidance:
- do not define a real placement method on the mock transport
- fail if fixtures contain `broker_native_order`, `account_id`, `order_no`, raw vendor payload, or private symbol list
- translation output is a dry-run translation, not a broker-native order

## Receipt / translation schema

Suggested `broker-dry-run-preflight/v1`:

```json
{
  "schema_version": "broker-dry-run-preflight/v1",
  "broker": {"id": "mock-fixture", "vendor": "mock", "version": "v0"},
  "mode": "dry-run",
  "transport": {"kind": "mock", "id": "mock-fixture", "no_network": true},
  "translation": {
    "schema_version": "broker-dry-run-translation/v1",
    "input_kind": "normalized_execution_request",
    "cases_checked": 1,
    "translations": [
      {
        "case_id": "synthetic-buy-1",
        "request_id": "dry-run:synthetic-buy-1",
        "symbol_ref": "<PUBLIC_SYMBOL_REF>",
        "side": "buy",
        "quantity": 1,
        "order_type": "market",
        "time_in_force": "day",
        "dry_run_operation": "submit_preview",
        "broker_native_order": null,
        "dispatch_suppressed": true
      }
    ]
  },
  "order_placement": {
    "enabled": false,
    "guard": "no-place-orders",
    "place_order_call_count": 0,
    "broker_native_order_count": 0
  },
  "redaction": {
    "status": "pass",
    "checked_terms": ["token", "password", "api_key", "secret", "cert", "account", "raw_response"],
    "raw_vendor_payload_present": false
  },
  "credential_inspection": "not-performed",
  "account_inspection": "not-performed",
  "live_readiness_claim": false,
  "no_network": true,
  "topology_changed": false
}
```

## Redaction contract

Public receipts must not contain:

- account ids / account numbers
- credentials, cert paths, env dumps
- raw broker/vendor payloads
- raw order ids / routing ids
- private symbol lists
- real broker SDK exception strings

Allowed:
- opaque public refs like `<PUBLIC_SYMBOL_REF>`
- stable hashes of synthetic fixtures
- `raw_ref` only if mock-local and sanitized

## Boundary: mock Stage 4a vs real Stage 4b

Stage 4a does not do real broker inspection.

Explicit boundary:

```text
mock dry-run only; no real broker SDK import, no network, no credential/env/cert reads,
no account/session inspection, no order placement, no live readiness claim
```

Future real Stage 4b requires separate CK authorization and a new packet for credential/session inspect, redaction, topology, and rollback.

## Tests / counterfactuals

```bash
uv run pytest tests/test_broker_dry_run.py tests/test_cli.py tests/test_broker_adapter_contract.py tests/test_paper_cli.py
uv run ruff check src/steamer_card_engine/broker_dry_run src/steamer_card_engine/cli.py tests/test_broker_dry_run.py tests/test_cli.py
```

Required counterfactuals:
1. happy path emits `broker-dry-run-preflight/v1`
2. missing `--no-place-orders` fails before fixture read
3. `--mode live` fails closed
4. unknown/real broker id fails closed
5. native/broker order payload in fixtures fails
6. forbidden redaction terms absent from full JSON
7. monkeypatched secret env values do not appear
8. no network path; transport reports `no_network=true`
9. no `/workspace/steamer` access
10. no default operator/cron/runtime state writes
11. receipt write only occurs when explicit `--receipt` is provided
12. `live_readiness_claim=false`

## Topology / rollback

Topology for this slice:
- runtime topology changed: no
- cron/scheduler topology changed: no
- broker/account authority changed: no
- `/workspace/steamer` touched: no
- network/SDK dependency added: no

Rollback:
- local git revert of implementation commit
- delete generated local `out/broker-preflight.receipt.json` artifacts if needed

## Delegation packet

Objective:

> Implement `steamer-card-engine broker preflight` as a mock-only Stage 4a dry-run adapter shape verifier with mandatory `--no-place-orders`, deterministic translation receipt, redaction checks, and no real broker/session/credential behavior.

Stop immediately if implementation requires:
- real SDK import
- network
- credentials/env/cert/account reads
- `/workspace/steamer`
- cron/runtime changes
- live readiness claims
- broker-native order payloads

Return:
- diff summary
- pytest/ruff receipts
- sample mock preflight receipt
- topology statement
- deferred real Stage 4b boundaries
