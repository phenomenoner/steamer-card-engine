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
    assert payload["plan"]["exit_leg"]["side"] == "cover"
    assert payload["plan"]["exit_leg"]["broker_order_side"] == "buy"
    assert payload["plan"]["max_entry_orders_per_run"] == 1
    assert payload["cli_contract"]["command"] == "operator plan-real-trade-gate"
    assert payload["cli_contract"]["status"] == "planned"
    receipt = json.loads(Path(payload["receipt_path"]).read_text())
    assert receipt["schema_version"] == "operator-action-receipt/v1"
    assert receipt["action"] == "plan-real-trade-gate"
    assert receipt["status"] == "planned"
    assert receipt["details"]["request"]["symbol"] == "2330"
    assert receipt["details"]["plan"]["exit_leg"]["side"] == "cover"
    assert receipt["posture"]["armed_live"] is False


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


def test_real_trade_gate_plan_refuses_unrelated_deck_even_if_symbol_shortable(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "plan-real-trade-gate",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
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
    blocker_codes = {row["code"] for row in payload["blockers"]}
    assert code == 4
    assert "stage1-deck-card-contract-mismatch" in blocker_codes
    assert "real-trade-gate-policy-missing" in blocker_codes
    assert Path(payload["receipt_path"]).exists()


def test_real_trade_gate_plan_refuses_non_trade_profile(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "plan-real-trade-gate",
            "--deck",
            "examples/decks/tw_cash_real_trade_gate_stage1_short_first.toml",
            "--auth-profile",
            "examples/profiles/tw_cash_agent_assist.toml",
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
    blocker_codes = {row["code"] for row in payload["blockers"]}
    assert code == 4
    assert "trade-disabled" in blocker_codes
    assert Path(payload["receipt_path"]).exists()


def test_real_trade_gate_plan_refuses_while_already_armed(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    arm_code = main(
        [
            "operator",
            "arm-live",
            "--deck",
            "examples/decks/tw_cash_real_trade_gate_stage1_short_first.toml",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--ttl-seconds",
            "60",
            "--confirm-live",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )
    assert arm_code == 0
    capsys.readouterr()

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
    blocker_codes = {row["code"] for row in payload["blockers"]}
    assert code == 4
    assert "posture-already-armed" in blocker_codes
    assert Path(payload["receipt_path"]).exists()


def test_real_trade_gate_plan_refuses_invalid_quantity_and_delay(capsys, tmp_path: Path) -> None:
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
            "0",
            "--exit-delay-seconds",
            "0",
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
    blocker_codes = {row["code"] for row in payload["blockers"]}
    assert code == 4
    assert "invalid-quantity" in blocker_codes
    assert "invalid-exit-delay" in blocker_codes
    assert Path(payload["receipt_path"]).exists()


def test_real_trade_gate_plan_rejects_buy_first_for_stage1(capsys, tmp_path: Path) -> None:
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
            "buy",
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
    blocker_codes = {row["code"] for row in payload["blockers"]}
    assert code == 4
    assert "stage1-requires-sell-first" in blocker_codes
    assert Path(payload["receipt_path"]).exists()


def _write_stage1_deck(path: Path, *, cards: list[str]) -> None:
    cards_literal = ",\n  ".join(f'"{card}"' for card in cards)
    path.write_text(
        "deck_id = \"tmp-stage1-contract\"\n"
        "market = \"TW_CASH\"\n"
        "session = \"intraday\"\n"
        "auth_profile = \"profiles/tw_cash_password_auth.toml\"\n"
        f"cards = [\n  {cards_literal}\n]\n"
        "symbol_scope = [\"2330\"]\n\n"
        "[policy]\n"
        "live_mode = true\n"
        "allow_card_symbol_pool = true\n\n"
        "[policy.real_trade_gate]\n"
        "stage = \"stage1-short-capability-smoke\"\n"
        "entry_side = \"sell\"\n"
        "exit_side = \"cover\"\n"
        "max_entry_orders_per_run = 1\n"
        "max_exit_orders_per_run = 1\n"
        "max_round_trips_per_day = 1\n"
        "requires_shortable_symbol_allowlist = true\n",
        encoding="utf-8",
    )


def _assert_stage1_deck_refused(capsys, tmp_path: Path, deck_cards: list[str]) -> None:
    deck_path = tmp_path / "stage1_deck.toml"
    _write_stage1_deck(deck_path, cards=deck_cards)
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "plan-real-trade-gate",
            "--deck",
            str(deck_path),
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
    blocker_codes = {row["code"] for row in payload["blockers"]}
    assert code == 4
    assert blocker_codes & {"stage1-deck-card-contract-mismatch", "deck-manifest-invalid"}
    assert Path(payload["receipt_path"]).exists()


def test_real_trade_gate_plan_refuses_duplicate_entry_card_sequence(capsys, tmp_path: Path) -> None:
    _assert_stage1_deck_refused(
        capsys,
        tmp_path,
        [
            "real-trade-gate-short-first-entry-v1",
            "real-trade-gate-short-first-entry-v1",
            "real-trade-gate-short-first-cover-v1",
        ],
    )


def test_real_trade_gate_plan_refuses_reversed_card_sequence(capsys, tmp_path: Path) -> None:
    _assert_stage1_deck_refused(
        capsys,
        tmp_path,
        [
            "real-trade-gate-short-first-cover-v1",
            "real-trade-gate-short-first-entry-v1",
        ],
    )
