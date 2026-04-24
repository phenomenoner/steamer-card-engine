# Closure Receipt — Fincept Absorption Item 2

Date: 2026-04-24
Item: BrokerAdapter capability + normalized error envelope

## Commits

- `a913dd4` — feat: add broker capability error envelope
- `3431b0c` — fix: fail closed on unknown execution modes

## Review outcome

Implementation review verdict: request-changes.

Blocker addressed immediately:
- `BrokerCapabilityProfile.allows()` now rejects unknown execution modes instead of treating every non-`live` value as paper.
- Added test coverage for malformed/external mode values such as `sandbox`.

Non-blocking nit tracked for future hardening:
- `BrokerReceipt.to_public_dict()` remains a safe normalized surface by contract, but `message` and `raw_ref` are not yet centrally sanitized. Future item 3/session-capability work should consider bounded message/raw-ref helpers or adapter responsibility tests.

## Verification

- `uv run ruff check src/steamer_card_engine/adapters/base.py tests/test_broker_adapter_contract.py` — passed
- `uv run pytest tests/test_broker_adapter_contract.py tests/test_session_phase.py` — 6 passed
- `uv run pytest` — 95 passed

## Boundary

- No real broker adapter was implemented.
- No auth/secret flow was added.
- No CLI live authority was expanded.
- No Fincept code was copied.
- Live/paper submit remains explicit capability-gated fail-closed behavior.

## Topology

Topology changed: docs/test/base adapter contract only inside `steamer-card-engine`.
Authority broadened: no.
Runtime live-trading capability changed: no.

## Historical next step

ROI item 3 was the next step at the time of this receipt and is now closed. See `docs/receipts/2026-04-24_fincept_absorption_rollup_closure.md`.
