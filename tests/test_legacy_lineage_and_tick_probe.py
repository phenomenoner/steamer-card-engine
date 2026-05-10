from __future__ import annotations

import json
from pathlib import Path

from steamer_card_engine.legacy_lineage import classify_mismatch
from steamer_card_engine.legacy_tick_probe import load_tick_series, probe_session, reconstruct_at


def test_classify_risk_order_layer() -> None:
    row = {"enter": False, "reason": "no_funds: avail=1", "state": {}}
    klass, _ = classify_mismatch(row, "enter_rev_short", True)
    assert klass == "risk_order_layer"


def test_classify_market_gate_policy_lineage() -> None:
    row = {"enter": False, "reason": "now_time_3", "state": {}}
    klass, _ = classify_mismatch(row, "now_time_5", False)
    assert klass == "policy_lineage"


def test_tick_reconstruct_at() -> None:
    series = {"ts": [1.0, 2.0, 3.0], "price": [10.0, 12.0, 11.0]}
    reconstructed = reconstruct_at(series, 2.5)
    assert reconstructed is not None
    assert {key: reconstructed[key] for key in ["px", "open_px", "max_seen", "min_seen"]} == {
        "px": 12.0,
        "open_px": 10.0,
        "max_seen": 12.0,
        "min_seen": 10.0,
    }


def test_probe_session_core_price_fields(tmp_path: Path) -> None:
    root = tmp_path / "data"
    session = root / "dt3" / "20260129"
    session.mkdir(parents=True)
    ticks = [
        {"symbol": "1234", "price": 10.0, "ws_received_time": 1.0, "isOpen": True},
        {"symbol": "1234", "price": 12.0, "ws_received_time": 2.0, "isContinuous": True},
        {"symbol": "1234", "price": 11.0, "ws_received_time": 3.0, "isContinuous": True},
    ]
    decisions = [
        {
            "symbol": "1234",
            "gate": "REV_SHORT_AFTER_UP",
            "enter": False,
            "reason": "not_strong_up",
            "state": {"now_ts": 2.5, "px": 12.0, "open_px": 10.0, "max_seen": 12.0, "min_seen": 10.0},
        }
    ]
    (session / "ticks.jsonl").write_text("".join(json.dumps(row) + "\n" for row in ticks), encoding="utf-8")
    (session / "decisions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in decisions), encoding="utf-8")

    summary = probe_session(
        data_root=root,
        machine="dt3",
        date="20260129",
        gate="REV_SHORT_AFTER_UP",
        max_samples=10,
        tolerance=0.0,
    )
    assert summary["verdict"] == "PASS_FEASIBLE"
    assert summary["field_summary"]["px"]["mismatches"] == 0
