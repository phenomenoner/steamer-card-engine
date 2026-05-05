from __future__ import annotations

import json
from pathlib import Path

from steamer_card_engine.cli import main


DECK = "examples/decks/tw_cash_real_trade_gate_stage1_short_first.toml"
PROFILE = "examples/profiles/tw_cash_password_auth.toml"


def _arm(state_file: Path, receipt_dir: Path) -> None:
    code = main(
        [
            "operator",
            "arm-live",
            "--deck",
            DECK,
            "--auth-profile",
            PROFILE,
            "--ttl-seconds",
            "300",
            "--confirm-live",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )
    assert code == 0


def test_execute_real_trade_gate_refuses_when_disarmed(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    receipt_dir = tmp_path / "receipts"
    code = main(
        [
            "operator",
            "execute-real-trade-gate",
            "--deck",
            DECK,
            "--auth-profile",
            PROFILE,
            "--symbol",
            "2330",
            "--quantity",
            "1000",
            "--shortable-symbol",
            "2330",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--roundtrip-ledger",
            str(tmp_path / "ledger.json"),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 4
    assert payload["ok"] is False
    assert "submission-gate-denied" in {row["code"] for row in payload["blockers"]}
    assert Path(payload["receipt_path"]).exists()


def test_execute_real_trade_gate_armed_dry_run_writes_receipt_without_ledger(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    receipt_dir = tmp_path / "receipts"
    ledger = tmp_path / "ledger.json"
    _arm(state_file, receipt_dir)
    capsys.readouterr()

    code = main(
        [
            "operator",
            "execute-real-trade-gate",
            "--deck",
            DECK,
            "--auth-profile",
            PROFILE,
            "--symbol",
            "2330",
            "--quantity",
            "1000",
            "--shortable-symbol",
            "2330",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--roundtrip-ledger",
            str(ledger),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["ok"] is True
    assert payload["execution_status"] == "dry-run-closed"
    assert payload["execution_receipt"]["dispatch_suppressed"] is True
    receipt = json.loads(Path(payload["receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["action"] == "execute-real-trade-gate"
    assert receipt["status"] == "executed"
    assert not ledger.exists()


def test_execute_real_trade_gate_refuses_armed_deck_mismatch(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    receipt_dir = tmp_path / "receipts"
    ledger = tmp_path / "ledger.json"
    alt_deck = tmp_path / "alt_deck.toml"
    alt_deck.write_text(Path(DECK).read_text(encoding="utf-8").replace(
        'deck_id = "tw-cash-real-trade-gate-stage1-short-first"',
        'deck_id = "tw-cash-real-trade-gate-stage1-short-first-alt"',
    ), encoding="utf-8")
    _arm(state_file, receipt_dir)
    capsys.readouterr()

    code = main([
        "operator", "execute-real-trade-gate",
        "--deck", str(alt_deck),
        "--auth-profile", PROFILE,
        "--symbol", "2330",
        "--quantity", "1000",
        "--shortable-symbol", "2330",
        "--state-file", str(state_file),
        "--receipt-dir", str(receipt_dir),
        "--roundtrip-ledger", str(ledger),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 4
    assert "armed-scope-deck-mismatch" in {row["code"] for row in payload["blockers"]}


def test_execute_real_trade_gate_hard_caps_quantity_even_if_deck_raises_it(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    receipt_dir = tmp_path / "receipts"
    ledger = tmp_path / "ledger.json"
    oversized_deck = tmp_path / "oversized_deck.toml"
    oversized_deck.write_text(
        Path(DECK).read_text(encoding="utf-8").replace(
            'max_round_trips_per_day = 1\n',
            'max_round_trips_per_day = 1\nmax_quantity = 5000\n',
        ),
        encoding="utf-8",
    )
    code = main([
        "operator", "arm-live",
        "--deck", str(oversized_deck),
        "--auth-profile", PROFILE,
        "--ttl-seconds", "300",
        "--confirm-live",
        "--state-file", str(state_file),
        "--receipt-dir", str(receipt_dir),
        "--json",
    ])
    assert code == 0
    capsys.readouterr()

    code = main([
        "operator", "execute-real-trade-gate",
        "--deck", str(oversized_deck),
        "--auth-profile", PROFILE,
        "--symbol", "2330",
        "--quantity", "1001",
        "--shortable-symbol", "2330",
        "--state-file", str(state_file),
        "--receipt-dir", str(receipt_dir),
        "--roundtrip-ledger", str(ledger),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 4
    assert "quantity-exceeds-policy" in {row["code"] for row in payload["blockers"]}


def test_execute_real_trade_gate_dry_run_does_not_consume_roundtrip_ledger(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    receipt_dir = tmp_path / "receipts"
    ledger = tmp_path / "ledger.json"
    _arm(state_file, receipt_dir)
    capsys.readouterr()
    args = [
        "operator", "execute-real-trade-gate",
        "--deck", DECK,
        "--auth-profile", PROFILE,
        "--symbol", "2330",
        "--quantity", "1000",
        "--shortable-symbol", "2330",
        "--state-file", str(state_file),
        "--receipt-dir", str(receipt_dir),
        "--roundtrip-ledger", str(ledger),
        "--json",
    ]
    assert main(args) == 0
    capsys.readouterr()
    assert main(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["execution_status"] == "dry-run-closed"
    assert not ledger.exists()


def test_execute_real_trade_gate_live_without_secret_dir_refuses(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    receipt_dir = tmp_path / "receipts"
    _arm(state_file, receipt_dir)
    capsys.readouterr()
    code = main([
        "operator", "execute-real-trade-gate",
        "--deck", DECK,
        "--auth-profile", PROFILE,
        "--symbol", "2330",
        "--quantity", "1000",
        "--shortable-symbol", "2330",
        "--mode", "live",
        "--confirm-live-submit",
        "--state-file", str(state_file),
        "--receipt-dir", str(receipt_dir),
        "--roundtrip-ledger", str(tmp_path / "ledger.json"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 4
    assert "neoapi-secret-dir-required" in {row["code"] for row in payload["blockers"]}


def test_execute_real_trade_gate_multi_symbol_dry_run(capsys, tmp_path: Path) -> None:
    deck = tmp_path / "gate5_deck.toml"
    deck.write_text(
        Path("examples/decks/tw_cash_gate5_three_under20_short_first.toml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    state_file = tmp_path / "state.json"
    receipt_dir = tmp_path / "receipts"
    ledger = tmp_path / "ledger.json"
    assert main([
        "operator", "arm-live",
        "--deck", str(deck),
        "--auth-profile", PROFILE,
        "--ttl-seconds", "300",
        "--confirm-live",
        "--state-file", str(state_file),
        "--receipt-dir", str(receipt_dir),
        "--json",
    ]) == 0
    capsys.readouterr()

    code = main([
        "operator", "execute-real-trade-gate",
        "--deck", str(deck),
        "--auth-profile", PROFILE,
        "--symbol", "2002",
        "--symbol", "2834",
        "--symbol", "1314",
        "--quantity", "1000",
        "--shortable-symbol", "2002",
        "--shortable-symbol", "2834",
        "--shortable-symbol", "1314",
        "--state-file", str(state_file),
        "--receipt-dir", str(receipt_dir),
        "--roundtrip-ledger", str(ledger),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["ok"] is True
    assert payload["execution_status"] == "dry-run-closed"
    assert [plan["entry"]["symbol"] for plan in payload["plans"]] == ["2002", "2834", "1314"]
    assert len(payload["execution_receipts"]) == 3
    assert all(row["dispatch_suppressed"] is True for row in payload["execution_receipts"])
    assert not ledger.exists()


def test_execute_real_trade_gate_multi_symbol_refuses_missing_shortable(capsys, tmp_path: Path) -> None:
    deck = tmp_path / "gate5_deck.toml"
    deck.write_text(
        Path("examples/decks/tw_cash_gate5_three_under20_short_first.toml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    state_file = tmp_path / "state.json"
    receipt_dir = tmp_path / "receipts"
    assert main([
        "operator", "arm-live",
        "--deck", str(deck),
        "--auth-profile", PROFILE,
        "--ttl-seconds", "300",
        "--confirm-live",
        "--state-file", str(state_file),
        "--receipt-dir", str(receipt_dir),
        "--json",
    ]) == 0
    capsys.readouterr()

    code = main([
        "operator", "execute-real-trade-gate",
        "--deck", str(deck),
        "--auth-profile", PROFILE,
        "--symbol", "2002",
        "--symbol", "2834",
        "--symbol", "1314",
        "--quantity", "1000",
        "--shortable-symbol", "2002",
        "--shortable-symbol", "2834",
        "--state-file", str(state_file),
        "--receipt-dir", str(receipt_dir),
        "--roundtrip-ledger", str(tmp_path / "ledger.json"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 4
    assert "short-capability-unproven" in {row["code"] for row in payload["blockers"]}
