from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal, Protocol, TypedDict


class BrokerDryRunError(ValueError):
    def __init__(self, message: str, *, exit_code: int = 2, reason: str = "invalid") -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.reason = reason


class MockTransportHealth(TypedDict):
    transport_id: str
    transport_kind: str
    connectivity: str
    no_network: bool
    credential_inspection: str
    account_inspection: str


class ExecutionRequest(TypedDict):
    case_id: str
    symbol_ref: str
    side: str
    quantity: int
    order_type: str
    time_in_force: str


class DryRunTranslation(TypedDict):
    case_id: str
    request_id: str
    symbol_ref: str
    side: str
    quantity: int
    order_type: str
    time_in_force: str
    dry_run_operation: str
    broker_native_order: None
    dispatch_suppressed: bool


class MockBrokerDryRunTransport(Protocol):
    transport_id: str
    no_network: Literal[True]

    def preflight(self) -> MockTransportHealth: ...
    def translate_order(self, request: ExecutionRequest) -> DryRunTranslation: ...


_FORBIDDEN_FIXTURE_KEYS = {
    "account",
    "account_id",
    "account_no",
    "account_number",
    "broker_native_order",
    "cert",
    "cert_path",
    "env",
    "order_id",
    "order_no",
    "password",
    "private_symbol_list",
    "raw",
    "raw_response",
    "raw_vendor_payload",
    "secret",
    "session",
    "token",
    "vendor_payload",
}
_ALLOWED_BROKERS = {"mock-fixture"}


def validate_fail_closed_args(
    *, broker_id: str, mode: str, no_place_orders: bool, mock_transport: str
) -> None:
    if not no_place_orders:
        raise BrokerDryRunError("--no-place-orders is required", reason="missing-no-place-orders")
    if mode != "dry-run":
        raise BrokerDryRunError("--mode must be dry-run for Stage 4a", reason="non-dry-run-mode")
    if mock_transport != "fixture":
        raise BrokerDryRunError(
            "--mock-transport must be fixture for Stage 4a", reason="unsupported-transport"
        )
    if broker_id not in _ALLOWED_BROKERS:
        raise BrokerDryRunError("broker must be mock-fixture for Stage 4a", reason="unsupported-broker")


@dataclass(frozen=True)
class FixtureMockTransport:
    fixtures_path: Path
    transport_id: str = "mock-fixture"
    no_network: Literal[True] = True

    def preflight(self) -> MockTransportHealth:
        return {
            "transport_id": self.transport_id,
            "transport_kind": "mock",
            "connectivity": "mock-verified",
            "no_network": True,
            "credential_inspection": "not-performed",
            "account_inspection": "not-performed",
        }

    def load_requests(self) -> list[ExecutionRequest]:
        fixture_file = self.fixtures_path / "requests.json"
        payload = json.loads(fixture_file.read_text(encoding="utf-8"))
        _reject_forbidden_fixture_payload(payload)
        cases = payload.get("requests") if isinstance(payload, dict) else None
        if not isinstance(cases, list) or not cases:
            raise BrokerDryRunError("fixture must contain a non-empty requests list", reason="bad-fixture")
        return [_normalize_request(case) for case in cases]

    def translate_order(self, request: ExecutionRequest) -> DryRunTranslation:
        return {
            "case_id": request["case_id"],
            "request_id": f"dry-run:{request['case_id']}",
            "symbol_ref": request["symbol_ref"],
            "side": request["side"],
            "quantity": request["quantity"],
            "order_type": request["order_type"],
            "time_in_force": request["time_in_force"],
            "dry_run_operation": "submit_preview",
            "broker_native_order": None,
            "dispatch_suppressed": True,
        }


def _reject_forbidden_fixture_payload(value: object, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in _FORBIDDEN_FIXTURE_KEYS or lowered.startswith("raw_"):
                raise BrokerDryRunError(
                    f"fixture contains forbidden broker/private field at {path}.{key}",
                    reason="forbidden-fixture-field",
                )
            _reject_forbidden_fixture_payload(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden_fixture_payload(child, path=f"{path}[{index}]")


def _normalize_request(value: object) -> ExecutionRequest:
    if not isinstance(value, dict):
        raise BrokerDryRunError("each fixture request must be an object", reason="bad-fixture")
    required = ("case_id", "symbol_ref", "side", "quantity", "order_type", "time_in_force")
    missing = [key for key in required if key not in value]
    if missing:
        raise BrokerDryRunError(f"fixture request missing fields: {', '.join(missing)}", reason="bad-fixture")
    side = str(value["side"])
    order_type = str(value["order_type"])
    time_in_force = str(value["time_in_force"])
    quantity = value["quantity"]
    if side not in {"buy", "sell"}:
        raise BrokerDryRunError("fixture side must be buy or sell", reason="bad-fixture")
    if order_type not in {"market", "limit"}:
        raise BrokerDryRunError("fixture order_type must be market or limit", reason="bad-fixture")
    if time_in_force not in {"day"}:
        raise BrokerDryRunError("fixture time_in_force must be day", reason="bad-fixture")
    if not isinstance(quantity, int) or quantity <= 0:
        raise BrokerDryRunError("fixture quantity must be a positive integer", reason="bad-fixture")
    symbol_ref = str(value["symbol_ref"])
    if not (symbol_ref.startswith("<") and symbol_ref.endswith(">")):
        raise BrokerDryRunError("fixture symbol_ref must be an opaque public ref", reason="bad-fixture")
    return {
        "case_id": str(value["case_id"]),
        "symbol_ref": symbol_ref,
        "side": side,
        "quantity": quantity,
        "order_type": order_type,
        "time_in_force": time_in_force,
    }
