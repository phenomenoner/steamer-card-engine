from __future__ import annotations

import json
from pathlib import Path

from steamer_card_engine.triangle_compare import build_candidate_from_trace, compare_summaries, load_trace, summarize_trace


def test_triangle_compare_builds_c_from_b_state(tmp_path: Path) -> None:
    path = tmp_path / "b.jsonl"
    row = {
        "symbol": "1234",
        "gate": "REV_SHORT_AFTER_UP",
        "enter": False,
        "reason": "now_time_5",
        "state": {
            "symbol": "1234",
            "is_open": False,
            "sweet_ok": True,
            "now_time": "09:10:00",
            "max_seen": 10.0,
            "last_close": 9.5,
            "open_px": 9.6,
            "new_high_recent": True,
            "now_ts": 1.0,
            "last_qualified_high_ts": 1.0,
            "zz_trend": 0,
            "slope_down_ok": False,
            "px": 10.0,
            "price_ema": 10.0,
            "slope": None,
            "slope_2": None,
            "slope_3": None,
            "upper_limit_start_time": None,
        },
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    rows = load_trace(path, gate="REV_SHORT_AFTER_UP", end_local="09:30:00")
    c_rows = build_candidate_from_trace(rows, gate="REV_SHORT_AFTER_UP", cfg={"market_gate": 5, "allow_blind_open": False, "strong_up_pct": 3.0, "strong_up_pct_abs": 5.0, "require_recent_high": True, "enable_zz": True, "enable_angle": True, "fallback_pct": 1.2})
    assert c_rows[0]["reason"] == "now_time_5"


def test_compare_summaries_reports_deltas() -> None:
    left = summarize_trace("left", [{"symbol": "1", "enter": False, "reason": "a"}])
    right = summarize_trace("right", [{"symbol": "1", "enter": True, "reason": "b"}])
    delta = compare_summaries(left, right)
    assert delta["enter_true_delta"] == 1
    assert delta["reason_delta_top20_scope"] == {"a": -1, "b": 1}
