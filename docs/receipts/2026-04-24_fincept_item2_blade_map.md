# Sakura Blade Map — Fincept Absorption Item 2

Date: 2026-04-24
Scope: BrokerAdapter capability + normalized error envelope
Posture: contract-first, additive, no real broker authority

## Gate

Turn BrokerAdapter from a simple receipt/status stub into a safer contract surface for capability-gated broker operations and normalized errors, without implementing real broker behavior.

## Reviewer receipt

Claude CLI lane remains blocked by local auth. Copilot read-only reviewer fallback completed review and recommended proceeding if the slice stays additive and fail-closed.

Reviewer verdict: proceed.

## Slice 1 — Contract landing

Targets:
- `docs/ADAPTER_SPEC.md`
- `docs/AUTH_AND_SESSION_MODEL.md`
- optional `docs/FINCEPT_ABSORPTION_ROI.md` cross-link/tightening
- `src/steamer_card_engine/adapters/base.py`
- `tests/test_broker_adapter_contract.py`

Requirements:
- Define broker capability profile and explicit trade permission gating.
- Define normalized error taxonomy:
  - `auth`
  - `insufficient_funds`
  - `invalid_order`
  - `rate_limit`
  - `network`
  - `unavailable`
  - `capability_mismatch`
  - `unknown`
- Define metadata: `retryable`, `safe_to_replay`, `raw_ref`, `receipt_id`.
- Keep vendor/raw payloads out of the normalized receipt.
- Add tiny inert dataclass/helper additions only.
- Preserve existing adapter signatures unless unavoidable.

Verifier:
- A paper-only/no-live fixture rejects submit with `capability_mismatch`.
- The reject is fail-closed and safe to replay.
- Receipt/error serialization does not leak raw vendor payloads/secrets.
- Existing tests continue to pass.

## Stop-loss

Stop and report if implementation tries to:
- implement a real broker adapter
- add auth/secret handling
- expand CLI live authority
- turn paper/live into a casual boolean without capability gating
- copy Fincept code
