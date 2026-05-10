from __future__ import annotations

import json
from pathlib import Path

import pytest

from steamer_card_engine.legacy_equivalence import (
    DEFAULT_GATE_CONFIG,
    GateDecision,
    LegacyEquivalenceError,
    compare_file,
    main,
    normalize_state,
    resolve_output_dir,
    rev_short_after_up_card_decision,
)


def _base_rev_state() -> dict:
    return {
        "symbol": "1234",
        "px": 104.0,
        "avg_px": 105.0,
        "max_seen": 106.0,
        "min_seen": 100.0,
        "open_px": 100.0,
        "last_close": 100.0,
        "price_ema": 105.0,
        "zz_trend": -1,
        "slope_down_ok": True,
        "slope": -20.0,
        "slope_2": 0.0,
        "slope_3": 0.0,
        "sweet_ok": True,
        "is_open": False,
        "new_high_recent": True,
        "last_qualified_high_ts": 1000.0,
        "now_ts": 1100.0,
        "now_time": "09:31:00",
        "upper_limit_start_time": None,
    }


def test_rev_short_after_up_compatibility_enter() -> None:
    state = normalize_state(_base_rev_state())
    decision = rev_short_after_up_card_decision(state, dict(DEFAULT_GATE_CONFIG))
    assert decision == GateDecision(True, "enter_rev_short")


def test_rev_short_after_up_counterfactual_wrong_fallback_changes_decision() -> None:
    state = normalize_state(_base_rev_state())
    cfg = dict(DEFAULT_GATE_CONFIG)
    cfg["fallback_pct"] = 3.0
    decision = rev_short_after_up_card_decision(state, cfg)
    assert decision == GateDecision(False, "too_shallow")


def test_resolve_output_dir_rejects_paths_outside_runs() -> None:
    with pytest.raises(LegacyEquivalenceError):
        resolve_output_dir("/tmp/not-allowed")
    with pytest.raises(LegacyEquivalenceError):
        resolve_output_dir("../not-allowed")


def test_empty_run_refuses_false_pass(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    with pytest.raises(LegacyEquivalenceError, match="no matching decision rows"):
        main(["--data-root", str(data_root), "--output-dir", "runs/legacy-equivalence/empty-test"])


def test_compare_file_reports_reason_mismatch(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    decision_dir = data_root / "dt3" / "20260129"
    decision_dir.mkdir(parents=True)
    path = decision_dir / "decisions.jsonl"
    row = {
        "symbol": "1234",
        "gate": "REV_SHORT_AFTER_UP",
        "enter": True,
        "reason": "legacy_old_reason",
        "state": _base_rev_state(),
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    dataset, samples = compare_file(
        path,
        data_root=data_root,
        gates={"REV_SHORT_AFTER_UP"},
        cfg=dict(DEFAULT_GATE_CONFIG),
        max_mismatch_samples=10,
    )

    stats = dataset["gates"]["REV_SHORT_AFTER_UP"]
    assert stats["rows"] == 1
    assert stats["enter_mismatches"] == 0
    assert stats["reason_mismatches"] == 1
    assert samples[0]["candidate_reason"] == "enter_rev_short"
