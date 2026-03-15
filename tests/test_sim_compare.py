from __future__ import annotations

import json
from pathlib import Path

from steamer_card_engine.cli import main


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _build_minimal_baseline(tmp_path: Path) -> Path:
    baseline = tmp_path / "baseline"
    baseline.mkdir()

    _write_jsonl(
        baseline / "ticks.jsonl",
        [
            {
                "raw_id": "t1",
                "raw_event": "data",
                "symbol": "2330",
                "time": 1773363249201491,
                "price": 950.0,
                "size": 10,
            },
            {
                "raw_id": "t2",
                "raw_event": "data",
                "symbol": "2330",
                "time": 1773363250201491,
                "price": 951.0,
                "size": 5,
            },
        ],
    )

    _write_jsonl(
        baseline / "decisions.jsonl",
        [
            {
                "stage": "features",
                "ok": True,
                "reason": "features:ok",
                "side": "long",
                "symbol": "2330",
                "ts": "1773363250201491",
                "metrics": {"bars": 100, "ret_from_open": 0.01},
            },
            {
                "stage": "gate",
                "ok": True,
                "reason": "gate:ok",
                "side": "long",
                "symbol": "2330",
                "ts": "1773363250201491",
                "metrics": {"bars": 100},
            },
            {
                "stage": "signal",
                "ok": True,
                "reason": "signal:long_trigger",
                "side": "long",
                "symbol": "2330",
                "ts": "1773363250201491",
                "metrics": {"bars": 100},
            },
            {
                "stage": "entry",
                "ok": True,
                "reason": "entry:entered",
                "side": "long",
                "symbol": "2330",
                "ts": "1773363250201491",
                "metrics": {"bars": 100},
            },
        ],
    )

    return baseline


