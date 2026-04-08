from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from steamer_card_engine.session_phase import assess_twse_session_phase


def _assess(clock: str):
    local = datetime.fromisoformat(f"2026-03-13T{clock}").replace(tzinfo=ZoneInfo("Asia/Taipei"))
    assessment = assess_twse_session_phase(local.astimezone(ZoneInfo("UTC")))
    assert assessment is not None
    return assessment


def test_twse_session_phase_boundaries() -> None:
    assert _assess("08:59:59").phase == "pre_open_trial_match"
    assert _assess("09:00:00").phase == "regular_session_open"
    assert _assess("09:01:00").phase == "regular_session"
    assert _assess("12:01:00").phase == "risk_monitor_only"
    assert _assess("13:18:00").phase == "forced_exit"
    assert _assess("13:25:00").phase == "final_auction"
    assert _assess("13:30:00").phase == "session_closed"


def test_twse_session_phase_semantics() -> None:
    open_discovery = _assess("09:00:10")
    forced_exit = _assess("13:18:05")
    regular = _assess("09:05:00")

    assert open_discovery.semantic_label == "open_discovery"
    assert not open_discovery.allows_regular_entry
    assert regular.default_order_profile == "regular-entry-market-ioc"
    assert regular.requested_user_def_suffix == "Enter"
    assert forced_exit.forced_exit_active is True
    assert forced_exit.default_order_profile == "forced-exit-market-rod"
    assert forced_exit.requested_user_def_suffix == "Close"
