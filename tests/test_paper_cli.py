from __future__ import annotations

import json
from pathlib import Path

from steamer_card_engine.cli import main

FIXTURES = "examples/probes/adapter_contract"


def test_paper_run_cli_creates_receipt_and_audit_cli_passes(tmp_path: Path, capsys) -> None:
    ledger = tmp_path / "ledger.sqlite"
    receipt_path = tmp_path / "receipt.json"

    code = main(
        [
            "paper",
            "run",
            "--adapter",
            "fixture-paper-only",
            "--fixtures",
            FIXTURES,
            "--paper-ledger",
            str(ledger),
            "--receipt",
            str(receipt_path),
            "--max-position",
            "1",
            "--max-loss-placeholder",
            "0",
            "--stale-signal-seconds",
            "300",
            "--json",
        ]
    )
    run_payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert ledger.exists()
    assert receipt_path.exists()
    assert run_payload["cli_contract"]["command"] == "paper run"
    assert run_payload["risk"]["decision"] == "pass"

    audit_code = main(["paper", "audit", "--paper-ledger", str(ledger), "--json"])
    audit_payload = json.loads(capsys.readouterr().out)
    assert audit_code == 0
    assert audit_payload["cli_contract"]["command"] == "paper audit"
    assert audit_payload["decision"] == "pass"


def test_paper_cli_unknown_adapter_fails_before_ledger_mutation(tmp_path: Path, capsys) -> None:
    ledger = tmp_path / "ledger.sqlite"

    code = main(
        [
            "paper",
            "run",
            "--adapter",
            "unknown-fixture",
            "--fixtures",
            FIXTURES,
            "--paper-ledger",
            str(ledger),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 4
    assert payload["reason_code"] == "unknown_adapter"
    assert payload["cli_contract"]["exit_class"] == "operator-refused"
    assert not ledger.exists()
