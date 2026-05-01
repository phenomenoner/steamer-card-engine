from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from steamer_card_engine.adapters.base import (
    BrokerCapabilityProfile,
    BrokerReceipt,
    ExecutionRequest,
    SessionCapabilityEnvelope,
    SessionContext,
    broker_submit_preflight,
)


FIXTURE_PROBE_SCHEMA_VERSION = "adapter-probe/v0"
FIXTURE_ADAPTER_ID = "fixture-paper-only"
FIXTURE_ADAPTER_VENDOR = "fixture"
FIXTURE_ADAPTER_VERSION = "v0"
FIXTURE_DISPATCH_BOUNDARY = "fixture-only; no broker SDK; no live order"


@dataclass(frozen=True, slots=True)
class FixtureAdapterIdentity:
    id: str = FIXTURE_ADAPTER_ID
    vendor: str = FIXTURE_ADAPTER_VENDOR
    version: str = FIXTURE_ADAPTER_VERSION

    def to_public_dict(self) -> dict[str, str]:
        return {"id": self.id, "vendor": self.vendor, "version": self.version}


class FixturePaperOnlyAdapter:
    """Deterministic fixture broker adapter for contract probing only.

    This adapter intentionally has no broker SDK, network, env, credential, or state-file
    dependencies. It exists to prove public contract shape and fail-closed behavior.
    """

    adapter_id = FIXTURE_ADAPTER_ID
    identity = FixtureAdapterIdentity()

    def __init__(self) -> None:
        self.capabilities = BrokerCapabilityProfile(
            marketdata_enabled=True,
            account_query_enabled=False,
            trade_enabled=True,
            paper_trading_enabled=True,
            live_trading_enabled=False,
            supported_actions=("submit", "cancel"),
            rate_limit_policy="fixture deterministic; no transport",
            credential_permission_state="fixture-paper-only",
        )
        self.session = SessionContext(
            session_id="fixture:paper-only",
            auth_mode="unknown",
            authenticated=True,
            health_status="fixture-only",
            capabilities=SessionCapabilityEnvelope(
                marketdata_enabled=True,
                account_query_enabled=False,
                trade_enabled=True,
                paper_trading_enabled=True,
                live_trading_enabled=False,
                supported_actions=("submit", "cancel"),
            ),
            account_scope="fixture-public-scope",
        )

    def submit(self, request: ExecutionRequest) -> BrokerReceipt:
        decision = broker_submit_preflight(
            session=self.session,
            broker=self.capabilities,
            request=request,
        )
        if not decision.allowed:
            return decision.to_receipt(
                request.request_id,
                receipt_id=f"receipt:{request.request_id}",
            )
        return BrokerReceipt(
            request_id=request.request_id,
            status="preflight_allowed",
            message="fixture paper-only preflight allowed; dispatch suppressed",
            retryable=False,
            safe_to_replay=True,
            raw_ref="fixture:paper-only",
            receipt_id=f"receipt:{request.request_id}",
        )

    def cancel(self, broker_order_id: str) -> BrokerReceipt:
        return BrokerReceipt(
            request_id=broker_order_id,
            status="preflight_allowed",
            message="fixture cancel preflight allowed; dispatch suppressed",
            retryable=False,
            safe_to_replay=True,
            raw_ref="fixture:paper-only",
            receipt_id=f"receipt:{broker_order_id}",
        )

    def iter_order_events(self) -> Iterable[object]:
        return ()


def fixture_capabilities_public_dict(profile: BrokerCapabilityProfile) -> dict[str, object]:
    return {
        "marketdata_enabled": profile.marketdata_enabled,
        "account_query_enabled": profile.account_query_enabled,
        "trade_enabled": profile.trade_enabled,
        "paper_trading_enabled": profile.paper_trading_enabled,
        "live_trading_enabled": profile.live_trading_enabled,
        "supported_actions": list(profile.supported_actions),
        "rate_limit_policy": profile.rate_limit_policy,
        "credential_permission_state": profile.credential_permission_state,
    }


def build_fixture_probe_payload(*, fixture: str, execution_mode: str) -> tuple[dict[str, object], int]:
    if fixture != "paper-only":
        payload: dict[str, object] = {
            "adapter": {"id": fixture, "vendor": "fixture", "version": "unknown"},
            "session_posture": "fixture_only",
            "preflight": {
                "decision": "reject",
                "execution_mode": execution_mode,
                "reason": "unknown fixture is not permitted for adapter probe",
            },
            "receipt": {
                "status": "rejected",
                "normalized": True,
                "raw_ref": "fixture:unknown",
            },
            "dispatch": FIXTURE_DISPATCH_BOUNDARY,
            "topology_changed": False,
            "schema_version": FIXTURE_PROBE_SCHEMA_VERSION,
            "no_network": True,
        }
        return payload, 4

    adapter = FixturePaperOnlyAdapter()
    request = ExecutionRequest(
        request_id="fixture-probe-paper-only",
        symbol="<FIXTURE_SYMBOL>",
        side="buy",
        quantity=1,
        execution_mode=execution_mode,  # type: ignore[arg-type]
    )
    decision = broker_submit_preflight(
        session=adapter.session,
        broker=adapter.capabilities,
        request=request,
    )
    receipt = adapter.submit(request)

    if decision.allowed:
        reason = "fixture paper-only capability allows paper preflight"
        decision_label = "allow"
        exit_code = 0
    else:
        reason = decision.reason or "fixture probe failed closed before dispatch"
        decision_label = "reject"
        exit_code = 4

    payload = {
        "adapter": adapter.identity.to_public_dict(),
        "capabilities": fixture_capabilities_public_dict(adapter.capabilities),
        "session_posture": "fixture_only",
        "preflight": {
            "decision": decision_label,
            "execution_mode": execution_mode,
            "reason": reason,
            "session_allows": decision.session_allows,
            "broker_allows": decision.broker_allows,
        },
        "receipt": {
            "status": "ok" if decision.allowed else "rejected",
            "normalized": True,
            "raw_ref": receipt.to_public_dict()["raw_ref"] or "fixture:paper-only",
            "public": receipt.to_public_dict(),
        },
        "dispatch": FIXTURE_DISPATCH_BOUNDARY,
        "topology_changed": False,
        "schema_version": FIXTURE_PROBE_SCHEMA_VERSION,
        "input_hash": "fixture-paper-only:v0:paper-probe",
        "no_network": True,
    }
    return payload, exit_code
