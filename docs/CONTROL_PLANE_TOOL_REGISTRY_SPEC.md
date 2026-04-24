# Control-Plane Tool Registry Spec v1

Status: additive contract, read-only only, remote-safe.

## Verdict

`steamer-card-engine` exposes a small control-plane inspection registry. It is not a generic agent tool surface and it does not grant runtime authority.

## Contract

Each registered tool declares:

- `tool_id`
- `description`
- `read_only=true`
- `allowed_action=read`
- sanitized input contract
- sanitized output contract
- `receipt_required=true`

The registry fails closed when:

- the tool id is unknown
- the requested action is anything except `read`
- a tool is not explicitly read-only
- a registered tool has no handler

Every call returns a public-safe receipt, including rejected calls.

## Seed tool

### `latest_evidence_report`

Action: `read`

Returns only a sanitized local pointer to a deterministic aggregate evidence report fixture:

- pointer: `docs/receipts/artifacts/latest-evidence-report.fixture.json`
- pointer kind: `sanitized-local-pointer`
- evidence date: `2026-04-24`
- raw evidence included: false
- raw symbols included: false
- strategy params included: false
- credentials included: false
- account data included: false

The tool does not read raw bundles, unpack archives, execute replay/live-sim, mutate cards/decks, call broker/account APIs, or expose credentials.

## Public-safety boundary

Allowed:

- sanitized pointers
- aggregate report metadata
- receipt ids
- public-safe booleans stating excluded private surfaces

Forbidden:

- runtime execution
- deck/card mutation
- live-sim launch
- broker/account calls
- credentials or auth material
- raw symbols, ticks, orders, trades, decisions, strategy params, or raw evidence bundles
- Fincept code adoption

## Topology

Control-plane contract topology changed: yes.
Runtime execution topology changed: no.
