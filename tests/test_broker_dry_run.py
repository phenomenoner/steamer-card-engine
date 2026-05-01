from __future__ import annotations

import json
from pathlib import Path

import pytest

from steamer_card_engine.broker_dry_run import (
    BrokerDryRunError,
    build_preflight_receipt,
    redact_check_receipt,
)
from steamer_card_engine.broker_dry_run.transport import FixtureMockTransport


def _fixture_dir(tmp_path: Path, payload: dict) -> Path:
    root = tmp_path / "fixtures"
    root.mkdir()
    (root / "requests.json").write_text(json.dumps(payload), encoding="utf-8")
    return root


def _valid_payload() -> dict:
    return {
        "schema_version": "broker-dry-run-fixture/v1",
        "requests": [
            {
                "case_id": "synthetic-buy-1",
                "symbol_ref": "<PUBLIC_SYMBOL_REF>",
                "side": "buy",
                "quantity": 1,
                "order_type": "market",
                "time_in_force": "day",
            }
        ],
    }


def test_happy_path_emits_mock_preflight_receipt(tmp_path: Path) -> None:
    fixture_dir = _fixture_dir(tmp_path, _valid_payload())
    receipt = tmp_path / "receipt.json"

    payload = build_preflight_receipt(
        broker_id="mock-fixture",
        mode="dry-run",
        no_place_orders=True,
        mock_transport="fixture",
        fixtures_path=fixture_dir,
        receipt_path=receipt,
    )

    assert payload["schema_version"] == "broker-dry-run-preflight/v1"
    assert payload["translation"]["schema_version"] == "broker-dry-run-translation/v1"
    assert payload["translation"]["cases_checked"] == 1
    assert payload["order_placement"] == {
        "enabled": False,
        "guard": "no-place-orders",
        "guard_required": True,
        "guard_present": True,
        "place_order_call_count": 0,
        "broker_native_order_count": 0,
    }
    assert payload["no_network"] is True
    assert payload["transport_health"]["no_network"] is True
    assert payload["live_readiness_claim"] is False
    assert payload["topology_changed"] is False
    assert receipt.exists()


def test_missing_no_place_orders_fails_before_fixture_read(tmp_path: Path) -> None:
    missing_fixture_dir = tmp_path / "missing-fixtures"

    with pytest.raises(BrokerDryRunError) as excinfo:
        build_preflight_receipt(
            broker_id="mock-fixture",
            mode="dry-run",
            no_place_orders=False,
            mock_transport="fixture",
            fixtures_path=missing_fixture_dir,
        )

    assert excinfo.value.reason == "missing-no-place-orders"


def test_live_mode_fails_closed_before_fixture_read(tmp_path: Path) -> None:
    with pytest.raises(BrokerDryRunError) as excinfo:
        build_preflight_receipt(
            broker_id="mock-fixture",
            mode="live",
            no_place_orders=True,
            mock_transport="fixture",
            fixtures_path=tmp_path / "missing-fixtures",
        )

    assert excinfo.value.reason == "non-dry-run-mode"


@pytest.mark.parametrize("broker_id", ["fubon", "fubon-neo", "unknown", "real-broker"])
def test_unknown_or_real_broker_fails_closed_before_fixture_read(
    tmp_path: Path, broker_id: str
) -> None:
    with pytest.raises(BrokerDryRunError) as excinfo:
        build_preflight_receipt(
            broker_id=broker_id,
            mode="dry-run",
            no_place_orders=True,
            mock_transport="fixture",
            fixtures_path=tmp_path / "missing-fixtures",
        )

    assert excinfo.value.reason == "unsupported-broker"


@pytest.mark.parametrize("forbidden_key", ["broker_native_order", "account_id", "raw_vendor_payload"])
def test_forbidden_fixture_native_account_or_raw_vendor_payload_fails(
    tmp_path: Path, forbidden_key: str
) -> None:
    payload = _valid_payload()
    payload["requests"][0][forbidden_key] = "blocked"
    fixture_dir = _fixture_dir(tmp_path, payload)

    with pytest.raises(BrokerDryRunError) as excinfo:
        build_preflight_receipt(
            broker_id="mock-fixture",
            mode="dry-run",
            no_place_orders=True,
            mock_transport="fixture",
            fixtures_path=fixture_dir,
        )

    assert excinfo.value.reason == "forbidden-fixture-field"


def test_secret_values_and_raw_vendor_terms_absent_from_full_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STEAMER_BROKER_TOKEN", "super-secret-token-value")
    fixture_dir = _fixture_dir(tmp_path, _valid_payload())

    payload = build_preflight_receipt(
        broker_id="mock-fixture",
        mode="dry-run",
        no_place_orders=True,
        mock_transport="fixture",
        fixtures_path=fixture_dir,
    )

    text = json.dumps(payload, sort_keys=True).lower()
    assert "super-secret-token-value" not in text
    assert "token-value" not in text
    assert "raw_response" not in text
    assert payload["redaction"]["status"] == "pass"


def test_transport_has_no_network_and_no_order_placement_methods(tmp_path: Path) -> None:
    transport = FixtureMockTransport(fixtures_path=tmp_path)

    assert transport.no_network is True
    assert transport.preflight()["connectivity"] == "mock-verified"
    for forbidden in ("submit", "place_order", "send_order", "login", "connect", "positions", "balances"):
        assert not hasattr(transport, forbidden)


def test_receipt_written_only_when_explicit_receipt_is_provided(tmp_path: Path) -> None:
    fixture_dir = _fixture_dir(tmp_path, _valid_payload())

    build_preflight_receipt(
        broker_id="mock-fixture",
        mode="dry-run",
        no_place_orders=True,
        mock_transport="fixture",
        fixtures_path=fixture_dir,
    )

    assert list(tmp_path.glob("*.json")) == []


def test_redact_check_passes_sample_receipt(tmp_path: Path) -> None:
    fixture_dir = _fixture_dir(tmp_path, _valid_payload())
    receipt = tmp_path / "receipt.json"
    build_preflight_receipt(
        broker_id="mock-fixture",
        mode="dry-run",
        no_place_orders=True,
        mock_transport="fixture",
        fixtures_path=fixture_dir,
        receipt_path=receipt,
    )

    result = redact_check_receipt(receipt_path=receipt)

    assert result["schema_version"] == "broker-dry-run-redact-check/v1"
    assert result["status"] == "pass"
    assert result["matches"] == []
