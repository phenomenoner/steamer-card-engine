from __future__ import annotations

import json
from pathlib import Path

from steamer_card_engine.legacy_replay import replay_session


def test_latest_legacy_replay_emits_rows(tmp_path: Path) -> None:
    root = tmp_path / "data"
    session = root / "dt3" / "20260129"
    session.mkdir(parents=True)
    ticks = [
        {"symbol": "1234", "price": 10.0, "bid": 10.0, "time": 1_000_000, "isOpen": True},
        {"symbol": "1234", "price": 10.5, "bid": 10.5, "time": 2_000_000, "isContinuous": True},
    ]
    decisions = [
        {"symbol": "1234", "gate": "REV_SHORT_AFTER_UP", "enter": False, "reason": "now_time_5", "state": {"last_close": 9.8}}
    ]
    (session / "ticks.jsonl").write_text("".join(json.dumps(row) + "\n" for row in ticks), encoding="utf-8")
    (session / "decisions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in decisions), encoding="utf-8")

    rows = replay_session(
        data_root=root,
        machine="dt3",
        date="20260129",
        gate="REV_SHORT_AFTER_UP",
        cfg={
            "market_gate": 5,
            "allow_blind_open": False,
            "strong_up_pct": 3.0,
            "strong_up_pct_abs": 5.0,
            "require_recent_high": True,
            "enable_zz": True,
            "enable_angle": True,
            "fallback_pct": 1.2,
            "new_high_tol_pct": 0.97,
            "zz_threshold": 0.2,
            "honey_sweet_profit_pct": 5.0,
        },
        max_rows=None,
        end_local=None,
    )
    assert len(rows) == 2
    assert rows[0]["state"]["open_px"] == 10.0
    assert rows[0]["reason"] == "blocked_blind_open"
