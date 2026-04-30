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


def test_real_trade_gate_plan_refuses_sell_first_without_shortable_allowlist(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "plan-real-trade-gate",
            "--deck",
            "examples/decks/tw_cash_real_trade_gate_stage1_short_first.toml",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--symbol",
            "2330",
            "--entry-side",
            "sell",
            "--quantity",
            "1",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    blocker_codes = {row["code"] for row in payload["blockers"]}
    assert code == 4
    assert payload["ok"] is False
    assert payload["plan_status"] == "refused"
    assert "short-capability-unproven" in blocker_codes
    assert Path(payload["receipt_path"]).exists()


def test_real_trade_gate_plan_accepts_sell_first_with_shortable_allowlist(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "plan-real-trade-gate",
            "--deck",
            "examples/decks/tw_cash_real_trade_gate_stage1_short_first.toml",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--symbol",
            "2330",
            "--entry-side",
            "sell",
            "--quantity",
            "1",
            "--shortable-symbol",
            "2330",
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
    assert payload["plan_status"] == "planned"
    assert payload["plan"]["entry_leg"]["side"] == "sell"
    assert payload["plan"]["exit_leg"]["side"] == "buy"
    assert payload["plan"]["max_entry_orders_per_run"] == 1
    assert Path(payload["receipt_path"]).exists()


def test_real_trade_gate_plan_refuses_symbol_outside_deck_scope_even_if_shortable(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "plan-real-trade-gate",
            "--deck",
            "examples/decks/tw_cash_real_trade_gate_stage1_short_first.toml",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--symbol",
            "2317",
            "--entry-side",
            "sell",
            "--quantity",
            "1",
            "--shortable-symbol",
            "2317",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    blocker_codes = {row["code"] for row in payload["blockers"]}
    assert code == 4
    assert "symbol-not-in-deck-scope" in blocker_codes
