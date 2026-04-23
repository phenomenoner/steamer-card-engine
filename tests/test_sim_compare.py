from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from steamer_card_engine.cli import main


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _twse_us(date: str, clock: str) -> int:
    local = datetime.fromisoformat(f"{date}T{clock}").replace(tzinfo=ZoneInfo("Asia/Taipei"))
    return int(local.timestamp() * 1_000_000)


def _build_baseline(
    tmp_path: Path,
    *,
    tick_times: list[str],
    decision_time: str,
    tick_overrides: list[dict] | None = None,
    decision_rows: list[dict] | None = None,
) -> Path:
    baseline = tmp_path / "baseline"
    baseline.mkdir()

    tick_rows = []
    for index, tick_time in enumerate(tick_times):
        row = {
            "raw_id": f"t{index + 1}",
            "raw_event": "data",
            "symbol": "2330",
            "time": _twse_us("2026-03-13", tick_time),
            "price": 950.0 + index,
            "size": max(1, 10 - index),
        }
        if tick_overrides and index < len(tick_overrides):
            row.update(tick_overrides[index])
        tick_rows.append(row)
    _write_jsonl(baseline / "ticks.jsonl", tick_rows)

    if decision_rows is None:
        decision_ts = str(_twse_us("2026-03-13", decision_time))
        decision_rows = [
            {
                "stage": "features",
                "ok": True,
                "reason": "features:ok",
                "side": "long",
                "symbol": "2330",
                "ts": decision_ts,
                "metrics": {"bars": 100, "ret_from_open": 0.01},
            },
            {
                "stage": "gate",
                "ok": True,
                "reason": "gate:ok",
                "side": "long",
                "symbol": "2330",
                "ts": decision_ts,
                "metrics": {"bars": 100},
            },
            {
                "stage": "signal",
                "ok": True,
                "reason": "signal:long_trigger",
                "side": "long",
                "symbol": "2330",
                "ts": decision_ts,
                "metrics": {"bars": 100},
            },
            {
                "stage": "entry",
                "ok": True,
                "reason": "entry:entered",
                "side": "long",
                "symbol": "2330",
                "ts": decision_ts,
                "metrics": {"bars": 100},
            },
        ]
    _write_jsonl(baseline / "decisions.jsonl", decision_rows)

    return baseline


def _build_minimal_baseline(tmp_path: Path) -> Path:
    return _build_baseline(
        tmp_path,
        tick_times=["08:54:09", "08:54:10"],
        decision_time="08:54:10",
    )


def _build_regular_session_baseline(tmp_path: Path) -> Path:
    return _build_baseline(
        tmp_path,
        tick_times=["08:59:50", "09:00:05", "09:01:10"],
        decision_time="09:01:10",
    )


def _build_open_discovery_baseline(tmp_path: Path) -> Path:
    return _build_baseline(
        tmp_path,
        tick_times=["08:59:55", "09:00:05", "09:00:20", "09:01:10"],
        decision_time="09:01:10",
        tick_overrides=[
            {"isTrial": True, "volume": 0},
            {"isTrial": True, "volume": 0},
            {"isTrial": False, "volume": 1200},
            {"isTrial": False, "volume": 2400},
        ],
    )


def _build_forced_exit_baseline(tmp_path: Path) -> Path:
    ts = str(_twse_us("2026-03-13", "13:18:05"))
    return _build_baseline(
        tmp_path,
        tick_times=["13:17:55", "13:18:05", "13:25:05"],
        decision_time="13:18:05",
        tick_overrides=[
            {"isTrial": False, "volume": 10000},
            {"isTrial": False, "volume": 10100},
            {"isTrial": False, "volume": 12000},
        ],
        decision_rows=[
            {
                "stage": "forced_exit",
                "ok": True,
                "reason": "forced_exit:flatten_window",
                "side": "sell",
                "symbol": "2330",
                "ts": ts,
                "metrics": {"bars": 100},
            }
        ],
    )


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
    assert payload["cli_contract"] == {
        "version": "cli-command/v1",
        "command": "sim normalize-baseline",
        "exit_code": 0,
        "exit_class": "success",
        "status_key": "bundle_status",
        "status": "emitted",
    }
    assert payload["counts"]["events"] == 2
    assert payload["counts"]["execution_requests"] == 0
    assert payload["counts"]["anomalies"] >= 1

    run_manifest = _load_json(output_dir / "run-manifest.json")
    anomalies = _load_json(output_dir / "anomalies.json")
    assert run_manifest["capability_posture"]["trade_enabled"] is False
    assert run_manifest["execution_model"]["fill_model"] == "sim-fill-v1"
    assert run_manifest["session_phase_contract"]["version"] == "twse-session-phase/v1"
    assert run_manifest["session_phase_trace"][0]["phase"] == "pre_open_trial_match"
    assert run_manifest["session_phase_trace"][0]["semantic_label"] == "pre_open_warmup"
    assert any(item["category"] == "entry-phase-blocked" for item in anomalies["anomalies"])

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


