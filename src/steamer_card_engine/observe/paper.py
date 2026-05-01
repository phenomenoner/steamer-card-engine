from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from steamer_card_engine.paper import audit_paper_ledger, run_paper_replay
from steamer_card_engine.paper.receipts import stable_hash, with_receipt_hash

OBSERVE_PAPER_SCHEMA_VERSION = "observe-paper-run/v1"
FIXTURE_MARKET_SOURCE = "fixture-live-shape"
FIXED_NOW_SECONDS = 60
_FORBIDDEN_FIXTURE_KEYS = {
    "broker_native_order",
    "account_id",
    "account_no",
    "account_number",
    "raw_response",
    "raw_vendor_payload",
    "vendor_payload",
    "api_key",
    "password",
    "token",
    "secret",
    "cert",
}


@dataclass(frozen=True, slots=True)
class ObservePaperError(Exception):
    payload: dict[str, Any]
    exit_code: int = 4

    def __str__(self) -> str:
        return str(self.payload.get("stable_reason") or self.payload.get("reason_code") or "observe-paper failed")


def _reject_payload(*, reason_code: str, stable_reason: str, market_source: str = "unknown") -> dict[str, Any]:
    return {
        "schema_version": OBSERVE_PAPER_SCHEMA_VERSION,
        "mode": "observe-paper",
        "stage": "5a-fixture-live-shape",
        "decision": "fail",
        "reason_code": reason_code,
        "stable_reason": stable_reason,
        "market_source": {
            "kind": market_source,
            "provider": "fixture" if market_source == FIXTURE_MARKET_SOURCE else "unsupported",
            "no_network": True,
            "credential_inspection": "not-performed",
        },
        "execution": {
            "backend": "paper-ledger-only",
            "ledger_schema_version": "paper-ledger/v1",
            "broker_native_order_count": 0,
            "place_order_call_count": 0,
        },
        "freshness": {
            "decision": "fail",
            "max_staleness_seconds": None,
            "stale_events": 0,
            "outage_detected": False,
            "fail_closed": True,
            "failures": [{"code": reason_code, "detail": stable_reason}],
        },
        "risk": {"profile": "unknown", "decision": "fail", "paper_risk_checked": False},
        "summary": {
            "market_events_seen": 0,
            "signals_seen": 0,
            "paper_orders_accepted": 0,
            "paper_orders_rejected": 0,
            "fills": 0,
        },
        "execution_backend": "paper-ledger-only",
        "live_order_route_present": False,
        "broker_order_placement_enabled": False,
        "stage6_live_canary_authority": False,
        "no_network": True,
        "topology_changed": False,
        "live_readiness_claim": False,
    }


def _load_fixture(fixtures_path: Path) -> dict[str, Any]:
    fixture_file = fixtures_path / "events.json" if fixtures_path.is_dir() else fixtures_path
    payload = json.loads(fixture_file.read_text(encoding="utf-8"))
    _reject_forbidden_fixture_payload(payload)
    return payload


