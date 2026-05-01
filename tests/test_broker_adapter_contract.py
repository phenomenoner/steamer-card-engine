from __future__ import annotations

import json
from typing import Iterable

from steamer_card_engine.adapters.base import (
    BrokerCapabilityProfile,
    BrokerReceipt,
    ExecutionRequest,
    SessionCapabilityEnvelope,
    SessionContext,
    broker_submit_preflight,
    normalized_broker_reject,
)
from steamer_card_engine.adapters.fixture_exchange import (
    FIXTURE_DISPATCH_BOUNDARY,
    FixturePaperOnlyAdapter,
    build_fixture_probe_payload,
)


class FixtureBrokerAdapter:
    adapter_id = "fixture-paper-only"

    def __init__(self) -> None:
        self.capabilities = BrokerCapabilityProfile(
            marketdata_enabled=True,
            account_query_enabled=True,
            trade_enabled=True,
            paper_trading_enabled=True,
            live_trading_enabled=False,
            supported_actions=("submit", "cancel", "positions"),
            rate_limit_policy="fixture: 1/s",
            credential_permission_state="paper-only",
        )
        self._vendor_payload = {
            "token": "super-secret-token",
            "raw_response": "vendor says live trading disabled",
        }

    def submit(self, request: ExecutionRequest) -> BrokerReceipt:
        if not self.capabilities.allows("submit", request.execution_mode):
            return normalized_broker_reject(
                request_id=request.request_id,
                category="capability_mismatch",
                message="live submit is not enabled for this broker capability profile",
                retryable=False,
                safe_to_replay=True,
                raw_ref="fixture-log:capability-mismatch",
                receipt_id=f"receipt:{request.request_id}",
            )
        return BrokerReceipt(request_id=request.request_id, status="accepted")

    def cancel(self, broker_order_id: str) -> BrokerReceipt:
        return BrokerReceipt(request_id=broker_order_id, status="cancelled")

    def iter_order_events(self) -> Iterable[object]:
        return ()


def test_paper_only_adapter_rejects_live_submit_with_capability_mismatch() -> None:
    adapter = FixtureBrokerAdapter()
    request = ExecutionRequest(
        request_id="req-live-1",
        symbol="<SYMBOL>",
        side="buy",
        quantity=1,
        execution_mode="live",
    )

    receipt = adapter.submit(request)

    assert receipt.status == "rejected"
    assert receipt.error is not None
    assert receipt.error.category == "capability_mismatch"
    assert receipt.receipt_id == "receipt:req-live-1"
    assert receipt.raw_ref == "fixture-log:capability-mismatch"


def test_capability_mismatch_metadata_is_stable_and_replay_safe() -> None:
    adapter = FixtureBrokerAdapter()
    receipt = adapter.submit(
        ExecutionRequest(
            request_id="req-live-2",
            symbol="<SYMBOL>",
            side="sell",
            quantity=1,
            execution_mode="live",
        )
    )

    assert receipt.retryable is False
    assert receipt.safe_to_replay is True
    assert receipt.error is not None
    assert receipt.error.retryable is False
    assert receipt.error.safe_to_replay is True
    assert receipt.error.raw_ref == receipt.raw_ref
    assert receipt.error.receipt_id == receipt.receipt_id


def test_normalized_receipt_does_not_expose_vendor_payload_or_secrets() -> None:
    adapter = FixtureBrokerAdapter()
    receipt = adapter.submit(
        ExecutionRequest(
            request_id="req-live-3",
            symbol="<SYMBOL>",
            side="buy",
            quantity=1,
            execution_mode="live",
        )
    )

    serialized = json.dumps(receipt.to_public_dict(), sort_keys=True)

    assert "super-secret-token" not in serialized
    assert "vendor says live trading disabled" not in serialized
    assert "raw_response" not in serialized
    assert "token" not in serialized
    assert "fixture-log:capability-mismatch" in serialized


def test_capability_profile_rejects_unknown_execution_mode_fail_closed() -> None:
    profile = BrokerCapabilityProfile(
        trade_enabled=True,
        paper_trading_enabled=True,
        live_trading_enabled=True,
        supported_actions=("submit",),
    )

    assert profile.allows("submit", "sandbox") is False  # type: ignore[arg-type]


