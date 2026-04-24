# Blade Map — Fincept Absorption Item 4

Date: 2026-04-24
Item: Strategy Powerhouse handoff task/activity receipts

## Verdict

Implement a remote-safe handoff/activity receipt contract for `strategy-powerhouse-framework`, then expose a seed example/verifier proving a synthetic-verifier handoff can emit machine-readable activity and final engine handoff packets without runtime execution.

## Whole-picture promise

Strategy Powerhouse stays a research + packaging + control-plane lane. It may describe work, evidence refs, verifier status, and handoff intent, but it must not become the live-sim runtime or leak strategy-private material.

## Scope

Primary repo: `/root/.openclaw/workspace/strategy-powerhouse-framework`

Additive contract-first slice:

- Define task/activity event schema for the six research-cycle stages:
  - intake
  - family_selection
  - backtest_estimate
  - synthetic_verifier
  - engine_handoff
  - closure
- Define final engine handoff packet schema with:
  - candidate family id
  - execution intent (`replay`, `deck_validation`, `live_sim_observation`)
  - expected card/deck surfaces
  - verifier status/target
  - evidence packet refs
  - local-only omissions
  - rollback/safe abort
  - topology statement
- Provide a small Python helper or model layer that serializes deterministic, remote-safe packet dictionaries.
- Add tests or a deterministic verifier command proving one synthetic-verifier handoff emits valid activity log + final handoff JSON and does not execute runtime/deck/live-sim work.
- Update docs/templates to point at the contract.

## Non-goals

- No runtime execution.
- No deck mutation.
- No live-sim launch.
- No strategy params, raw symbols, account/broker info, or raw runtime bundles.
- No Fincept code adoption.
- No generic AI-agent/task sprawl.

## Acceptance verifier

1. One synthetic-verifier handoff fixture emits a machine-readable activity log.
2. The final handoff packet includes verifier status, next `steamer-card-engine` target, evidence refs, omissions, rollback, and topology.
3. Public fixture content remains placeholder-safe.
4. Tests or deterministic verifier pass locally.
5. A closure receipt records topology: framework contract changed; runtime execution topology unchanged.

## Handoff target

`steamer-card-engine` only receives the packaged handoff target. Actual card/deck/replay/live-sim work remains outside this item.
