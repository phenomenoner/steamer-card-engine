from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from steamer_card_engine.adapters.base import sanitize_public_ref, sanitize_public_text


ControlPlaneAction = Literal["read"]
ToolCallStatus = Literal["ok", "rejected"]

_SCHEMA_VERSION = "control-plane-tool-registry/v1"
_RECEIPT_SCHEMA_VERSION = "control-plane-tool-receipt/v1"
_LATEST_EVIDENCE_REPORT_ID = "latest_evidence_report"
_FIXED_FIXTURE_TS = "2026-04-24T00:00:00Z"

_MUTATING_ACTIONS = {
    "write",
    "mutate",
    "delete",
    "patch",
    "execute",
    "run",
    "launch",
    "start",
    "stop",
    "submit",
    "cancel",
    "replace",
    "trade",
    "order",
    "arm",
    "disarm",
    "flatten",
}


@dataclass(frozen=True, slots=True)
class ControlPlaneToolSpec:
    """Remote-safe contract metadata for one control-plane inspection tool."""

    tool_id: str
    description: str
    read_only: bool
    allowed_action: ControlPlaneAction
    input_contract: dict[str, str] = field(default_factory=dict)
    output_contract: dict[str, str] = field(default_factory=dict)
    receipt_required: bool = True

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "tool_id": sanitize_public_ref(self.tool_id),
            "description": sanitize_public_text(self.description),
            "read_only": self.read_only,
            "allowed_action": self.allowed_action,
            "input_contract": {
                sanitize_public_ref(key) or "field": sanitize_public_text(value)
                for key, value in self.input_contract.items()
            },
            "output_contract": {
                sanitize_public_ref(key) or "field": sanitize_public_text(value)
                for key, value in self.output_contract.items()
            },
            "receipt_required": self.receipt_required,
        }


@dataclass(frozen=True, slots=True)
class ControlPlaneToolRequest:
    tool_id: str
    action: str = "read"
    inputs: dict[str, Any] = field(default_factory=dict)
    request_id: str = "control-plane-fixture-request"


@dataclass(frozen=True, slots=True)
class ControlPlaneToolReceipt:
    receipt_id: str
    tool_id: str
    action: str
    status: ToolCallStatus
    reason: str
    public_safe: bool = True
    generated_at: str = _FIXED_FIXTURE_TS

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": _RECEIPT_SCHEMA_VERSION,
            "receipt_id": sanitize_public_ref(self.receipt_id),
            "tool_id": sanitize_public_ref(self.tool_id),
            "action": sanitize_public_ref(self.action),
            "status": self.status,
            "reason": sanitize_public_text(self.reason),
            "public_safe": self.public_safe,
            "raw_data_included": False,
            "credentials_included": False,
            "account_data_included": False,
            "strategy_params_included": False,
            "generated_at": self.generated_at,
        }


@dataclass(frozen=True, slots=True)
class ControlPlaneToolResult:
    status: ToolCallStatus
    tool_id: str
    action: str
    output: dict[str, Any]
    receipt: ControlPlaneToolReceipt
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "status": self.status,
            "tool_id": sanitize_public_ref(self.tool_id),
            "action": sanitize_public_ref(self.action),
            "output": self.output,
            "receipt": self.receipt.to_public_dict(),
            "error": sanitize_public_text(self.error),
        }