def test_logged_in_trade_disabled_session_allows_data_health_but_submit_fails_closed() -> None:
    session = SessionContext(
        session_id="session-fixture-1",
        auth_mode="account_api_key_cert",
        authenticated=True,
        health_status="healthy",
        capabilities=SessionCapabilityEnvelope(
            marketdata_enabled=True,
            account_query_enabled=True,
            trade_enabled=False,
            paper_trading_enabled=False,
            live_trading_enabled=False,
            supported_actions=("marketdata", "positions"),
        ),
        account_scope="<ACCOUNT_SCOPE>",
    )
    broker = BrokerCapabilityProfile(
        trade_enabled=True,
        paper_trading_enabled=True,
        supported_actions=("submit",),
        credential_permission_state="paper-only",
    )
    request = ExecutionRequest(
        request_id="req-session-paper-1",
        symbol="<SYMBOL>",
        side="buy",
        quantity=1,
        execution_mode="paper",
    )

    decision = broker_submit_preflight(session=session, broker=broker, request=request)
    receipt = decision.to_receipt(request.request_id, receipt_id="receipt:req-session-paper-1")

    assert session.allows_marketdata() is True
    assert session.allows_account_query("positions") is True
    assert decision.allowed is False
    assert decision.session_allows is False
    assert decision.broker_allows is True
    assert receipt.status == "rejected"
    assert receipt.error is not None
    assert receipt.error.category == "capability_mismatch"


def test_unknown_execution_mode_submit_preflight_fails_closed() -> None:
    session = SessionContext(
        session_id="session-fixture-2",
        auth_mode="account_api_key_cert",
        authenticated=True,
        health_status="healthy",
        capabilities=SessionCapabilityEnvelope(
            trade_enabled=True,
            paper_trading_enabled=True,
            live_trading_enabled=True,
            supported_actions=("submit",),
        ),
    )
    broker = BrokerCapabilityProfile(
        trade_enabled=True,
        paper_trading_enabled=True,
        live_trading_enabled=True,
        supported_actions=("submit",),
    )
    request = ExecutionRequest(
        request_id="req-unknown-mode",
        symbol="<SYMBOL>",
        side="buy",
        quantity=1,
        execution_mode="sandbox",  # type: ignore[arg-type]
    )

    decision = broker_submit_preflight(session=session, broker=broker, request=request)

    assert decision.allowed is False
    assert decision.category == "capability_mismatch"
    assert decision.session_allows is False
    assert decision.broker_allows is False


def test_public_receipt_sanitizes_message_and_raw_ref() -> None:
    receipt = normalized_broker_reject(
        request_id="req-secret-public",
        category="unknown",
        message="broker token=super-secret-token leaked in raw payload",
        retryable=False,
        safe_to_replay=False,
        raw_ref="local log token=super-secret-token",
        receipt_id="receipt id one",
    )

    public_payload = receipt.to_public_dict()
    serialized = json.dumps(public_payload, sort_keys=True)

    assert "super-secret-token" not in serialized
    assert public_payload["message"] == "[redacted]"
    assert public_payload["raw_ref"] == "[redacted]"
    assert public_payload["receipt_id"] == "receipt_id_one"


def test_session_public_dict_uses_placeholder_safe_scope() -> None:
    session = SessionContext(
        session_id="session-fixture-3",
        authenticated=True,
        capabilities=SessionCapabilityEnvelope(marketdata_enabled=True),
        account_scope="<ACCOUNT_SCOPE>",
        vendor_metadata={"token": "super-secret-token"},
    )

    serialized = json.dumps(session.to_public_dict(), sort_keys=True)

    assert "super-secret-token" not in serialized
    assert "<ACCOUNT_SCOPE>" not in serialized
    assert "_ACCOUNT_SCOPE_" in serialized

def test_fixture_probe_payload_allows_paper_only_without_dispatch() -> None:
    payload, exit_code = build_fixture_probe_payload(fixture="paper-only", execution_mode="paper")

    assert exit_code == 0
    assert payload["adapter"] == {"id": "fixture-paper-only", "vendor": "fixture", "version": "v0"}
    assert payload["capabilities"]["paper_trading_enabled"] is True
    assert payload["capabilities"]["live_trading_enabled"] is False
    assert payload["preflight"]["decision"] == "allow"
    assert payload["receipt"]["status"] == "ok"
    assert payload["receipt"]["normalized"] is True
    assert payload["dispatch"] == FIXTURE_DISPATCH_BOUNDARY
    assert payload["topology_changed"] is False
    assert payload["no_network"] is True


def test_fixture_probe_rejects_live_and_unknown_modes_before_dispatch() -> None:
    live_payload, live_exit = build_fixture_probe_payload(fixture="paper-only", execution_mode="live")
    unknown_payload, unknown_exit = build_fixture_probe_payload(
        fixture="paper-only",
        execution_mode="sandbox",
    )

    assert live_exit == 4
    assert live_payload["preflight"]["decision"] == "reject"
    assert live_payload["preflight"]["broker_allows"] is False
    assert live_payload["dispatch"] == FIXTURE_DISPATCH_BOUNDARY
    assert unknown_exit == 4
    assert unknown_payload["preflight"]["decision"] == "reject"
    assert unknown_payload["preflight"]["reason"] == "unknown execution mode is not permitted for broker submit"
    assert unknown_payload["dispatch"] == FIXTURE_DISPATCH_BOUNDARY


