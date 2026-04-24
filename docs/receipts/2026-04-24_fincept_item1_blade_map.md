# Sakura Blade Map — Fincept Absorption Item 1

Date: 2026-04-24
Scope: Evidence Provenance Envelope + MarketDataHub stats
Posture: docs-first, remote-safe, no strategy-private leakage

## Gate

Turn the first Fincept absorption item into a Steamer-native contract, not a generic architecture note.

## Review receipt

Claude CLI review was attempted first but failed with authentication error. A same-purpose Copilot reviewer fallback completed read-only review and recommended proceeding if the slice stays contract-first.

Reviewer verdict: proceed, but do not overclaim runtime maturity.

## Slice 1 — Contract landing

Targets:
- `docs/EVIDENCE_PROVENANCE_ENVELOPE_SPEC.md`
- `docs/ARCHITECTURE.md`
- `docs/SIM_ARTIFACT_SPEC.md`
- `docs/TOPOLOGY.md`
- optional tiny inert schema helpers/tests only if already aligned with existing code shape

Requirements:
- Define aggregate-only provenance envelope.
- Define bounded reason taxonomy: `no_trades`, `warmup_not_ready`, `insufficient_bars`, `other_reject`, `pass`, plus unknown/error only if needed.
- Define read-only MarketDataHub stats/introspection contract.
- Cross-link to Fincept absorption ROI map.
- Explicitly forbid raw symbols, accounts, params, orders/trades, raw event excerpts, and path leakage.
- Mark real runtime introspection as not implemented unless code already supports it.

Verifier:
- Payload can be serialized without raw symbols/params/accounts/trades.
- Banned keys are absent.
- Zero/low coverage can be explained by aggregate reason counts.
- MarketDataHub stats expose counts/timestamps/error summaries only, not subscriber identities/raw events.

## Slice 2 — Main review/integration

After Minion returns:
- inspect diff
- run targeted tests/docs checks if applicable
- commit only this slice

## Slice 3 — Minion code review

Dispatch separate review session after integration.

Review asks:
- privacy boundary
- overclaiming runtime behavior
- consistency with existing card-engine architecture
- verifier adequacy

## Stop-loss

Stop and report if implementation tries to:
- touch `/workspace/steamer` raw local-only data
- add broad connector/runtime implementation
- introduce live broker/session behavior
- copy Fincept code
- leak strategy-private material
