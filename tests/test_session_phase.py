from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from steamer_card_engine.session_phase import assess_twse_session_phase


def _assess(clock: str) -> str:
    local = datetime.fromisoformat(f"2026-03-13T{clock}").replace(tzinfo=ZoneInfo("Asia/Taipei"))
    assessment = assess_twse_session_phase(local.astimezone(ZoneInfo("UTC")))
    assert assessment is not None
    return assessment.phase


def test_twse_session_phase_boundaries() -> None:
    assert _assess("08:59:59") == "pre_open_trial_match"
    assert _assess("09:00:00") == "regular_session_open"
    assert _assess("09:01:00") == "regular_session"
    assert _assess("13:25:00") == "final_auction"
    assert _assess("13:30:00") == "session_closed"
