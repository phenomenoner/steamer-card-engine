from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "aws_shadow_observer_dry_run.py"
spec = importlib.util.spec_from_file_location("aws_shadow_observer_dry_run", MODULE_PATH)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_active_universe_from_sources() -> None:
    symbols = mod.active_universe_from_sources(
        [{"symbol": "2330"}],
        [{"state": {"symbol": "1301"}}],
        [{"symbol": "2330"}],
    )
    assert symbols == ["1301", "2330"]


def test_card_shadow_intent_rows_enter_only() -> None:
    rows = mod.card_shadow_intent_rows([
        {"symbol": "2367", "enter": True, "reason": "enter_rev_short", "state": {"now_time": "09:30:00", "now_ts": 1}},
        {"symbol": "2367", "enter": False, "reason": "above_ema", "state": {"now_time": "09:30:01", "now_ts": 2}},
    ])
    assert len(rows) == 1
    assert rows[0]["action"] == "enter"
    assert rows[0]["submits_orders"] if "submits_orders" in rows[0] else True
