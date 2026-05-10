from __future__ import annotations

import json
from pathlib import Path

from steamer_card_engine.order_intent_compare import (
    compare_intent_multisets,
    decision_to_intent,
    intent_signature,
    load_order_intents,
    parse_order_result,
)


def test_decision_to_enter_order_intent() -> None:
    row = {"symbol": "2367", "enter": True, "reason": "enter_rev_short", "state": {"now_ts": 1, "now_time": "09:39:41"}}
    intent = decision_to_intent(row, source="legacy", line_no=1)
    assert intent["action"] == "enter"
    assert intent["side"] == "sell"
    assert intent["quantity"] == 1000
    assert intent["price_basis"] == "market"
    assert intent["order_time_in_force"] == "IOC"


def test_parse_order_result_and_load_order_intent(tmp_path: Path) -> None:
    data = 'OrderResult {\n    stock_no: "2367",\n    buy_sell: Sell,\n    price_type: Market,\n    quantity: 1000,\n    time_in_force: IOC,\n    order_type: DayTrade,\n    user_def: "hvl_enter",\n    last_time: "09:39:41.330",\n}'
    parsed = parse_order_result(data)
    assert parsed["buy_sell"] == "Sell"
    assert parsed["quantity"] == "1000"
    path = tmp_path / "orders.jsonl"
    path.write_text(json.dumps({"event": "order_submit", "time": 1.0, "symbol": "2367", "action": "enter", "data": data}) + "\n", encoding="utf-8")
    intents = load_order_intents(path, source="orders")
    assert intents[0]["symbol"] == "2367"
    assert intents[0]["side"] == "sell"
    assert intents[0]["order_type"] == "DayTrade"


def test_compare_intent_multisets() -> None:
    left = [{"symbol": "1", "action": "enter", "side": "sell", "quantity": 1000, "price_basis": "market", "order_type": "DayTrade", "order_time_in_force": "IOC"}]
    right = list(left)
    assert compare_intent_multisets(left, right, left_name="l", right_name="r")["match"] is True
    assert compare_intent_multisets(left, [], left_name="l", right_name="r")["match"] is False


def test_counterfactual_quantity_tif_and_symbol_mismatch_flags() -> None:
    left = [{"symbol": "1", "action": "enter", "side": "sell", "quantity": 1000, "price_basis": "market", "order_type": "DayTrade", "order_time_in_force": "IOC"}]
    right = [{"symbol": "2", "action": "enter", "side": "sell", "quantity": 2000, "price_basis": "market", "order_type": "DayTrade", "order_time_in_force": "ROD"}]
    result = compare_intent_multisets(left, right, left_name="legacy", right_name="candidate")
    assert result["match"] is False
    assert result["missing_from_right"][0]["class"] == "order_lifecycle_diff"
    assert result["extra_in_right"][0]["class"] == "order_lifecycle_diff"
    assert intent_signature(left[0]) != intent_signature(right[0])
