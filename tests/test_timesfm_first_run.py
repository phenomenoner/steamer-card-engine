from __future__ import annotations

import json
from pathlib import Path

from steamer_card_engine.timesfm_first_run import main, run_first_pass


FIXTURE = Path("tests/fixtures/timesfm_first_run_fixture.csv")


def test_run_first_pass_builds_receipt_without_overclaiming() -> None:
    payload = run_first_pass(
        FIXTURE,
        slice_count=3,
        top_k=1,
        turnover_cost_bps=10.0,
        universe_min_symbols=3,
    )

    assert payload["verdict"] == "HOLD"
    assert payload["strategy_results"]["timesfm"]["summary"]["rank_ic"] > 0
    assert payload["interpretation"]["strongest_trivial_baseline"] in {
        "last_return",
        "momentum_5_20",
        "simple_reversal",
        "moving_average_slope",
        "simple_volatility_proxy",
    }
    assert "## Decision-grade metrics" in payload["markdown_receipt"]


def test_cli_writes_markdown_and_json_receipts(tmp_path: Path, capsys) -> None:
    receipt_md = tmp_path / "receipt.md"
    receipt_json = tmp_path / "receipt.json"

    code = main(
        [
            str(FIXTURE),
            "--top-k",
            "1",
            "--receipt-md",
            str(receipt_md),
            "--receipt-json",
            str(receipt_json),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert receipt_md.exists()
    assert receipt_json.exists()
    assert payload["verdict"] == "HOLD"
    assert receipt_md.read_text(encoding="utf-8").startswith("# Result receipt")