def test_fixture_probe_public_payload_contains_no_secret_like_or_vendor_raw_material() -> None:
    payload, _ = build_fixture_probe_payload(fixture="paper-only", execution_mode="paper")
    serialized = json.dumps(payload, sort_keys=True).lower()

    forbidden = ("token", "password", "api_key", "secret", "cert", "raw_response", "env")
    assert all(term not in serialized for term in forbidden)


def test_fixture_adapter_has_no_order_events_or_live_capability() -> None:
    adapter = FixturePaperOnlyAdapter()

    assert adapter.capabilities.live_trading_enabled is False
    assert adapter.capabilities.account_query_enabled is False
    assert tuple(adapter.iter_order_events()) == ()


def test_fixture_contract_explain_schema_pins_stage1_surfaces() -> None:
    from steamer_card_engine.adapters.fixture_exchange import build_fixture_explain_payload

    payload, exit_code = build_fixture_explain_payload(adapter_id="fixture-paper-only")

    assert exit_code == 0
    assert payload["schema_version"] == "adapter-contract/v1"
    assert payload["dispatch"] == FIXTURE_DISPATCH_BOUNDARY
    assert payload["topology_changed"] is False
    contract = payload["contract"]
    assert contract["input_context"]["required"] == [
        "card_id",
        "deck_id",
        "symbol",
        "side",
        "quantity",
        "execution_mode",
        "signal",
    ]
    assert contract["order_intent_candidate"]["broker_native_order"] is None
    assert contract["receipt_envelope"]["broker_native_orders_allowed"] is False
    assert "receipt_envelope" in contract
    assert "sanitizer_contract" in contract


def test_fixture_contract_case_outputs_are_deterministic_and_not_broker_native() -> None:
    from steamer_card_engine.adapters.fixture_exchange import evaluate_fixture_contract_case

    case = {
        "case_id": "paper-buy-valid",
        "input_context": {
            "card_id": "fixture-card-paper-buy",
            "deck_id": "fixture-deck-paper-only",
            "symbol": "<FIXTURE_SYMBOL>",
            "side": "buy",
            "quantity": 1,
            "execution_mode": "paper",
            "signal": {"action": "enter", "confidence": 0.75, "reason": "fixture-threshold-cross"},
        },
    }

    first = evaluate_fixture_contract_case(case)
    second = evaluate_fixture_contract_case(case)

    assert first == second
    assert first["normalized_signal"]["decision"] == "allow"
    assert first["normalized_signal"]["reason_code"] == "paper_preflight_allowed"
    assert first["order_intent_candidate"]["kind"] == "normalized_order_intent_candidate"
    assert first["order_intent_candidate"]["broker_native_order"] is None
    assert first["broker_native_orders"] == []
    assert first["dispatch"] == FIXTURE_DISPATCH_BOUNDARY


def test_fixture_contract_reject_and_noop_reasons_are_stable() -> None:
    from steamer_card_engine.adapters.fixture_exchange import evaluate_fixture_contract_case

    live_reject = evaluate_fixture_contract_case(
        {
            "case_id": "live-buy-rejected",
            "input_context": {
                "symbol": "<FIXTURE_SYMBOL>",
                "side": "buy",
                "quantity": 1,
                "execution_mode": "live",
                "signal": {"action": "enter"},
            },
        }
    )
    noop = evaluate_fixture_contract_case(
        {
            "case_id": "hold-noop",
            "input_context": {
                "symbol": "<FIXTURE_SYMBOL>",
                "side": "buy",
                "quantity": 0,
                "execution_mode": "paper",
                "signal": {"action": "hold"},
            },
        }
    )

    assert live_reject["normalized_signal"]["decision"] == "reject"
    assert live_reject["normalized_signal"]["reason_code"] == "capability_mismatch"
    assert live_reject["reject_or_noop_reason"]["stable_reason"]
    assert noop["normalized_signal"]["decision"] == "noop"
    assert noop["normalized_signal"]["reason_code"] == "signal_no_action"
    assert noop["order_intent_candidate"] is None
    assert noop["reject_or_noop_reason"]["stable_reason"] == "signal action does not request an order intent"


def test_fixture_contract_check_golden_cases_and_sanitized_public_payload() -> None:
    from pathlib import Path

    from steamer_card_engine.adapters.fixture_exchange import build_fixture_contract_check_payload

    payload, exit_code = build_fixture_contract_check_payload(
        adapter_id="fixture-paper-only",
        fixtures_path=Path("examples/probes/adapter_contract"),
    )
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert exit_code == 0
    assert payload["summary"] == {"checked": 3, "failed": 0, "decision": "pass"}
    assert {case["normalized_signal"]["reason_code"] for case in payload["cases"]} == {
        "paper_preflight_allowed",
        "capability_mismatch",
        "signal_no_action",
    }
    assert "broker_native_order" in serialized
    for term in ("super-secret-token", "raw_response", "api_key", "password"):
        assert term not in serialized
