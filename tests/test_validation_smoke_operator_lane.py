from __future__ import annotations

import json
from pathlib import Path

from steamer_card_engine.cli import main


def test_validation_smoke_preflight_ready_on_validation_deck(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "preflight-smoke",
            "--deck",
            "examples/decks/tw_cash_validation_smoke.toml",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--trading-day-status",
            "open",
            "--probe-json",
            "examples/probes/session_health.connected.json",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["ok"] is True
    assert payload["deck"] == "examples/decks/tw_cash_validation_smoke.toml"
    assert payload["logical_session"]["boundary"]["probe_source"] == "example-probe"
    assert payload["operator_status"]["armed_live"] is False


def test_validation_smoke_live_smoke_readiness_passes_on_validation_deck(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "live-smoke-readiness",
            "--deck",
            "examples/decks/tw_cash_validation_smoke.toml",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--trading-day-status",
            "open",
            "--probe-json",
            "examples/probes/session_health.connected.json",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["ok"] is True
    assert payload["smoke_status"] == "pass"
    assert payload["deck"] == "examples/decks/tw_cash_validation_smoke.toml"
    assert payload["preflight"]["deck"] == "examples/decks/tw_cash_validation_smoke.toml"
    assert payload["preflight"]["logical_session"]["boundary"]["probe_source"] == "example-probe"
    assert payload["steps"][0]["step"] == "preflight-smoke-gate"


def test_validation_smoke_live_smoke_readiness_blocks_with_agent_assist_profile(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "live-smoke-readiness",
            "--deck",
            "examples/decks/tw_cash_validation_smoke.toml",
            "--auth-profile",
            "examples/profiles/tw_cash_agent_assist.toml",
            "--trading-day-status",
            "open",
            "--probe-json",
            "examples/probes/session_health.connected.json",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    blocker_codes = {row["code"] for row in payload["preflight"]["blockers"]}
    assert code == 4
    assert payload["smoke_status"] == "blocked"
    assert payload["preflight"]["deck"] == "examples/decks/tw_cash_validation_smoke.toml"
    assert "capability-trade-disabled" in blocker_codes