def _reject_forbidden_fixture_payload(value: object, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in _FORBIDDEN_FIXTURE_KEYS or lowered.startswith("raw_"):
                raise ObservePaperError(
                    _reject_payload(
                        reason_code="forbidden-fixture-field",
                        stable_reason=f"fixture contains forbidden broker/private field at {path}.{key}",
                        market_source=FIXTURE_MARKET_SOURCE,
                    )
                )
            _reject_forbidden_fixture_payload(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden_fixture_payload(child, path=f"{path}[{index}]")


def _validate_events(payload: dict[str, Any], *, stale_market_data_seconds: int) -> tuple[list[dict[str, Any]], list[dict[str, str]], bool]:
    events = payload.get("events")
    if not isinstance(events, list) or not events:
        return [], [{"code": "market_data_outage", "detail": "no fixture market events available"}], True
    failures: list[dict[str, str]] = []
    normalized: list[dict[str, Any]] = []
    outage = False
    previous_sequence = -1
    stale_events = 0
    for event in events:
        if not isinstance(event, dict):
            failures.append({"code": "bad_market_event", "detail": "event is not an object"})
            continue
        sequence = int(event.get("sequence", -1))
        if sequence <= previous_sequence:
            failures.append({"code": "market_sequence_regressed", "detail": str(sequence)})
        previous_sequence = sequence
        status = str(event.get("status", "ok"))
        if status in {"stale", "degraded", "outage"}:
            outage = outage or status == "outage"
            failures.append({"code": f"market_data_{status}", "detail": str(event.get("case_id", sequence))})
        age_seconds = int(event.get("age_seconds", 0))
        if age_seconds > stale_market_data_seconds:
            stale_events += 1
            failures.append({"code": "market_data_stale", "detail": f"age_seconds={age_seconds}"})
        normalized.append(event)
    if stale_events:
        outage = outage or False
    return normalized, failures, outage


def _adapter_contract_fixtures(fixtures_path: Path, payload: dict[str, Any]) -> Path:
    raw = payload.get("adapter_contract_fixtures", "../adapter_contract")
    base = fixtures_path if fixtures_path.is_dir() else fixtures_path.parent
    return (base / str(raw)).resolve()


def _base_payload(
    *,
    fixture_payload: dict[str, Any],
    market_source: str,
    execution: str,
    ledger_path: Path,
    risk_profile: str,
    stale_market_data_seconds: int,
    failures: list[dict[str, str]],
    outage_detected: bool,
    market_events_seen: int,
    signals_seen: int,
) -> dict[str, Any]:
    return {
        "schema_version": OBSERVE_PAPER_SCHEMA_VERSION,
        "mode": "observe-paper",
        "stage": "5a-fixture-live-shape",
        "market_source": {
            "kind": market_source,
            "provider": "fixture",
            "no_network": True,
            "credential_inspection": "not-performed",
            "fixture_hash": stable_hash(fixture_payload),
        },
        "execution": {
            "backend": "paper-ledger-only",
            "ledger_schema_version": "paper-ledger/v1",
            "ledger": {"path": str(ledger_path), "backend": "sqlite"},
            "broker_native_order_count": 0,
            "place_order_call_count": 0,
        },
        "freshness": {
            "decision": "fail" if failures else "pass",
            "max_staleness_seconds": stale_market_data_seconds,
            "stale_events": sum(1 for failure in failures if failure["code"] == "market_data_stale"),
            "outage_detected": outage_detected,
            "fail_closed": True,
            "failures": failures,
        },
        "risk": {
            "profile": risk_profile,
            "decision": "fail" if failures else "pass",
            "paper_risk_checked": not failures,
        },
        "summary": {
            "market_events_seen": market_events_seen,
            "signals_seen": signals_seen,
            "paper_orders_accepted": 0,
            "paper_orders_rejected": 0,
            "fills": 0,
        },
        "execution_backend": "paper-ledger-only",
        "live_order_route_present": False,
        "broker_order_placement_enabled": False,
        "stage6_live_canary_authority": False,
        "no_network": True,
        "topology_changed": False,
        "live_readiness_claim": False,
    }


def run_observe_paper(
    *,
    adapter_id: str,
    market_source: str,
    fixtures_path: Path,
    execution: str,
    ledger_path: Path,
    risk_profile: str,
    duration_seconds: int,
    stale_market_data_seconds: int,
    receipt_path: Path | None,
) -> tuple[dict[str, Any], int]:
    if market_source != FIXTURE_MARKET_SOURCE:
        payload = _reject_payload(
            reason_code="unsupported-market-source",
            stable_reason="Stage 5a only permits fixture-live-shape market source",
            market_source=market_source,
        )
        raise ObservePaperError(payload)
    if execution != "paper":
        payload = _reject_payload(
            reason_code="unsupported-execution",
            stable_reason="Stage 5a observe-paper requires --execution paper",
            market_source=market_source,
        )
        raise ObservePaperError(payload)
    if adapter_id != "fixture-paper-only":
        payload = _reject_payload(
            reason_code="unsupported-adapter",
            stable_reason="Stage 5a only permits fixture-paper-only adapter",
            market_source=market_source,
        )
        raise ObservePaperError(payload)

    fixture_payload = _load_fixture(fixtures_path)
    events, failures, outage_detected = _validate_events(
        fixture_payload,
        stale_market_data_seconds=stale_market_data_seconds,
    )
    signals_seen = sum(1 for event in events if event.get("signal", {}).get("action") in {"enter", "exit", "hold"} if isinstance(event.get("signal"), dict))
    payload = _base_payload(
        fixture_payload=fixture_payload,
        market_source=market_source,
        execution=execution,
        ledger_path=ledger_path,
        risk_profile=risk_profile,
        stale_market_data_seconds=stale_market_data_seconds,
        failures=failures,
        outage_detected=outage_detected,
        market_events_seen=len(events),
        signals_seen=signals_seen,
    )
    payload["duration_seconds"] = duration_seconds

    if failures:
        payload = with_receipt_hash(payload)
        if receipt_path is not None:
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return payload, 4

    adapter_fixtures = _adapter_contract_fixtures(fixtures_path, fixture_payload)
    paper_receipt, paper_exit = run_paper_replay(
        adapter_id=adapter_id,
        fixtures_path=adapter_fixtures,
        ledger_path=ledger_path,
        receipt_path=None,
        max_position=1,
        max_loss_placeholder=0,
        stale_signal_seconds=stale_market_data_seconds,
    )
    audit_payload, audit_exit = audit_paper_ledger(ledger_path=ledger_path)
    payload["paper_run"] = {
        "schema_version": paper_receipt.get("schema_version"),
        "decision": paper_receipt.get("risk", {}).get("decision") if isinstance(paper_receipt.get("risk"), dict) else "unknown",
        "summary": paper_receipt.get("summary"),
    }
    payload["paper_audit"] = {
        "schema_version": audit_payload.get("schema_version"),
        "decision": audit_payload.get("decision"),
        "counts": audit_payload.get("counts"),
    }
    payload["summary"]["paper_orders_accepted"] = int((paper_receipt.get("summary") or {}).get("orders_accepted", 0)) if isinstance(paper_receipt.get("summary"), dict) else 0
    payload["summary"]["paper_orders_rejected"] = int((paper_receipt.get("summary") or {}).get("orders_rejected", 0)) if isinstance(paper_receipt.get("summary"), dict) else 0
    payload["summary"]["fills"] = int((paper_receipt.get("summary") or {}).get("fills", 0)) if isinstance(paper_receipt.get("summary"), dict) else 0
    if paper_exit != 0 or audit_exit != 0:
        payload["risk"]["decision"] = "fail"
        payload["freshness"]["decision"] = "fail"
        payload["freshness"]["failures"].append({"code": "paper_backend_failed", "detail": "paper run or audit failed"})
        exit_code = 4
    else:
        exit_code = 0
    payload = with_receipt_hash(payload)
    if receipt_path is not None:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload, exit_code
