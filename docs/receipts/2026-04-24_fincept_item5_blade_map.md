# Blade Map — Fincept Absorption Item 5

Date: 2026-04-24
Item: Limited read-only control-plane tool registry

## Verdict

Implement a small, remote-safe, read-only control-plane tool registry contract. This is inspection-only tooling with receipts, not generic agent sprawl and not execution authority.

## Whole-picture promise

Operators and research/control-plane helpers should be able to ask for sanitized pointers such as latest evidence report, card/deck metadata, replay status, or live-sim status without exposing raw evidence, strategy params, accounts, brokers, credentials, or granting mutation authority.

## Scope

Primary target: `steamer-card-engine`

Additive contract-first slice:

- Define a minimal read-only tool registry model/schema.
- Define tool capability metadata:
  - tool id
  - description
  - read-only flag
  - allowed action
  - sanitized input contract
  - sanitized output contract
  - receipt requirement
- Seed one deterministic read-only tool fixture/verifier, preferably `latest_evidence_report`.
- The fixture must return a sanitized pointer + receipt, not raw private data.
- Add tests proving:
  - registered tools are read-only
  - unknown tools fail closed
  - mutating actions are rejected
  - output receipt is public-safe

## Non-goals

- No broad generic file/API/Python tool surface.
- No write/mutate/delete actions.
- No runtime execution, deck mutation, live-sim launch, broker/account calls, or credential handling.
- No raw symbols, strategy params, raw ticks, raw decisions, raw orders, or runtime bundles.
- No Fincept code adoption.

## Acceptance verifier

1. `latest_evidence_report` or equivalent read-only fixture returns sanitized pointer + receipt.
2. Unknown tool id fails closed.
3. Any non-read-only/mutating request is rejected.
4. Tests pass locally.
5. Closure receipt records topology: control-plane contract changed; runtime execution topology unchanged.

## Handoff target

This registry can be consumed by Strategy Powerhouse or operator lanes as a safe inspection surface, but execution remains in governed `steamer-card-engine` runtime paths.
