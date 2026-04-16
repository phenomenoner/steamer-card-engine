from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import steamer_card_engine.cli as cli_module
from steamer_card_engine.cli import main
from steamer_card_engine import operator_control


def _write_stage(root: Path, probe_date: str, stage: str, payload: dict) -> None:
    path = root / probe_date / "stages" / f"{stage}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_cli_validate_card_success(capsys) -> None:
    code = main(["author", "validate-card", "examples/cards/gap_reclaim.toml"])

    captured = capsys.readouterr()
    assert code == 0
    assert "OK: card manifest is valid" in captured.out


def test_cli_inspect_deck_json(capsys) -> None:
    code = main(
        [
            "author",
            "inspect-deck",
            "examples/decks/tw_cash_intraday.toml",
            "--cards-dir",
            "examples/cards",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["deck_id"] == "tw-cash-main"
    assert "gap-reclaim-v1" in payload["enabled_cards"]
    assert "2330" in payload["merged_symbol_scope"]


def test_cli_validate_auth_failure(capsys) -> None:
    code = main(["auth", "validate-profile", "tests/fixtures/bad_auth_missing_key.toml"])

    captured = capsys.readouterr()
    assert code == 2
    assert "Validation failed for auth_profile manifest" in captured.out


def test_cli_inspect_session_json_reports_seed_logical_session(capsys) -> None:
    code = main(
        [
            "auth",
            "inspect-session",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--trading-day-status",
            "closed",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["auth_profile"] == "examples/profiles/tw_cash_password_auth.toml"
    assert payload["capabilities"]["trade_enabled"] is True
    assert payload["health_status"]["broker_connection"] == "not-connected"
    assert payload["session_status"]["connections"]["marketdata"]["state"] == "not-connected"
    assert payload["session_status"]["session_state"] == "logical-profile-only"
    assert payload["trading_day_gate"]["status"] == "closed"
    assert payload["trading_day_gate"]["live_allowed"] is False
    assert payload["boundary"]["activation"] == "prepared-only"


def test_cli_inspect_session_accepts_probe_snapshot_override(capsys, tmp_path: Path) -> None:
    probe = tmp_path / "probe.json"
    probe.write_text(
        json.dumps(
            {
                "probe_source": "fixture-probe",
                "session_status": {
                    "session_state": "healthy",
                    "renewal_state": "fresh",
                    "connected_surfaces": ["marketdata", "broker", "account"],
                    "degraded_surfaces": [],
                    "connections": {
                        "marketdata": {"state": "connected", "detail": "fixture", "last_heartbeat_at": None, "last_error": None},
                        "broker": {"state": "connected", "detail": "fixture", "last_heartbeat_at": None, "last_error": None},
                        "account": {"state": "connected", "detail": "fixture", "last_heartbeat_at": None, "last_error": None},
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    code = main(
        [
            "auth",
            "inspect-session",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--trading-day-status",
            "open",
            "--probe-json",
            str(probe),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["session_status"]["session_state"] == "healthy"
    assert payload["health_status"]["broker_connection"] == "connected"
    assert payload["boundary"]["probe_source"] == "fixture-probe"


def test_cli_inspect_session_can_resolve_steamer_cron_health_probe_source(
    capsys, tmp_path: Path, monkeypatch
) -> None:
    probe_date = "20260416"
    stage_root = tmp_path / "cron-health"
    monkeypatch.setattr(cli_module, "STEAMER_CRON_HEALTH_ROOT", stage_root)
    _write_stage(
        stage_root,
        probe_date,
        "aws_auth",
        {
            "status": "success",
            "detail": "aws_sts_ok",
            "updated_at": "2026-04-16T00:25:14Z",
        },
    )
    _write_stage(
        stage_root,
        probe_date,
        "ec2_verify",
        {
            "status": "success",
            "detail": "verify_green",
            "updated_at": "2026-04-16T00:45:17Z",
        },
    )

    code = main(
        [
            "auth",
            "inspect-session",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--trading-day-status",
            "open",
            "--probe-source",
            "steamer-cron-health",
            "--probe-date",
            probe_date,
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["boundary"]["probe_source"] == f"steamer-cron-health:{probe_date}"
    assert payload["session_status"]["connections"]["broker"]["state"] == "connected"
    assert payload["boundary"]["broker_connected"] is True
    assert payload["boundary"]["probe_freshness"]["status"] == "fresh"
    assert payload["boundary"]["probe_freshness"]["observed_at"] == "2026-04-16T00:45:17Z"
    assert payload["boundary"]["probe_receipt"]["label"] == f"ec2_verify:{probe_date}"
    assert payload["boundary"]["probe_receipt"]["path"] == str(
        (stage_root / probe_date / "stages" / "ec2_verify.json").resolve()
    )


def test_cli_inspect_session_named_source_missing_stage_dir_stays_not_connected(
    capsys, tmp_path: Path, monkeypatch
) -> None:
    probe_date = "20260416"
    monkeypatch.setattr(cli_module, "STEAMER_CRON_HEALTH_ROOT", tmp_path / "missing-root")

    code = main(
        [
            "auth",
            "inspect-session",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--trading-day-status",
            "open",
            "--probe-source",
            "steamer-cron-health",
            "--probe-date",
            probe_date,
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["boundary"]["probe_source"] == f"steamer-cron-health:{probe_date}"
    assert payload["session_status"]["connections"]["broker"]["state"] == "not-connected"
    assert payload["boundary"]["probe_freshness"]["status"] == "not-attached"
    assert payload["boundary"]["probe_receipt"]["path"] is None


def test_operator_probe_session_emits_canonical_seed_snapshot(capsys) -> None:
    code = main(
        [
            "operator",
            "probe-session",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--trading-day-status",
            "open",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["probe_source"] == "operator-probe-session:seed"
    assert payload["session_status"]["connections"]["broker"]["state"] == "not-connected"
    assert payload["capabilities"]["trade_enabled"] is True
    assert payload["probe_freshness"]["status"] == "seed-unverified"
    assert payload["probe_receipt"]["kind"] == "seed"


def test_probe_json_takes_precedence_over_named_probe_source(
    capsys, tmp_path: Path, monkeypatch
) -> None:
    probe_date = "20260416"
    stage_root = tmp_path / "cron-health"
    monkeypatch.setattr(cli_module, "STEAMER_CRON_HEALTH_ROOT", stage_root)
    _write_stage(
        stage_root,
        probe_date,
        "ec2_verify",
        {
            "status": "success",
            "detail": "verify_green",
            "updated_at": "2026-04-16T00:45:17Z",
        },
    )
    probe = tmp_path / "probe.json"
    probe.write_text(Path("examples/probes/session_health.connected.json").read_text(encoding="utf-8"), encoding="utf-8")

    code = main(
        [
            "auth",
            "inspect-session",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--trading-day-status",
            "open",
            "--probe-json",
            str(probe),
            "--probe-source",
            "steamer-cron-health",
            "--probe-date",
            probe_date,
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["boundary"]["probe_source"] == "example-probe"
    assert payload["session_status"]["connections"]["account"]["state"] == "connected"


def test_operator_probe_session_writes_snapshot_file(capsys, tmp_path: Path) -> None:
    output_path = tmp_path / "probe" / "session_probe.json"

    code = main(
        [
            "operator",
            "probe-session",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--trading-day-status",
            "open",
            "--probe-json",
            "examples/probes/session_health.connected.json",
            "--output",
            str(output_path),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["output_path"] == str(output_path)
    assert written["probe_source"] == "example-probe"
    assert written["session_status"]["session_state"] == "healthy"
    assert written["probe_freshness"]["status"] == "fresh"
    assert written["probe_receipt"]["path"] == str(Path("examples/probes/session_health.connected.json").resolve())


def test_cli_validate_strategy_catalog_success(capsys) -> None:
    code = main(
        [
            "catalog",
            "validate",
            "examples/catalog/strategy_catalog_metadata.v0.toml",
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "OK: strategy catalog metadata manifest is valid" in captured.out


def test_cli_query_strategy_catalog_by_regime(capsys) -> None:
    code = main(
        [
            "catalog",
            "query",
            "examples/catalog/strategy_catalog_metadata.v0.toml",
            "--regime",
            "open-drive",
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "gap-reclaim-v1" in captured.out


def test_operator_status_json_disarmed_gate(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "status",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["armed_live"] is False
    assert payload["order_submission_gate"]["allowed"] is False
    assert payload["order_submission_gate"]["reason"] == "disarmed-posture"


def test_operator_status_empty_state_file_treated_as_default(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    state_file.write_text("", encoding="utf-8")
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "status",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["armed_live"] is False
    assert payload["order_submission_gate"]["reason"] == "disarmed-posture"


def test_operator_arm_live_requires_confirmation(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "arm-live",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--ttl-seconds",
            "300",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 5
    assert payload["ok"] is False
    assert "missing --confirm-live" in payload["error"]


def test_operator_submit_order_refused_when_disarmed(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "submit-order-smoke",
            "--symbol",
            "2330",
            "--side",
            "buy",
            "--quantity",
            "1",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 4
    assert payload["ok"] is False
    assert "runtime is disarmed" in payload["error"]


def test_operator_auto_disarm_after_ttl_expiry(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    arm_code = main(
        [
            "operator",
            "arm-live",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--ttl-seconds",
            "300",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--confirm-live",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )
    assert arm_code == 0
    capsys.readouterr()

    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["armed_live"] = True
    state["armed_scope"]["expires_at"] = (
        datetime.now(UTC) - timedelta(minutes=1)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    status_code = main(
        [
            "operator",
            "status",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert status_code == 0
    assert payload["armed_live"] is False
    assert "auto_disarm_receipt" in payload


def test_operator_auto_disarm_when_scope_missing_expiry(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    arm_code = main(
        [
            "operator",
            "arm-live",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--ttl-seconds",
            "300",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--confirm-live",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )
    assert arm_code == 0
    capsys.readouterr()

    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["armed_live"] = True
    state["armed_scope"].pop("expires_at", None)
    state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    status_code = main(
        [
            "operator",
            "status",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert status_code == 0
    assert payload["armed_live"] is False
    assert "auto_disarm_receipt" in payload

    receipt_payload = json.loads(Path(payload["auto_disarm_receipt"]).read_text(encoding="utf-8"))
    assert receipt_payload["action"] == "auto-disarm"
    assert receipt_payload["status"] == "scope-invalid"
    assert receipt_payload["details"]["reason"] == "missing-expires-at"


def test_operator_submit_order_reports_auto_disarm_receipt_when_ttl_expired(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    arm_code = main(
        [
            "operator",
            "arm-live",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--ttl-seconds",
            "300",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--confirm-live",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )
    assert arm_code == 0
    capsys.readouterr()

    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["armed_live"] = True
    state["armed_scope"]["expires_at"] = (
        datetime.now(UTC) - timedelta(minutes=1)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    code = main(
        [
            "operator",
            "submit-order-smoke",
            "--symbol",
            "2330",
            "--side",
            "buy",
            "--quantity",
            "1",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 4
    assert payload["ok"] is False
    assert payload["gate_reason"] == "disarmed-posture"
    assert "auto_disarm_receipt" in payload

    receipt_payload = json.loads(Path(payload["auto_disarm_receipt"]).read_text(encoding="utf-8"))
    assert receipt_payload["action"] == "auto-disarm"
    assert receipt_payload["status"] == "ttl-expired"


def test_operator_submit_order_reports_scope_invalid_receipt_when_expiry_malformed(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    arm_code = main(
        [
            "operator",
            "arm-live",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--ttl-seconds",
            "300",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--confirm-live",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )
    assert arm_code == 0
    capsys.readouterr()

    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["armed_live"] = True
    state["armed_scope"]["expires_at"] = "not-a-utc-timestamp"
    state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    code = main(
        [
            "operator",
            "submit-order-smoke",
            "--symbol",
            "2330",
            "--side",
            "buy",
            "--quantity",
            "1",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 4
    assert payload["ok"] is False
    assert payload["gate_reason"] == "disarmed-posture"
    assert "auto_disarm_receipt" in payload

    auto_disarm = json.loads(Path(payload["auto_disarm_receipt"]).read_text(encoding="utf-8"))
    assert auto_disarm["action"] == "auto-disarm"
    assert auto_disarm["status"] == "scope-invalid"
    assert auto_disarm["details"]["reason"] == "invalid-expires-at"
    assert auto_disarm["details"]["expires_at"] == "not-a-utc-timestamp"

    refusal = json.loads(Path(payload["receipt_path"]).read_text(encoding="utf-8"))
    assert refusal["details"]["auto_disarm_receipt"] == payload["auto_disarm_receipt"]


def test_operator_flatten_implicitly_disarms(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    arm_code = main(
        [
            "operator",
            "arm-live",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--ttl-seconds",
            "300",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--confirm-live",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )
    assert arm_code == 0
    capsys.readouterr()

    flatten_code = main(
        [
            "operator",
            "flatten",
            "--mode",
            "forced-exit",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert flatten_code == 0
    assert payload["ok"] is True
    assert payload["implicit_disarm"] is True
    assert payload["armed_live"] is False


def test_operator_live_smoke_readiness_runs_bounded_sequence(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "live-smoke-readiness",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--trading-day-status",
            "open",
            "--probe-json",
            "examples/probes/session_health.connected.json",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["ok"] is True
    assert payload["smoke_status"] == "pass"
    assert payload["activation"] == "prepared-only"
    assert payload["preflight"]["preflight_status"] == "ready"
    assert [step["step"] for step in payload["steps"]] == [
        "preflight-smoke-gate",
        "status-disarmed-baseline",
        "submit-refused-while-disarmed",
        "arm-live-bounded-scope",
        "submit-accepted-while-armed",
        "flatten-and-close-armed-window",
        "status-disarmed-after-flatten",
    ]
    assert all(step["ok"] for step in payload["steps"])
    assert len(payload["receipt_paths"]) == 4

    final_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert final_state["armed_live"] is False


def test_operator_live_smoke_readiness_fails_without_trade_capability(capsys, tmp_path: Path) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "live-smoke-readiness",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--auth-profile",
            "examples/profiles/tw_cash_agent_assist.toml",
            "--trading-day-status",
            "open",
            "--probe-json",
            "examples/probes/session_health.connected.json",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 4
    assert payload["ok"] is False
    assert payload["smoke_status"] == "blocked"
    assert payload["probe_freshness"]["status"] == "fresh"
    assert payload["probe_receipt"]["kind"] == "probe-json"
    assert payload["failed_step"]["step"] == "preflight-smoke-gate"
    blocker_codes = {row["code"] for row in payload["preflight"]["blockers"]}
    assert "capability-trade-disabled" in blocker_codes
    assert state_file.exists()
    assert not receipt_dir.exists()


def test_operator_live_smoke_readiness_cleans_up_arm_state_after_midsequence_failure(
    capsys, tmp_path: Path, monkeypatch
) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    original_submit = operator_control.operator_submit_order_smoke
    call_count = {"value": 0}

    def fail_on_armed_submit(**kwargs):
        call_count["value"] += 1
        if call_count["value"] == 2:
            return operator_control.OperatorResult(
                payload={
                    "ok": False,
                    "error": "synthetic armed submit failure",
                },
                exit_code=1,
            )
        return original_submit(**kwargs)

    monkeypatch.setattr(operator_control, "operator_submit_order_smoke", fail_on_armed_submit)

    code = main(
        [
            "operator",
            "live-smoke-readiness",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--trading-day-status",
            "open",
            "--probe-json",
            "examples/probes/session_health.connected.json",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["ok"] is False
    assert payload["failed_step"]["step"] == "submit-accepted-while-armed"
    assert payload["steps"][-1]["step"] == "cleanup-disarm-after-failure"
    assert payload["steps"][-1]["ok"] is True

    final_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert final_state["armed_live"] is False


def test_operator_live_smoke_readiness_consumes_steamer_cron_health_probe_source(
    capsys, tmp_path: Path, monkeypatch
) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"
    probe_date = "20260416"
    stage_root = tmp_path / "cron-health"
    monkeypatch.setattr(cli_module, "STEAMER_CRON_HEALTH_ROOT", stage_root)
    _write_stage(
        stage_root,
        probe_date,
        "aws_auth",
        {
            "status": "success",
            "detail": "aws_sts_ok",
            "updated_at": "2026-04-16T00:25:14Z",
        },
    )
    _write_stage(
        stage_root,
        probe_date,
        "ec2_verify",
        {
            "status": "success",
            "detail": "verify_green",
            "updated_at": "2026-04-16T00:45:17Z",
        },
    )

    code = main(
        [
            "operator",
            "live-smoke-readiness",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--trading-day-status",
            "open",
            "--probe-source",
            "steamer-cron-health",
            "--probe-date",
            probe_date,
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["steps"][0]["step"] == "preflight-smoke-gate"
    assert payload["steps"][0]["ok"] is True
    assert payload["probe_freshness"]["status"] == "fresh"
    assert payload["probe_receipt"]["label"] == f"ec2_verify:{probe_date}"
    assert payload["preflight"]["logical_session"]["boundary"]["probe_source"] == (
        f"steamer-cron-health:{probe_date}"
    )
    assert (
        payload["preflight"]["logical_session"]["session_status"]["connections"]["account"]["state"]
        == "not-connected"
    )


def test_operator_preflight_smoke_truthfully_blocks_when_seed_runtime_not_connected(
    capsys, tmp_path: Path
) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"

    code = main(
        [
            "operator",
            "preflight-smoke",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--trading-day-status",
            "open",
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 4
    assert payload["ok"] is False
    assert payload["preflight_status"] == "blocked"
    assert payload["probe_freshness"]["status"] == "seed-unverified"
    assert payload["probe_receipt"]["kind"] == "seed"
    blocker_codes = {row["code"] for row in payload["blockers"]}
    assert "marketdata-not-connected" in blocker_codes
    assert "broker-not-connected" in blocker_codes
    assert payload["logical_session"]["trading_day_gate"]["status"] == "open"
    assert payload["replacement_contract"]["expected_connected_surfaces"] == ["marketdata", "broker"]
    assert payload["operator_status"]["armed_live"] is False


def test_operator_preflight_smoke_classifies_stale_probe_states(
    capsys, tmp_path: Path
) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"
    probe = tmp_path / "probe.json"
    probe.write_text(
        json.dumps(
            {
                "probe_source": "fixture-probe",
                "session_status": {
                    "session_state": "stale",
                    "renewal_state": "attention-needed",
                    "connected_surfaces": [],
                    "degraded_surfaces": ["marketdata", "broker"],
                    "connections": {
                        "marketdata": {"state": "stale", "detail": "ticks stale", "last_heartbeat_at": None, "last_error": "ticks stale"},
                        "broker": {"state": "stale", "detail": "ticks stale", "last_heartbeat_at": None, "last_error": "ticks stale"},
                        "account": {"state": "stale", "detail": "ticks stale", "last_heartbeat_at": None, "last_error": "ticks stale"},
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    code = main(
        [
            "operator",
            "preflight-smoke",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--trading-day-status",
            "open",
            "--probe-json",
            str(probe),
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    blocker_codes = {row["code"] for row in payload["blockers"]}
    assert code == 4
    assert "marketdata-stale" in blocker_codes
    assert "broker-stale" in blocker_codes


def test_operator_preflight_smoke_can_read_probe_snapshot_and_turn_ready(
    capsys, tmp_path: Path
) -> None:
    state_file = tmp_path / "operator_state.json"
    receipt_dir = tmp_path / "receipts"
    probe = tmp_path / "probe.json"
    probe.write_text(
        json.dumps(
            {
                "probe_source": "fixture-probe",
                "session_status": {
                    "session_state": "healthy",
                    "renewal_state": "fresh",
                    "connected_surfaces": ["marketdata", "broker", "account"],
                    "degraded_surfaces": [],
                    "connections": {
                        "marketdata": {"state": "connected", "detail": "fixture", "last_heartbeat_at": None, "last_error": None},
                        "broker": {"state": "connected", "detail": "fixture", "last_heartbeat_at": None, "last_error": None},
                        "account": {"state": "connected", "detail": "fixture", "last_heartbeat_at": None, "last_error": None},
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    code = main(
        [
            "operator",
            "preflight-smoke",
            "--deck",
            "examples/decks/tw_cash_intraday.toml",
            "--auth-profile",
            "examples/profiles/tw_cash_password_auth.toml",
            "--trading-day-status",
            "open",
            "--probe-json",
            str(probe),
            "--state-file",
            str(state_file),
            "--receipt-dir",
            str(receipt_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["ok"] is True
    assert payload["preflight_status"] == "ready"
    assert payload["logical_session"]["boundary"]["probe_source"] == "fixture-probe"
    assert payload["probe_freshness"]["status"] == "fresh"
    assert payload["probe_receipt"]["kind"] == "probe-json"
    assert payload["probe_receipt"]["path"] == str(probe.resolve())
