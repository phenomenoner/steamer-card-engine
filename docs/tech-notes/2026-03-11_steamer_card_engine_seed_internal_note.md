# Steamer Card Engine — Internal Seed Note (2026-03-11)

## Why this note exists
This is the **internal continuity note** for the public seed repo:
- public repo: `phenomenoner/steamer-card-engine`
- URL: `https://github.com/phenomenoner/steamer-card-engine`

The public repo is intentionally **docs-first + bounded-contract-first**. This note records how we should interpret it internally, what is already true, and what still remains private/operator-side discussion rather than public README material.

## Current status
Public seed repo already landed and was iterated in three bounded steps:
1. public seed repo scaffold + initial product/spec docs
2. bounded executable-contract slice
   - manifest schemas/models for auth/card/deck/global
   - CLI validate/inspect commands
   - tests for manifest/CLI behavior
3. consultant + topology pass
   - Copilot CLI consultant review captured in repo
   - public repo topology doc added
   - public README cleaned of internal TODO/process chatter

Current public receipts:
- seed repo initial commit: `82d1c5b35e513dac7ebe2e00fff0443a08783c1f`
- docs/contract refinement pass: `86abfa7be7ce0870c9f3069ee440e743e49db832`
- executable manifest slice: `20462bc`
- consultant/topology cleanup: `6221d0b`

## Boundary (important)
`steamer-card-engine` is **not** the live Steamer execution lane.

It is a **productization track** for a future card-oriented runtime with these design goals:
- Taiwan **stock intraday** scope first (not "cash intraday" wording)
- single/shared connection/session posture where supported
- shared market-data hub + reusable feature/synthesizer layer
- cards emit intents, not direct orders
- CLI-managed card/deck/global/auth contracts
- replay-first / live-sim-first progression
- adapter-swappable broker/marketdata boundary

This should be treated internally as:
- a **planning + contract hardening** repo now
- a future runtime candidate later
- **not** the current production/SIM system of record

## What CK explicitly wants preserved internally
These points came from live discussion and should remain easy to recover later:
- each card may own its own symbol pool; enabled cards feed subscription planning
- auth/session should support at least:
  - account + password + cert + cert password
  - account + API key + cert + cert password
- API-key-with-trade-disabled is a valid safety boundary for agent-assisted setup
- day-trade controls need explicit config surfaces for:
  - emergency stop / fast stop behavior
  - forced intraday exit windows
  - optional final-auction flatten behavior around `13:25–13:30 Asia/Taipei`
- cards should express more than entries:
  - stop-loss / take-profit
  - symbol pool
  - capital controls
  - feature requirements / derived-series needs
- marketdata + trading/account login/session posture should be modeled once and shared when the adapter supports it
- routing/order lifecycle handling must be filterable by:
  - active account number
  - `user_def`
- low latency is first-class for day trading
- marketdata should be recordable/replayable; execution should support live-sim + replay-sim

## Internal interpretation of current roadmap
Useful near-term shape after today’s work:
- v0.1-ish seed is now real enough for contract discussion
- next likely worthwhile internal track:
  1. contract hardening (`Intent`, execution requests, receipts, lifecycle events)
  2. replay artifacts/schema discipline + roundtrip tests
  3. only then adapter shim / live-sim governance posture

This matches the external consultant signal as well.

## What should stay out of public README
Do not leak internal chore sequencing or agent workflow notes into the public entrypoint, e.g.:
- “TODO / NEXT (deferred by scope)” process lists
- internal operator sequencing notes
- internal-only follow-up choreography

If it is useful internally, keep it here, in workspace memory, or in a private handoff/note — not in the public README.

## Suggested internal next discussion
When resuming, discuss in this order:
1. whether to push into contract-hardening now or let the seed sit briefly
2. whether the future runtime should stay under the Steamer umbrella or eventually split branding/product identity further
3. how much of the current Steamer bot’s execution/rate-limit/exception-handling logic should be codified as explicit migration contracts before adapter work starts

## Cross-reference
- public repo topology: `steamer-card-engine/docs/TOPOLOGY.md`
- workspace durable note: `/root/.openclaw/workspace/memory/2026-03-11.md`
