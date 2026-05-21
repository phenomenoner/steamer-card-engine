from __future__ import annotations

import json
from pathlib import Path

from steamer_card_engine.cli import main


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_normalize_dt3_legacy_emits_fills_positions_and_pnl(capsys, tmp_path: Path) -> None:
    src = tmp_path / "dt3" / "20260519"
    _write_jsonl(
        src / "ticks.jsonl",
        [
            {"time": 1779152700.0, "symbol": "1785", "price": 146.0},
            {"time": 1779155702.0, "symbol": "1785", "price": 142.0},
        ],
    )
    _write_jsonl(
        src / "decisions.jsonl",
        [
            {
                "symbol": "1785",
                "gate": "REV_SHORT_AFTER_UP",
                "enter": True,
                "reason": "enter_rev_short",
                "time": 1779152713.0,
                "state": {"px": 146.0},
            }
        ],
    )
    _write_jsonl(
        src / "orders.jsonl",
        [
            {
                "event": "order_submit",
                "symbol": "1785",
                "time": 1779152713.4,
                "user_def": "hvl1Enter",
                "status": 10,
                "action": "enter",
                "order_no": "KT001",
                "data": "buy_sell: Sell, price_type: Market, quantity: 1000, time_in_force: IOC, order_type: DayTrade, order_no: KT001, seq_no: 0001, stock_no: 1785, user_def: hvl1Enter",
            },
            {
                "event": "order_fill",
                "symbol": "1785",
                "time": 1779152714.0,
                "user_def": "hvl1Enter",
                "action": "enter",
                "order_no": "KT001",
                "data": "buy_sell: Sell, filled_qty: 1000, filled_price: 146.0, order_no: KT001, stock_no: 1785, user_def: hvl1Enter",
            },
            {
                "event": "order_fill",
                "symbol": "1785",
                "time": 1779155702.0,
                "user_def": "hvl1Exit",
                "action": "exit",
                "order_no": "KT002",
                "data": "buy_sell: Buy, filled_qty: 1000, filled_price: 142.0, order_no: KT002, stock_no: 1785, user_def: hvl1Exit",
            },
            {
                "event": "trade_summary",
                "symbol": "1785",
                "time": 1779155702.4,
                "action": "Short",
                "entry_price": 146.0,
                "exit_price": 142.0,
                "qty": 1000,
                "pnl": 4000.0,
                "duration": 2988.0,
            },
        ],
    )

    out = tmp_path / "bundle"
    code = main(
        [
            "sim",
            "normalize-dt3-legacy",
            "--source-dir",
            str(src),
            "--output-dir",
            str(out),
            "--session-date",
            "2026-05-19",
            "--scenario-id",
            "dt3-test.2026-05-19",
            "--run-id",
            "dt3-test-run",
            "--intent-source",
            "decision-first",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["counts"]["intents"] == 1
    assert payload["counts"]["fills"] == 2
    assert payload["counts"]["positions"] == 2
    assert payload["pnl_summary"]["realized_pnl_gross"] == 4000.0
    assert payload["dt3_contract"]["position_gate"] == "first_successful_entry_only"
    assert payload["dt3_contract"]["selected_symbol"] == "1785"
    assert payload["dt3_contract"]["intent_source"] == "decision-first"
    assert payload["dt3_contract"]["order_decision_symbol_match"] is True

    fills = [json.loads(line) for line in (out / "fills.jsonl").read_text().splitlines()]
    assert [row["side"] for row in fills] == ["sell", "buy"]
    assert json.loads((out / "run-manifest.json").read_text())["capability_posture"]["trade_enabled"] is False
