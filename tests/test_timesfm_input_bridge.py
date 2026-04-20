from __future__ import annotations

import csv
import json
from pathlib import Path

from steamer_card_engine.timesfm_first_run import run_first_pass
from steamer_card_engine.timesfm_input_bridge import build_timesfm_input, main

FIXTURE_DIR = Path(__file__).parent / "fixtures"
CLOSE_HISTORY = FIXTURE_DIR / "timesfm_bridge_close_history.csv"
SCORES = FIXTURE_DIR / "timesfm_bridge_scores.csv"
WATCHLIST = FIXTURE_DIR / "timesfm_bridge_watchlist.csv"


def test_build_timesfm_input_merges_close_and_scores(tmp_path: Path) -> None:
    out_csv = tmp_path / "bridged.csv"
    summary_json = tmp_path / "summary.json"

    summary = build_timesfm_input(
        CLOSE_HISTORY,
        SCORES,
        out_csv,
        watchlist_path=WATCHLIST,
        summary_path=summary_json,
    )

    assert summary["rows_written"] == 72
    assert summary["unique_dates"] == 24
    assert summary["unique_symbols"] == 3
    assert summary["score_column"] == "timesfm_pred_return"

    with out_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0] == {
        "date": "2026-01-01",
        "symbol": "AAA",
        "close": "100",
        "timesfm_pred_return": "0.01",
    }
    assert json.loads(summary_json.read_text(encoding="utf-8"))["rows_written"] == 72


def test_bridge_cli_output_runs_first_pass(tmp_path: Path, capsys) -> None:
    out_csv = tmp_path / "bridged.csv"
    summary_json = tmp_path / "summary.json"

    code = main(
        [
            "--close-history",
            str(CLOSE_HISTORY),
            "--score-csv",
            str(SCORES),
            "--watchlist-csv",
            str(WATCHLIST),
            "--out",
            str(out_csv),
            "--summary-json",
            str(summary_json),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["rows_written"] == 72
    first_pass = run_first_pass(out_csv, slice_count=3, top_k=1, turnover_cost_bps=10.0, universe_min_symbols=3)
    assert first_pass["verdict"] in {"PROMISING", "HOLD", "ITERATE", "KILL"}
    assert first_pass["input_contract"]["fixed_universe_symbols"] == ["AAA", "BBB", "CCC"]
