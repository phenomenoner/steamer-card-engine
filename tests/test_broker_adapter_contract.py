from __future__ import annotations

import json
from typing import Iterable

from steamer_card_engine.adapters.base import (
    BrokerCapabilityProfile,
    BrokerReceipt,
    ExecutionRequest,
    normalized_broker_reject,
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