def test_sim_normalize_baseline_emits_bundle(tmp_path: Path, capsys) -> None:
    baseline = _build_minimal_baseline(tmp_path)
    output_dir = tmp_path / "bundle"

    code = main(
        [
            "sim",
            "normalize-baseline",
            "--baseline-dir",
            str(baseline),
            "--output-dir",
            str(output_dir),
            "--session-date",
            "2026-03-13",
            "--scenario-id",
            "tw-gap-reclaim.twse.2026-03-13.full-session",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["counts"]["events"] == 2
    assert payload["counts"]["execution_requests"] == 1

    run_manifest = _load_json(output_dir / "run-manifest.json")
    assert run_manifest["capability_posture"]["trade_enabled"] is False
    assert run_manifest["execution_model"]["fill_model"] == "sim-fill-v1"

    compare_required = [
        "run-manifest.json",
        "scenario-spec.json",
        "event-log.jsonl",
        "feature-provenance.jsonl",
        "intent-log.jsonl",
        "risk-receipts.jsonl",
        "execution-log.jsonl",
        "order-lifecycle.jsonl",
        "fills.jsonl",
        "positions.jsonl",
        "pnl-summary.json",
        "anomalies.json",
        "config-snapshot.json",
        "file-index.json",
    ]
    for name in compare_required:
        assert (output_dir / name).exists(), name


def test_sim_compare_hard_fails_execution_model_mismatch(tmp_path: Path, capsys) -> None:
    baseline = _build_minimal_baseline(tmp_path)
    baseline_bundle = tmp_path / "baseline_bundle"
    candidate_bundle = tmp_path / "candidate_bundle"

    code_a = main(
        [
            "sim",
            "normalize-baseline",
            "--baseline-dir",
            str(baseline),
            "--output-dir",
            str(baseline_bundle),
            "--session-date",
            "2026-03-13",
            "--scenario-id",
            "tw-gap-reclaim.twse.2026-03-13.full-session",
            "--lane",
            "baseline-bot",
        ]
    )
    assert code_a == 0
    capsys.readouterr()

    code_b = main(
        [
            "sim",
            "normalize-baseline",
            "--baseline-dir",
            str(baseline),
            "--output-dir",
            str(candidate_bundle),
            "--session-date",
            "2026-03-13",
            "--scenario-id",
            "tw-gap-reclaim.twse.2026-03-13.full-session",
            "--lane",
            "steamer-card-engine",
            "--fill-model",
            "broker-live-v1",
        ]
    )
    assert code_b == 0
    capsys.readouterr()

    compare_out = tmp_path / "compare_mismatch"
    compare_code = main(
        [
            "sim",
            "compare",
            "--baseline",
            str(baseline_bundle),
            "--candidate",
            str(candidate_bundle),
            "--output-dir",
            str(compare_out),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert compare_code == 3
    assert payload["status"] == "fail"
    assert any(
        "execution_model mismatch (hard stop)" in reason
        for reason in payload["hard_fail_reasons"]
    )


def test_sim_compare_passes_when_hard_gates_match(tmp_path: Path, capsys) -> None:
    baseline = _build_minimal_baseline(tmp_path)
    baseline_bundle = tmp_path / "baseline_bundle"
    candidate_bundle = tmp_path / "candidate_bundle"

    assert (
        main(
            [
                "sim",
                "normalize-baseline",
                "--baseline-dir",
                str(baseline),
                "--output-dir",
                str(baseline_bundle),
                "--session-date",
                "2026-03-13",
                "--scenario-id",
                "tw-gap-reclaim.twse.2026-03-13.full-session",
                "--lane",
                "baseline-bot",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "sim",
                "normalize-baseline",
                "--baseline-dir",
                str(baseline),
                "--output-dir",
                str(candidate_bundle),
                "--session-date",
                "2026-03-13",
                "--scenario-id",
                "tw-gap-reclaim.twse.2026-03-13.full-session",
                "--lane",
                "steamer-card-engine",
                "--fill-model",
                "sim-fill-v1",
            ]
        )
        == 0
    )
    capsys.readouterr()

    compare_out = tmp_path / "compare_pass"
    compare_code = main(
        [
            "sim",
            "compare",
            "--baseline",
            str(baseline_bundle),
            "--candidate",
            str(candidate_bundle),
            "--output-dir",
            str(compare_out),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert compare_code == 0
    assert payload["status"] == "pass"
    diff = _load_json(compare_out / "diff.json")
    assert diff["counts"]["intents"]["baseline"] >= 1
    assert diff["scaffold_placeholders"]["per_symbol_totals"] == "pending"


def test_replay_run_emits_candidate_bundle(tmp_path: Path, capsys) -> None:
    baseline = _build_minimal_baseline(tmp_path)
    output_root = tmp_path / "runs"

    code = main(
        [
            "replay",
            "run",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--date",
            "2026-03-13",
            "--scenario-id",
            "tw-gap-reclaim.twse.2026-03-13.full-session",
            "--baseline-dir",
            str(baseline),
            "--output-root",
            str(output_root),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["mode"] == "replay"
    assert payload["lane"] == "steamer-card-engine"

    bundle_dir = Path(payload["bundle_dir"])
    run_manifest = _load_json(bundle_dir / "run-manifest.json")
    config_snapshot = _load_json(bundle_dir / "config-snapshot.json")

    assert run_manifest["provenance"]["engine_name"] == "steamer-card-engine-replay-runner"
    assert config_snapshot["emitter"]["name"] == "steamer-card-engine replay run"
    assert config_snapshot["emitter"]["version"] == "m1-replay-runner/v0"


def test_replay_run_dry_run_has_no_side_effect(tmp_path: Path, capsys) -> None:
    baseline = _build_minimal_baseline(tmp_path)
    output_root = tmp_path / "runs"

    code = main(
        [
            "replay",
            "run",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--date",
            "2026-03-13",
            "--scenario-id",
            "tw-gap-reclaim.twse.2026-03-13.full-session",
            "--baseline-dir",
            str(baseline),
            "--output-root",
            str(output_root),
            "--dry-run",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["mode"] == "dry-run"
    assert not Path(payload["output_dir"]).exists()
