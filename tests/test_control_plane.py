from __future__ import annotations

import json

import pytest

from steamer_card_engine.control_plane import (
    ControlPlaneToolRequest,
    ControlPlaneToolSpec,
    ReadOnlyControlPlaneToolRegistry,
    default_read_only_registry,
    latest_evidence_report,
)


PRIVATE_MARKERS = (
    "api_key",
    "password",
    "secret",
    "token",
    "broker_order",
    "account_number",
    "raw_ticks_payload",
    "raw_strategy_params",
    "private_key",
)


def test_registered_tools_are_read_only_and_receipted() -> None:
    registry = default_read_only_registry()

    specs = registry.list_tools()

    assert [spec.tool_id for spec in specs] == ["latest_evidence_report"]
    for spec in specs:
        assert spec.read_only is True
        assert spec.allowed_action == "read"
        assert spec.receipt_required is True
        public_spec = spec.to_public_dict()
        assert public_spec["read_only"] is True
        assert public_spec["allowed_action"] == "read"


def test_latest_evidence_report_returns_sanitized_pointer_and_receipt() -> None:
    result = latest_evidence_report()

    assert result.ok is True
    payload = result.to_public_dict()
    report = payload["output"]["report"]
    receipt = payload["receipt"]

    assert report["pointer"] == "docs/receipts/artifacts/latest-evidence-report.fixture.json"
    assert report["contains_raw_evidence"] is False
    assert report["contains_raw_symbols"] is False
    assert report["contains_strategy_params"] is False
    assert report["contains_credentials"] is False
    assert receipt["status"] == "ok"
    assert receipt["public_safe"] is True
    assert receipt["raw_data_included"] is False
    assert receipt["credentials_included"] is False
    assert receipt["account_data_included"] is False
    assert receipt["strategy_params_included"] is False


def test_unknown_tool_id_fails_closed_with_public_safe_receipt() -> None:
    result = default_read_only_registry().invoke(
        ControlPlaneToolRequest(tool_id="unknown_private_tool", action="read", request_id="req-unknown")
    )

    assert result.ok is False
    assert result.status == "rejected"
    assert result.output == {"allowed": False}
    assert "unknown control-plane tool id failed closed" == result.error
    receipt = result.to_public_dict()["receipt"]
    assert receipt["status"] == "rejected"
    assert receipt["public_safe"] is True
    assert receipt["raw_data_included"] is False


@pytest.mark.parametrize("action", ["write", "mutate", "delete", "execute", "launch", "submit"])
def test_mutating_or_non_read_actions_are_rejected(action: str) -> None:
    result = default_read_only_registry().invoke(
        ControlPlaneToolRequest(tool_id="latest_evidence_report", action=action, request_id="req-mutating")
    )

    assert result.ok is False
    assert result.status == "rejected"
    assert result.output == {"allowed": False}
    assert result.receipt.status == "rejected"
    assert "only read action is allowed" in (result.error or "")


def test_registry_rejects_non_read_only_tool_specs() -> None:
    with pytest.raises(ValueError, match="only accepts read-only tools"):
        ReadOnlyControlPlaneToolRegistry(
            tools={
                "unsafe": ControlPlaneToolSpec(
                    tool_id="unsafe",
                    description="unsafe mutating fixture",
                    read_only=False,
                    allowed_action="read",
                    receipt_required=True,
                )
            }
        )


def test_public_receipts_do_not_expose_private_markers() -> None:
    registry = default_read_only_registry()
    results = [
        registry.invoke(ControlPlaneToolRequest(tool_id="latest_evidence_report", action="read")),
        registry.invoke(ControlPlaneToolRequest(tool_id="does_not_exist", action="read")),
        registry.invoke(ControlPlaneToolRequest(tool_id="latest_evidence_report", action="submit")),
    ]

    serialized = json.dumps([result.to_public_dict() for result in results], sort_keys=True).lower()

    for marker in PRIVATE_MARKERS:
        assert marker not in serialized
    assert "fixture.json" in serialized
    assert "receipt" in serialized
