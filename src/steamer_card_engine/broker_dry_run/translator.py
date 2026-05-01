from __future__ import annotations

from .transport import DryRunTranslation, ExecutionRequest, MockBrokerDryRunTransport


def build_translation_payload(
    *, transport: MockBrokerDryRunTransport, requests: list[ExecutionRequest]
) -> dict:
    translations: list[DryRunTranslation] = [transport.translate_order(request) for request in requests]
    return {
        "schema_version": "broker-dry-run-translation/v1",
        "input_kind": "normalized_execution_request",
        "cases_checked": len(translations),
        "translations": translations,
    }
