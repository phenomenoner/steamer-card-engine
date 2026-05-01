from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from steamer_card_engine.paper import PaperRunError, audit_paper_ledger, run_paper_replay

FIXTURES = Path("examples/probes/adapter_contract")


def _run(tmp_path: Path, **overrides):
    kwargs = {
        "adapter_id": "fixture-paper-only",
        "fixtures_path": FIXTURES,
        "ledger_path": tmp_path / "ledger.sqlite",
        "receipt_path": tmp_path / "paper.receipt.json",
        "max_position": 1,
        "max_loss_placeholder": 0,
        "stale_signal_seconds": 300,
    }
    kwargs.update(overrides)
    return run_paper_replay(**kwargs)


def test_paper_run_creates_ledger_receipt_and_audit_passes(tmp_path: Path) -> None:
    receipt, exit_code = _run(tmp_path)

    assert exit_code == 0
    assert (tmp_path / "ledger.sqlite").exists()
    assert (tmp_path / "paper.receipt.json").exists()
    assert receipt["schema_version"] == "paper-run/v1"
    assert receipt["summary"]["orders_accepted"] == 1
    assert receipt["summary"]["fills"] == 1
    assert receipt["summary"]["broker_native_order_count"] == 0
    assert receipt["no_network"] is True
    assert receipt["topology_changed"] is False
    assert receipt["live_readiness_claim"] is False
    audit, audit_code = audit_paper_ledger(ledger_path=tmp_path / "ledger.sqlite")
    assert audit_code == 0
    assert audit["decision"] == "pass"
    assert audit["counts"]["fills"] == 1


def test_duplicate_rerun_fails_closed_without_mutating_existing_ledger(tmp_path: Path) -> None:
    receipt, exit_code = _run(tmp_path)
    assert exit_code == 0
    audit_before, _ = audit_paper_ledger(ledger_path=tmp_path / "ledger.sqlite")

    duplicate_receipt, duplicate_code = _run(tmp_path)

    assert duplicate_code == 4
    assert duplicate_receipt["risk"]["decision"] == "fail"
    assert duplicate_receipt["risk"]["failures"][0]["code"] == "duplicate_order"
    audit_after, _ = audit_paper_ledger(ledger_path=tmp_path / "ledger.sqlite")
    assert audit_after == audit_before


def test_max_position_violation_rejects_without_ledger_mutation(tmp_path: Path) -> None:
    receipt, exit_code = _run(tmp_path, max_position=0)

    assert exit_code == 4
    assert receipt["risk"]["decision"] == "fail"
    assert receipt["risk"]["failures"][0]["code"] == "max_position_exceeded"
    audit, audit_code = audit_paper_ledger(ledger_path=tmp_path / "ledger.sqlite")
    assert audit_code == 0
    assert audit["counts"]["orders"] == 0
    assert audit["counts"]["fills"] == 0


def test_unknown_adapter_fails_before_ledger_mutation(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.sqlite"
    with pytest.raises(PaperRunError) as error:
        _run(tmp_path, adapter_id="unknown-fixture", ledger_path=ledger_path)

    assert error.value.exit_code == 4
    assert error.value.payload["reason_code"] == "unknown_adapter"
    assert not ledger_path.exists()


def test_audit_detects_corrupted_missing_fill_linkage(tmp_path: Path) -> None:
    _, exit_code = _run(tmp_path)
    assert exit_code == 0
    conn = sqlite3.connect(tmp_path / "ledger.sqlite")
    try:
        conn.execute("DELETE FROM paper_fills")
        conn.commit()
    finally:
        conn.close()

    audit, audit_code = audit_paper_ledger(ledger_path=tmp_path / "ledger.sqlite")

    assert audit_code == 4
    assert audit["decision"] == "fail"
    assert {failure["code"] for failure in audit["invariant_failures"]} >= {
        "filled_order_missing_fill",
        "position_without_fills",
    }


def test_receipts_do_not_expose_secret_or_raw_vendor_payload_strings(tmp_path: Path) -> None:
    receipt, exit_code = _run(tmp_path)

    assert exit_code == 0
    serialized = json.dumps(receipt, sort_keys=True)
    forbidden = ["super-secret-token", "raw_response", "token", "vendor says live trading disabled", "Neo", "Fubon"]
    for text in forbidden:
        assert text not in serialized
