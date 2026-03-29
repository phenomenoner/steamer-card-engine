from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

from steamer_card_engine.cli import main


def test_cli_validate_card_success(capsys) -> None:
    code = main(["author", "validate-card", "examples/cards/gap_reclaim.toml"])

    captured = capsys.readouterr()
    assert code == 0
    assert "OK: card manifest is valid" in captured.out


def test_cli_inspect_deck_json(capsys) -> None:
    code = main(
        [
            "author",
            "inspect-deck",
            "examples/decks/tw_cash_intraday.toml",
            "--cards-dir",
            "examples/cards",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["deck_id"] == "tw-cash-main"
    assert "gap-reclaim-v1" in payload["enabled_cards"]
    assert "2330" in payload["merged_symbol_scope"]


def test_cli_validate_auth_failure(capsys) -> None:
    code = main(["auth", "validate-profile", "tests/fixtures/bad_auth_missing_key.toml"])

    captured = capsys.readouterr()
    assert code == 2
    assert "Validation failed for auth_profile manifest" in captured.out


def test_cli_validate_strategy_catalog_success(capsys) -> None:
    code = main(
        [
            "catalog",
            "validate",
            "examples/catalog/strategy_catalog_metadata.v0.toml",
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "OK: strategy catalog metadata manifest is valid" in captured.out


def test_cli_query_strategy_catalog_by_regime(capsys) -> None:
    code = main(
        [
            "catalog",
            "query",
            "examples/catalog/strategy_catalog_metadata.v0.toml",
            "--regime",
            "open-drive",
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "gap-reclaim-v1" in captured.out


def test_operator_status_json_disarmed_gate(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "status",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["armed_live"] is False
    assert payload["order_submission_gate"]["allowed"] is False
    assert payload["order_submission_gate"]["reason"] == "disarmed-posture"


def test_operator_arm_live_requires_confirmation(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "arm-live",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--ttl-seconds",
            "300",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 5
    assert payload["ok"] is False
    assert "missing --confirm-live" in payload["error"]


def test_operator_submit_order_refused_when_disarmed(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "submit-order-smoke",
            "--symbol",
            "2330",
            "--side",
            "buy",
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
    assert code == 4
    assert payload["ok"] is False
    assert "runtime is disarmed" in payload["error"]


def test_operator_auto_disarm_after_ttl_expiry(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    arm_code = main(
        [
            "operator",
            "arm-live",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--ttl-seconds",
            "300",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
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

    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["armed_live"] = True
    state["armed_scope"]["expires_at"] = (
        datetime.now(UTC) - timedelta(minutes=1)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    status_code = main(
        [
            "operator",
            "status",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert status_code == 0
    assert payload["armed_live"] is False
    assert "auto_disarm_receipt" in payload


def test_operator_flatten_implicitly_disarms(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    arm_code = main(
        [
            "operator",
            "arm-live",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--ttl-seconds",
            "300",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
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

    flatten_code = main(
        [
            "operator",
            "flatten",
            "--mode",
            "forced-exit",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert flatten_code == 0
    assert payload["ok"] is True
    assert payload["implicit_disarm"] is True
    assert payload["armed_live"] is False
