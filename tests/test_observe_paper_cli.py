from __future__ import annotations

import json
from pathlib import Path

from steamer_card_engine.cli import main
from steamer_card_engine.paper import audit_paper_ledger


def test_observe_paper_cli_happy_path(capsys, tmp_path: Path) -> None:
    receipt = tmp_path / "observe.receipt.json"
    ledger = tmp_path / "ledger.sqlite"

    code = main(
        [
            "observe",
            "paper",
            "--adapter",
            "fixture-paper-only",
            "--market-source",
            "fixture-live-shape",
            "--fixtures",
            "examples/probes/live_observe",
            "--execution",
            "paper",
            "--paper-ledger",
            str(ledger),
            "--risk-profile",
            "conservative",
            "--duration-seconds",
            "60",
            "--stale-market-data-seconds",
            "5",
            "--receipt",
            str(receipt),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["cli_contract"] == {
        "version": "cli-command/v1",
        "command": "observe paper",
        "exit_code": 0,
        "exit_class": "success",
        "status_key": "risk.decision",
        "status": "pass",
    }
    assert payload["schema_version"] == "observe-paper-run/v1"
    assert payload["execution"]["backend"] == "paper-ledger-only"
    assert payload["summary"]["fills"] == 1
    assert payload["live_readiness_claim"] is False
    assert receipt.exists()
    audit, audit_code = audit_paper_ledger(ledger_path=ledger)
    assert audit_code == 0
    assert audit["decision"] == "pass"


def test_observe_paper_cli_rejects_live_market_source(capsys, tmp_path: Path) -> None:
    code = main(
        [
            "observe",
            "paper",
            "--adapter",
            "fixture-paper-only",
            "--market-source",
            "live",
            "--fixtures",
            "examples/probes/live_observe",
            "--execution",
            "paper",
            "--paper-ledger",
            str(tmp_path / "ledger.sqlite"),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 4
    assert payload["reason_code"] == "unsupported-market-source"
    assert payload["cli_contract"]["command"] == "observe paper"
    assert payload["cli_contract"]["exit_class"] == "operator-refused"
    assert not (tmp_path / "ledger.sqlite").exists()


def test_observe_paper_cli_rejects_non_paper_execution(capsys, tmp_path: Path) -> None:
    code = main(
        [
            "observe",
            "paper",
            "--adapter",
            "fixture-paper-only",
            "--market-source",
            "fixture-live-shape",
            "--fixtures",
            "examples/probes/live_observe",
            "--execution",
            "live",
            "--paper-ledger",
            str(tmp_path / "ledger.sqlite"),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 4
    assert payload["reason_code"] == "unsupported-execution"
    assert not (tmp_path / "ledger.sqlite").exists()
