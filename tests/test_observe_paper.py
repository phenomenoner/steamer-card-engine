from __future__ import annotations

import json
from pathlib import Path

import pytest

from steamer_card_engine.observe import ObservePaperError, run_observe_paper
from steamer_card_engine.paper import audit_paper_ledger

FIXTURES = Path("examples/probes/live_observe")


def _run(tmp_path: Path, **overrides):
    kwargs = {
        "adapter_id": "fixture-paper-only",
        "market_source": "fixture-live-shape",
        "fixtures_path": FIXTURES,
        "execution": "paper",
        "ledger_path": tmp_path / "ledger.sqlite",
        "risk_profile": "conservative",
        "duration_seconds": 60,
        "stale_market_data_seconds": 5,
        "receipt_path": tmp_path / "observe.receipt.json",
    }
    kwargs.update(overrides)
    return run_observe_paper(**kwargs)


def test_observe_paper_happy_path_writes_receipt_ledger_and_audit_passes(tmp_path: Path) -> None:
    receipt, exit_code = _run(tmp_path)

    assert exit_code == 0
    assert receipt["schema_version"] == "observe-paper-run/v1"
    assert receipt["stage"] == "5a-fixture-live-shape"
    assert receipt["market_source"]["kind"] == "fixture-live-shape"
    assert receipt["execution"]["backend"] == "paper-ledger-only"
    assert receipt["summary"]["market_events_seen"] == 1
    assert receipt["summary"]["paper_orders_accepted"] == 1
    assert receipt["summary"]["fills"] == 1
    assert receipt["live_order_route_present"] is False
    assert receipt["broker_order_placement_enabled"] is False
    assert receipt["stage6_live_canary_authority"] is False
    assert receipt["live_readiness_claim"] is False
    assert receipt["no_network"] is True
    assert receipt["topology_changed"] is False
    assert (tmp_path / "observe.receipt.json").exists()
    audit, audit_code = audit_paper_ledger(ledger_path=tmp_path / "ledger.sqlite")
    assert audit_code == 0
    assert audit["decision"] == "pass"


def test_stale_event_fails_closed_before_order_acceptance(tmp_path: Path) -> None:
    fixture = tmp_path / "events.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "observe-paper-fixture/v1",
                "adapter_contract_fixtures": str(Path.cwd() / "examples/probes/adapter_contract"),
                "events": [
                    {"case_id": "stale", "sequence": 1, "age_seconds": 99, "status": "ok", "signal": {"action": "enter"}}
                ],
            }
        )
    )

    receipt, exit_code = _run(tmp_path, fixtures_path=fixture)

    assert exit_code == 4
    assert receipt["freshness"]["decision"] == "fail"
    assert receipt["freshness"]["failures"][0]["code"] == "market_data_stale"
    assert receipt["summary"]["paper_orders_accepted"] == 0
    assert not (tmp_path / "ledger.sqlite").exists()


def test_outage_fixture_fails_closed(tmp_path: Path) -> None:
    fixture = tmp_path / "events.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "observe-paper-fixture/v1",
                "events": [{"case_id": "outage", "sequence": 1, "age_seconds": 0, "status": "outage"}],
            }
        )
    )

    receipt, exit_code = _run(tmp_path, fixtures_path=fixture)

    assert exit_code == 4
    assert receipt["freshness"]["outage_detected"] is True
    assert receipt["freshness"]["failures"][0]["code"] == "market_data_outage"


@pytest.mark.parametrize(
    ("overrides", "reason_code"),
    [
        ({"execution": "live"}, "unsupported-execution"),
        ({"market_source": "live"}, "unsupported-market-source"),
        ({"market_source": "unknown"}, "unsupported-market-source"),
    ],
)
def test_authority_boundary_failures_raise_before_ledger_mutation(tmp_path: Path, overrides: dict, reason_code: str) -> None:
    with pytest.raises(ObservePaperError) as error:
        _run(tmp_path, **overrides)

    assert error.value.payload["reason_code"] == reason_code
    assert not (tmp_path / "ledger.sqlite").exists()


def test_forbidden_broker_native_payload_fails(tmp_path: Path) -> None:
    fixture = tmp_path / "events.json"
    fixture.write_text(json.dumps({"events": [{"sequence": 1, "broker_native_order": {"id": "x"}}]}))

    with pytest.raises(ObservePaperError) as error:
        _run(tmp_path, fixtures_path=fixture)

    assert error.value.payload["reason_code"] == "forbidden-fixture-field"


def test_observe_receipt_does_not_expose_secret_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STEAMER_SUPER_SECRET", "super-secret-token")

    receipt, exit_code = _run(tmp_path)

    assert exit_code == 0
    serialized = json.dumps(receipt, sort_keys=True)
    for forbidden in ("super-secret-token", "api_key", "password", "raw_response", "/workspace/steamer"):
        assert forbidden not in serialized
