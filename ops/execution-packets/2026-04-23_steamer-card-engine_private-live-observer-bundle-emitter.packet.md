# Execution packet — steamer-card-engine private live observer bundle emitter

## Objective

Build the first **private-only bundle emitter** that converts one truthful live(sim) runtime surface into a sanitized observer bundle file consumable by the public-safe observer API.

The proof is:

> one private runtime path can continuously publish `metadata + events` for one session, and the existing observer sidecar can mount it through `STEAMER_OBSERVER_BUNDLE_JSON` without schema drift or sensitive leakage.

## In scope
- one session only
- one symbol only
- private runtime emitter only
- atomic bundle writes
- sanitized observer event emission
- attachment proof through the existing observer API

## Out of scope
- multi-session fanout
- browser auth/network hardening
- broker control/write actions
- public repo commits of private mapping logic

## Recommended upstream choice

Pick the narrowest truthful upstream pair that can show life:
1. session/probe health snapshot
2. candle/event source for one symbol

If order/fill/position truth is not yet cleanly reachable, do not fake it. Land health + candles first, then widen.

## Output contract

Private emitter writes a bundle JSON file:
- private runtime path under `/root/.openclaw/workspace/.state/steamer/observer/private/`
- mounted by `STEAMER_OBSERVER_BUNDLE_JSON`
- with `STEAMER_OBSERVER_INCLUDE_MOCK=0`

## Verifier plan

Must-pass:
1. attached session appears via `/api/observer/sessions`
2. `/bootstrap`, `/candles`, `/timeline`, and `/stream` all work for that session
3. reconnect after `after_seq` resumes cleanly
4. payload scan finds no forbidden fields
5. mock-disabled mode does not leak the demo session

## Stop-loss

Stop and report if:
- emitter wiring requires private logic to enter the public repo
- upstream truth for candles and state is split across incompatible sources
- the first slice drifts into deploy/auth work before one attached session is proven

## Closure

- checkpoint with mounted bundle path and verifier receipts
- topology statement
- no public push of private emitter code or payloads
