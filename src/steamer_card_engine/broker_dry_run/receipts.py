from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
from typing import Any

from .translator import build_translation_payload
from .transport import FixtureMockTransport, validate_fail_closed_args

_FORBIDDEN_RECEIPT_TERMS = (
    "token",
    "password",
    "api_key",
    "secret",
    "cert",
    "raw_response",
    "raw_vendor_payload",
)


def build_preflight_receipt(
    *,
    broker_id: str,
    mode: str,
    no_place_orders: bool,
    mock_transport: str,
    fixtures_path: Path,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    validate_fail_closed_args(
        broker_id=broker_id,
        mode=mode,
        no_place_orders=no_place_orders,
        mock_transport=mock_transport,
    )
    transport = FixtureMockTransport(fixtures_path=fixtures_path)
    health = transport.preflight()
    requests = transport.load_requests()
    translation = build_translation_payload(transport=transport, requests=requests)
    payload: dict[str, Any] = {
        "schema_version": "broker-dry-run-preflight/v1",
        "broker": {"id": broker_id, "vendor": "mock", "version": "v0"},
        "mode": mode,
        "transport": {"kind": "mock", "id": health["transport_id"], "no_network": True},
        "transport_health": health,
        "translation": translation,
        "order_placement": {
            "enabled": False,
            "guard": "no-place-orders",
            "guard_required": True,
            "guard_present": True,
            "place_order_call_count": 0,
            "broker_native_order_count": 0,
        },
        "redaction": _redaction_report_for_payload(translation),
        "credential_inspection": "not-performed",
        "account_inspection": "not-performed",
        "live_readiness_claim": False,
        "no_network": True,
        "topology_changed": False,
    }
    payload["redaction"] = _redaction_report_for_payload(payload)
    if receipt_path is not None:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def redact_check_receipt(*, receipt_path: Path) -> dict[str, Any]:
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    redaction = _redaction_report_for_payload(payload)
    return {
        "schema_version": "broker-dry-run-redact-check/v1",
        "receipt": str(receipt_path),
        "status": redaction["status"],
        "checked_term_count": redaction["checked_term_count"],
        "raw_vendor_payload_present": redaction["raw_vendor_payload_present"],
        "matches": redaction["matches"],
    }


def _redaction_report_for_payload(payload: Any) -> dict[str, Any]:
    leaf_text = "\n".join(_leaf_strings(payload)).lower()
    matches = [term for term in _FORBIDDEN_RECEIPT_TERMS if term in leaf_text]
    return {
        "status": "pass" if not matches else "fail",
        "checked_term_count": len(_FORBIDDEN_RECEIPT_TERMS),
        "raw_vendor_payload_present": any(
            term in leaf_text for term in ("raw_response", "raw_vendor_payload")
        ),
        "matches": matches,
    }


def _leaf_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [leaf for child in value.values() for leaf in _leaf_strings(child)]
    if isinstance(value, list):
        return [leaf for child in value for leaf in _leaf_strings(child)]
    if isinstance(value, str):
        return [value]
    return []


def forbidden_receipt_terms() -> Iterable[str]:
    return _FORBIDDEN_RECEIPT_TERMS