def test_sim_normalize_baseline_regular_session_emits_execution_request(tmp_path: Path, capsys) -> None:
    baseline = _build_regular_session_baseline(tmp_path)
    output_dir = tmp_path / "bundle_regular"

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
    execution_rows = [json.loads(line) for line in (output_dir / "execution-log.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    lifecycle_rows = [json.loads(line) for line in (output_dir / "order-lifecycle.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    fill_rows = [json.loads(line) for line in (output_dir / "fills.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    position_rows = [json.loads(line) for line in (output_dir / "positions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    pnl_summary = _load_json(output_dir / "pnl-summary.json")
    run_manifest = _load_json(output_dir / "run-manifest.json")

    assert code == 0
    assert payload["counts"]["execution_requests"] == 1
    assert payload["counts"]["fills"] == 1
    assert payload["counts"]["positions"] == 1
    assert execution_rows[0]["market_phase"] == "regular_session"
    assert execution_rows[0]["phase_semantic_label"] == "regular_entry"
    assert execution_rows[0]["time_in_force"] == "IOC"
    assert execution_rows[0]["order_profile_name"] == "regular-entry-market-ioc"
    assert execution_rows[0]["requested_user_def_suffix"] == "Enter"
    assert execution_rows[0]["qty"] == 1.0
    assert lifecycle_rows[0]["state"] == "new"
    assert lifecycle_rows[1]["state"] == "filled"
    assert fill_rows[0]["symbol"] == "2330"
    assert fill_rows[0]["qty"] == 1.0
    assert position_rows[0]["net_qty"] == 1.0
    assert position_rows[0]["position_state"] == "open"
    assert pnl_summary["entry_count"] == 1
    assert pnl_summary["max_position_qty"] == 1.0
    assert run_manifest["session_phase_trace"][0]["phase"] == "pre_open_trial_match"
    assert run_manifest["session_phase_trace"][-1]["phase"] == "regular_session"


def test_sim_normalize_baseline_records_open_discovery_summary(tmp_path: Path, capsys) -> None:
    baseline = _build_open_discovery_baseline(tmp_path)
    output_dir = tmp_path / "bundle_open_discovery"

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
    capsys.readouterr()
    run_manifest = _load_json(output_dir / "run-manifest.json")
    event_rows = [json.loads(line) for line in (output_dir / "event-log.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    assert code == 0
    assert run_manifest["open_discovery_summary"]["saw_trial_match_event"] is True
    assert run_manifest["open_discovery_summary"]["saw_official_open_signal"] is True
    assert run_manifest["open_discovery_summary"]["first_trial_match_utc"] is not None
    assert run_manifest["open_discovery_summary"]["first_official_open_signal_utc"] is not None
    assert any(row["market_observation_state"] == "trial-match" for row in event_rows)
    assert any(row["market_observation_state"] == "official-open-print" for row in event_rows)


def test_sim_normalize_baseline_emits_forced_exit_execution_request(tmp_path: Path, capsys) -> None:
    baseline = _build_forced_exit_baseline(tmp_path)
    output_dir = tmp_path / "bundle_forced_exit"

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
    payload = json.loads(capsys.readouterr().out)
    execution_rows = [json.loads(line) for line in (output_dir / "execution-log.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    risk_rows = [json.loads(line) for line in (output_dir / "risk-receipts.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    lifecycle_rows = [json.loads(line) for line in (output_dir / "order-lifecycle.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    assert code == 0
    assert payload["counts"]["execution_requests"] == 1
    assert execution_rows[0]["market_phase"] == "forced_exit"
    assert execution_rows[0]["phase_semantic_label"] == "forced_close"
    assert execution_rows[0]["time_in_force"] == "ROD"
    assert execution_rows[0]["order_profile_name"] == "forced-exit-market-rod"
    assert execution_rows[0]["requested_user_def_suffix"] == "Close"
    assert risk_rows[0]["policy_name"] == "legacy_forced_exit_policy"
    assert lifecycle_rows[0]["exec_request_id"] == execution_rows[0]["exec_request_id"]
    assert lifecycle_rows[0]["state"] == "new"
    assert lifecycle_rows[0]["order_profile_name"] == "forced-exit-market-rod"


def test_sim_run_live_shares_phase_trace_with_replay_bundle(tmp_path: Path, capsys) -> None:
    baseline = _build_regular_session_baseline(tmp_path)
    replay_output = tmp_path / "replay_bundle"
    live_output_root = tmp_path / "runs"

    replay_code = main(
        [
            "sim",
            "normalize-baseline",
            "--baseline-dir",
            str(baseline),
            "--output-dir",
            str(replay_output),
            "--session-date",
            "2026-03-13",
            "--scenario-id",
            "tw-gap-reclaim.twse.2026-03-13.full-session",
            "--json",
        ]
    )
    replay_payload = json.loads(capsys.readouterr().out)

    live_code = main(
        [
            "sim",
            "run-live",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--session-date",
            "2026-03-13",
            "--scenario-id",
            "tw-live-sim.twse.2026-03-13.full-session",
            "--baseline-dir",
            str(baseline),
            "--output-root",
            str(live_output_root),
            "--json",
        ]
    )
    live_payload = json.loads(capsys.readouterr().out)

    replay_manifest = _load_json(replay_output / "run-manifest.json")
    live_bundle = Path(live_payload["bundle_dir"])
    live_manifest = _load_json(live_bundle / "run-manifest.json")
    live_config = _load_json(live_bundle / "config-snapshot.json")
    live_intents = [
        json.loads(line)
        for line in (live_bundle / "intent-log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert replay_code == 0
    assert live_code == 0
    assert replay_payload["counts"]["execution_requests"] == 1
    assert live_payload["mode"] == "live-sim"
    assert replay_manifest["session_phase_trace"] == live_manifest["session_phase_trace"]
    assert live_manifest["capability_posture"]["trade_enabled"] is False
    assert live_config["deck_id"] == "tw-cash-main"
    assert live_config["cards"] == [{"card_id": "gap-reclaim-v1", "card_version": "manifest/v0"}]
    assert {row["deck_id"] for row in live_intents} == {"tw-cash-main"}
    assert {row["card_id"] for row in live_intents} == {"gap-reclaim-v1"}


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
    assert payload["cli_contract"] == {
        "version": "cli-command/v1",
        "command": "sim compare",
        "exit_code": 3,
        "exit_class": "general-failure",
        "status_key": "status",
        "status": "fail",
    }
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
    assert payload["cli_contract"] == {
        "version": "cli-command/v1",
        "command": "sim compare",
        "exit_code": 0,
        "exit_class": "success",
        "status_key": "status",
        "status": "pass",
    }
    diff = _load_json(compare_out / "diff.json")
    assert diff["counts"]["intents"]["baseline"] >= 1
    assert "decision_grade_diff" in diff


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
    assert payload["cli_contract"] == {
        "version": "cli-command/v1",
        "command": "replay run",
        "exit_code": 0,
        "exit_class": "success",
        "status_key": "mode",
        "status": "replay",
    }

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
    assert payload["cli_contract"] == {
        "version": "cli-command/v1",
        "command": "replay run",
        "exit_code": 0,
        "exit_class": "success",
        "status_key": "mode",
        "status": "dry-run",
    }
    assert not Path(payload["output_dir"]).exists()


def test_sim_run_live_emits_live_sim_bundle(tmp_path: Path, capsys) -> None:
    baseline = _build_minimal_baseline(tmp_path)
    output_root = tmp_path / "runs"

    code = main(
        [
            "sim",
            "run-live",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--session-date",
            "2026-03-13",
            "--scenario-id",
            "tw-live-sim.twse.2026-03-13.full-session",
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
    assert payload["mode"] == "live-sim"
    assert payload["cli_contract"] == {
        "version": "cli-command/v1",
        "command": "sim run-live",
        "exit_code": 0,
        "exit_class": "success",
        "status_key": "mode",
        "status": "live-sim",
    }

    bundle_dir = Path(payload["bundle_dir"])
    run_manifest = _load_json(bundle_dir / "run-manifest.json")

    assert run_manifest["run_type"] == "live-sim"
    assert run_manifest["capability_posture"]["trade_enabled"] is False


def test_sim_run_live_dry_run_has_no_side_effect(tmp_path: Path, capsys) -> None:
    baseline = _build_minimal_baseline(tmp_path)
    output_root = tmp_path / "runs"

    code = main(
        [
            "sim",
            "run-live",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--session-date",
            "2026-03-13",
            "--scenario-id",
            "tw-live-sim.twse.2026-03-13.full-session",
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
    assert payload["run_type"] == "live-sim"
    assert payload["cli_contract"] == {
        "version": "cli-command/v1",
        "command": "sim run-live",
        "exit_code": 0,
        "exit_class": "success",
        "status_key": "mode",
        "status": "dry-run",
    }
    assert not Path(payload["output_dir"]).exists()


def test_sim_compare_hard_fails_scenario_mismatch(tmp_path: Path, capsys) -> None:
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
                "2026-03-14",
                "--scenario-id",
                "tw-gap-reclaim.twse.2026-03-14.full-session",
                "--lane",
                "steamer-card-engine",
            ]
        )
        == 0
    )
    capsys.readouterr()

    compare_out = tmp_path / "compare_scenario_mismatch"
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
    assert any("scenario_id mismatch" in reason for reason in payload["hard_fail_reasons"])


def test_replay_run_requires_baseline_dir() -> None:
    with pytest.raises(SystemExit) as ex:
        main(
            [
                "replay",
                "run",
                "--deck",
                "examples/decks/tw_cash_intraday.toml",
                "--date",
                "2026-03-13",
                "--scenario-id",
                "tw-gap-reclaim.twse.2026-03-13.full-session",
            ]
        )
    assert ex.value.code == 2


def test_sim_compare_hard_fails_scenario_mismatch_with_replay_candidate(
    tmp_path: Path, capsys
) -> None:
    baseline = _build_minimal_baseline(tmp_path)
    baseline_bundle = tmp_path / "baseline_bundle"
    output_root = tmp_path / "runs"

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

    replay_code = main(
        [
            "replay",
            "run",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--date",
            "2026-03-14",
            "--scenario-id",
            "tw-gap-reclaim.twse.2026-03-14.full-session",
            "--baseline-dir",
            str(baseline),
            "--output-root",
            str(output_root),
            "--run-id",
            "candidate-mismatch-run",
            "--json",
        ]
    )
    assert replay_code == 0
    replay_payload = json.loads(capsys.readouterr().out)

    compare_out = tmp_path / "compare_scenario_mismatch_replay"
    compare_code = main(
        [
            "sim",
            "compare",
            "--baseline",
            str(baseline_bundle),
            "--candidate",
            replay_payload["bundle_dir"],
            "--output-dir",
            str(compare_out),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert compare_code == 3
    assert payload["status"] == "fail"
    assert any("scenario_id mismatch" in reason for reason in payload["hard_fail_reasons"])


def test_sim_compare_allow_missing_fingerprint_flag(tmp_path: Path, capsys) -> None:
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
            ]
        )
        == 0
    )
    capsys.readouterr()

    candidate_manifest_path = candidate_bundle / "run-manifest.json"
    candidate_manifest = _load_json(candidate_manifest_path)
    candidate_manifest.pop("scenario_fingerprint", None)
    candidate_manifest_path.write_text(
        json.dumps(candidate_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    file_index_path = candidate_bundle / "file-index.json"
    file_index = _load_json(file_index_path)
    for entry in file_index.get("files", []):
        if entry.get("path") == "run-manifest.json":
            entry["sha256"] = hashlib.sha256(candidate_manifest_path.read_bytes()).hexdigest()
            entry["bytes"] = candidate_manifest_path.stat().st_size
            break
    file_index_path.write_text(
        json.dumps(file_index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    compare_out_strict = tmp_path / "compare_missing_fingerprint_strict"
    strict_code = main(
        [
            "sim",
            "compare",
            "--baseline",
            str(baseline_bundle),
            "--candidate",
            str(candidate_bundle),
            "--output-dir",
            str(compare_out_strict),
            "--json",
        ]
    )
    strict_payload = json.loads(capsys.readouterr().out)
    assert strict_code == 3
    assert any("scenario_fingerprint missing" in reason for reason in strict_payload["hard_fail_reasons"])

    compare_out_relaxed = tmp_path / "compare_missing_fingerprint_relaxed"
    relaxed_code = main(
        [
            "sim",
            "compare",
            "--baseline",
            str(baseline_bundle),
            "--candidate",
            str(candidate_bundle),
            "--output-dir",
            str(compare_out_relaxed),
            "--allow-missing-fingerprint",
            "--json",
        ]
    )
    relaxed_payload = json.loads(capsys.readouterr().out)
    assert relaxed_code == 0
    assert relaxed_payload["status"] == "pass"


def test_replay_run_json_error_path_stays_machine_readable(tmp_path: Path, capsys) -> None:
    missing_baseline = tmp_path / "missing-baseline"
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
            str(missing_baseline),
            "--output-root",
            str(output_root),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["ok"] is False
    assert "candidate replay baseline source not found" in payload["error"]
    assert payload["cli_contract"] == {
        "version": "cli-command/v1",
        "command": "replay run",
        "exit_code": 2,
        "exit_class": "general-failure",
        "status_key": "status",
        "status": "error",
    }
