# Copilot Consultant Review (Architecture / Roadmap / Tests)

- Date (UTC): 2026-03-11
- Tool: `copilot` CLI (local)
- Command (approx):
  - `copilot -s --output-format text --deny-tool write --model gpt-5.4 -p "...review repo..."`
- Scope: docs + current Python skeleton only (no new implementation work)

> Notes
>
> - This document captures the **verbatim** consultant-style critique returned by Copilot CLI.
> - Any actionable follow-ups should be treated as **recommendations**, not already-implemented behavior.

---

I’m gathering the architecture docs and code surface first, then I’ll synthesize a focused review against your requested headings.

I’ve got the spec surface. Now I’m skimming the implementation skeleton to compare the stated contracts against what’s actually concretized today.

I’ve now compared the docs against the concrete datamodel/validator skeleton. One more quick pass on the manifest summaries and I can write the review.

## A. What’s strong

`README.md` and `docs/PRODUCT_SCOPE.md` are unusually honest about scope and authority. The repeated stance that cards emit intent, while operator-governed risk/execution owns live authority, is the right product boundary for this domain.

`docs/ARCHITECTURE.md` is strongest where it separates authoring/management from execution, and where it insists on a platform-owned `FeaturePipeline` instead of per-card indicator code. That is the best anti-monolith move in the repo.

`docs/AUTH_AND_SESSION_MODEL.md` and `docs/ADAPTER_SPEC.md` correctly treat shared logical session state, capability inspection, and `active_account + user_def` routing as first-class contracts, not implementation trivia.

The current Python skeleton also stays disciplined: `manifest.py` and `tests/test_manifests.py` implement just enough manifest validation without pretending runtime behavior exists yet.

## B. Boundary & contract gaps / ambiguities

The main gap is that the docs describe rich contracts, but the concrete models are still materially thinner.

`docs/CARD_SPEC.md` says `Intent` requires `timestamp`, `card_version`, `deck_id`, `time_horizon`, optional `price_reference`, `urgency`, `evidence_snapshot`, and `requested_user_def_suffix`; but `src/steamer_card_engine/models.py` only has `intent_id`, `card_id`, `symbol`, `side`, `intent_type`, `reason`, `confidence`, `size_hint`, `tags`. That is a contract hole, not just backlog.

`docs/ADAPTER_SPEC.md` requires normalized market events with `ts_exchange`, `ts_adapter`, and broker lifecycle events with `account_no`, `order_no`, `user_def`, etc. But `adapters/base.py` only defines a thin `MarketEvent` and no `OrderLifecycleEvent` at all. `ExecutionRequest` is also under-specified: no account, no routing marker, no order policy, no reduce-only / flatten reason.

`docs/ARCHITECTURE.md` gives `IntentAggregator` real conflict-resolution responsibility, but `runtime/components.py` only appends intents. The missing rule set is important: what happens when one card wants `enter long` and another wants `exit` on the same symbol?

Deck/global overlay semantics are still vague. Specific missing behaviors:
- precedence between card risk, deck risk, and global risk
- whether deck can widen card limits or only tighten them
- how `live_enabled` and `dry_run` interact if both are true
- whether `allow_card_symbol_pool=false` drops card-declared symbols silently or raises validation/runtime errors
- whether forced-exit windows are declarative hints or hard policy

Auth/session also needs explicit contracts for renewal behavior: what happens to active intents/orders during stale-session, partial reconnect, or capability downgrade?

## C. Roadmap phase allocation: suggested v0.2 / v0.3

### v0.2
Make this the **contract-hardening + replay receipt** release.

Include:
- concrete models for `MarketEvent`, `FeatureSnapshot`, `Intent`, `ExecutionRequest`, `OrderLifecycleEvent`, `RiskDecision`, `ExecutionReceipt`
- manifest schemas aligned to those models
- replay-run artifact format and CLI inspection
- one replay-only card end-to-end through receipts

Success criteria:
- replay produces deterministic-enough receipts for the same event source and config
- every intent and execution decision is attributable to card/version/deck/feature version
- CLI can validate and inspect all artifacts without live connectivity

Defer:
- real broker shim
- operator arm/disarm
- live-sim with live feeds

### v0.3
Make this the **adapter shim + live-sim governance** release.

Include:
- first TW cash market-data and broker adapter shim
- logical `SessionContext` with capability/health transitions
- live-sim path with real market data, fake execution
- explicit operator status/inspect commands

Success criteria:
- mixed order events are routed by account + `user_def`
- live-sim and replay share intent/risk/execution contracts
- operator can inspect active authority and session posture before any arm-live concept exists

Defer:
- multi-deck
- dynamic plugins
- live order submission
- advanced card conflict scheduling

## D. Test strategy

Unit tests:
- manifest validation edge cases in `manifest.py`
- merge semantics for deck/card/global overlays
- time-window validation for forced exit and final auction
- auth mode exclusivity and secret-source rules

Contract tests:
- `Intent` serialization includes provenance and routing metadata
- `MarketEvent` / `OrderLifecycleEvent` normalization rejects missing timestamp/account/routing fields
- replay artifact schema round-trip
- adapter capability mismatch surfaces structured failure states

CLI tests:
- stable exit codes for invalid manifests
- `inspect-* --json` shape snapshots
- replay run manifest creation and replay inspect output
- operator/status refusing ambiguous live posture

Concrete missing tests:
- conflicting intents from two cards on one symbol
- `allow_card_symbol_pool=false` behavior
- stale session during replay/live-sim transition
- account mismatch or `user_def` mismatch dropping lifecycle events
- final-auction flatten overriding card take-profit/hold logic

## E. Risks

Latency / hot-path:
The biggest risk is accidental drift into “spec says low latency, implementation reintroduces it later.” Non-blocking recorder, shared feature compute, and routing structures should become model/test requirements early.

Replay fidelity:
Right now receipts are described, not defined. Without stable event/feature/intent/execution artifacts, replay will become theater.

Operator authority:
Good docs, but authority boundaries still need executable states: disarmed, replay-only, live-sim, armed-live, degraded-session.

Auth/session safety:
Capability downgrade and partial reconnect are under-specified. That is exactly where unsafe behavior leaks in.

## F. Doc-only improvements

Small edits I’d make:
- Add one table in `docs/ARCHITECTURE.md` for **who may tighten vs widen** policy: card, deck, global, operator.
- Add canonical field tables for `Intent`, `ExecutionRequest`, and `OrderLifecycleEvent`.
- In `docs/CLI_SPEC.md`, define exit-code conventions explicitly.
- In `docs/MIGRATION_PLAN.md`, move “define concrete models” ahead of “adapter shim”; that is the real dependency.
- In `docs/CARD_SPEC.md`, say whether deck/global may reject invalid card symbol pools at validation time vs runtime.

Most opinionated take: the repo is **not overdesigned overall**; it is appropriately bounded. The one accidental complexity risk is talking about many components before freezing the minimal executable contracts between them.
