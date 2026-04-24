# Blade Map — Fincept Absorption Item 3

Date: 2026-04-24
Item: AuthSessionManager capability envelope

## Verdict

Implement a seed-grade logical session capability envelope, not real broker login.

The goal is to make successful login distinct from marketdata/account/trade authority, then make downstream broker-submit preflight fail closed unless both session and broker capabilities explicitly allow the requested action/mode.

## Scope

Additive contract-first slice in `steamer-card-engine`:

- Define session capability facts for marketdata, account query, paper trading, and live trading.
- Define a logical session context/status shape with auth mode, health, expiry/renewal hints, and degraded-state reason.
- Add a small helper/preflight contract that combines session capability and `BrokerCapabilityProfile` capability for submit decisions.
- Add tests showing a logged-in but trade-disabled session still allows marketdata/account health while broker submit fails closed.

## Non-goals

- No real login implementation.
- No credential/certificate storage.
- No real broker adapter integration.
- No live-trading authority expansion.
- No Fincept code adoption.
- No raw account identifiers or strategy-private params in docs/fixtures.

## Target files

Likely files:

- `src/steamer_card_engine/adapters/base.py`
- `tests/test_broker_adapter_contract.py` or a new focused auth/session contract test
- `docs/AUTH_AND_SESSION_MODEL.md`
- `docs/ADAPTER_SPEC.md` if broker preflight wording needs alignment

## Acceptance verifier

1. A session fixture can be `authenticated` / healthy for marketdata.
2. The same session can be trade-disabled.
3. A submit preflight with trade-disabled session rejects, even if broker paper capability exists.
4. Unknown/malformed execution mode stays fail-closed.
5. Public serialized output contains only placeholder-safe fields.
6. Targeted ruff + targeted pytest + full pytest pass.

## Review note carried from Item 2

`BrokerReceipt.to_public_dict()` is normalized but does not centrally sanitize arbitrary `message` / `raw_ref` content. Item 3 should either:

- add bounded public text/reference helpers, or
- explicitly document/test adapter responsibility without broadening the slice.

Prefer the smallest safe hardening if it is low-risk.