class ReadOnlyControlPlaneToolRegistry:
    """Fail-closed registry for read-only, public-safe inspection helpers.

    This class is intentionally not a generic execution surface. It only accepts
    registered read-only tools, rejects unknown ids and mutating actions, and
    returns a public-safe receipt for every call.
    """

    def __init__(self, tools: dict[str, ControlPlaneToolSpec] | None = None) -> None:
        self._tools = tools or {_LATEST_EVIDENCE_REPORT_ID: latest_evidence_report_spec()}
        for tool_id, spec in self._tools.items():
            if tool_id != spec.tool_id:
                raise ValueError("tool registry key must match tool_id")
            if not spec.read_only or spec.allowed_action != "read" or not spec.receipt_required:
                raise ValueError("control-plane registry only accepts read-only tools with receipts")

    def list_tools(self) -> tuple[ControlPlaneToolSpec, ...]:
        return tuple(self._tools.values())

    def invoke(self, request: ControlPlaneToolRequest) -> ControlPlaneToolResult:
        tool_id = sanitize_public_ref(request.tool_id) or "unknown"
        action = sanitize_public_ref(request.action) or "unknown"
        receipt_id = _receipt_id(tool_id=tool_id, action=action, request_id=request.request_id)

        spec = self._tools.get(request.tool_id)
        if spec is None:
            return _rejected_result(
                tool_id=tool_id,
                action=action,
                receipt_id=receipt_id,
                reason="unknown control-plane tool id failed closed",
            )

        if request.action != spec.allowed_action or request.action in _MUTATING_ACTIONS:
            return _rejected_result(
                tool_id=tool_id,
                action=action,
                receipt_id=receipt_id,
                reason="control-plane tool request rejected because only read action is allowed",
            )

        if not spec.read_only:
            return _rejected_result(
                tool_id=tool_id,
                action=action,
                receipt_id=receipt_id,
                reason="control-plane tool request rejected because tool is not read-only",
            )

        if request.tool_id == _LATEST_EVIDENCE_REPORT_ID:
            return _latest_evidence_report_result(spec=spec, request=request, receipt_id=receipt_id)

        return _rejected_result(
            tool_id=tool_id,
            action=action,
            receipt_id=receipt_id,
            reason="registered control-plane tool has no handler and failed closed",
        )


def latest_evidence_report_spec() -> ControlPlaneToolSpec:
    return ControlPlaneToolSpec(
        tool_id=_LATEST_EVIDENCE_REPORT_ID,
        description="Return a sanitized pointer to the latest aggregate evidence report fixture.",
        read_only=True,
        allowed_action="read",
        input_contract={
            "scope": "Optional sanitized selector. The deterministic fixture accepts latest only.",
        },
        output_contract={
            "pointer": "Opaque local/report pointer only; no raw evidence bundle content.",
            "receipt": "Public-safe receipt proving the read-only inspection boundary.",
        },
        receipt_required=True,
    )


def default_read_only_registry() -> ReadOnlyControlPlaneToolRegistry:
    return ReadOnlyControlPlaneToolRegistry()


def latest_evidence_report() -> ControlPlaneToolResult:
    return default_read_only_registry().invoke(
        ControlPlaneToolRequest(tool_id=_LATEST_EVIDENCE_REPORT_ID, action="read")
    )


def _latest_evidence_report_result(
    *, spec: ControlPlaneToolSpec, request: ControlPlaneToolRequest, receipt_id: str
) -> ControlPlaneToolResult:
    receipt = ControlPlaneToolReceipt(
        receipt_id=receipt_id,
        tool_id=spec.tool_id,
        action=request.action,
        status="ok",
        reason="sanitized latest evidence report pointer returned",
    )
    output = {
        "report": {
            "pointer": "docs/receipts/artifacts/latest-evidence-report.fixture.json",
            "pointer_kind": "sanitized-local-pointer",
            "evidence_date": "2026-04-24",
            "summary": "aggregate-only latest evidence report fixture",
            "contains_raw_evidence": False,
            "contains_raw_symbols": False,
            "contains_strategy_params": False,
            "contains_credentials": False,
            "contains_account_data": False,
        },
        "receipt_id": receipt.receipt_id,
        "receipt_required": True,
    }
    return ControlPlaneToolResult(
        status="ok",
        tool_id=spec.tool_id,
        action=request.action,
        output=output,
        receipt=receipt,
    )


def _rejected_result(*, tool_id: str, action: str, receipt_id: str, reason: str) -> ControlPlaneToolResult:
    receipt = ControlPlaneToolReceipt(
        receipt_id=receipt_id,
        tool_id=tool_id,
        action=action,
        status="rejected",
        reason=reason,
    )
    return ControlPlaneToolResult(
        status="rejected",
        tool_id=tool_id,
        action=action,
        output={"allowed": False},
        receipt=receipt,
        error=reason,
    )


def _receipt_id(*, tool_id: str, action: str, request_id: str) -> str:
    safe_tool = sanitize_public_ref(tool_id) or "unknown"
    safe_action = sanitize_public_ref(action) or "unknown"
    safe_request = sanitize_public_ref(request_id) or "request"
    return f"control-plane:{safe_tool}:{safe_action}:{safe_request}"
