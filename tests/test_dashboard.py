from __future__ import annotations

from pathlib import Path
import json
import re
import shutil
import tomllib

from fastapi.testclient import TestClient

from steamer_card_engine.dashboard import build_day_bundle, create_app, list_fixture_dates
from steamer_card_engine.dashboard.fixtures import FixtureDay, repo_root
from steamer_card_engine.dashboard.history_source_index import STATE_RELATIVE_PATH, build_strategy_history_source_index
from steamer_card_engine.dashboard.strategy_pipeline import build_strategy_pipeline_view
from steamer_card_engine.dashboard.strategy_powerhouse import build_strategy_powerhouse_view
from steamer_card_engine.observer import build_mock_observer_session, reset_observer_repository_cache
from steamer_card_engine.observer.history import _build_record


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_relpath(workspace_root: Path, raw_path: str | None) -> str | None:
    if raw_path is None:
        return None
    text = str(raw_path).strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = workspace_root / path
    try:
        return str(path.relative_to(workspace_root))
    except ValueError:
        return str(path)


def _target_labels(workspace_root: Path, payload: dict | None) -> list[str]:
    if not payload:
        return []
    labels: list[str] = []
    for item in payload.get("targets") or []:
        if not isinstance(item, dict):
            continue
        variant_id = str(item.get("variant_id") or "").strip()
        deck_path = str(item.get("deck_path") or "").strip()
        deck_id = None
        if deck_path:
            resolved = Path(deck_path)
            if not resolved.is_absolute():
                resolved = workspace_root / resolved
            if resolved.exists():
                with resolved.open("rb") as file:
                    deck = tomllib.load(file)
                deck_id = deck.get("deck_id")

        if deck_id and variant_id:
            labels.append(f"{deck_id} ({variant_id})")
        elif deck_id:
            labels.append(str(deck_id))
        elif variant_id:
            labels.append(variant_id)
    return labels


def test_observer_api_defaults_to_mock_session() -> None:
    reset_observer_repository_cache()
    client = TestClient(create_app())

    sessions = client.get("/api/observer/sessions")
    assert sessions.status_code == 200
    payload = sessions.json()
    assert payload["items"]
    assert payload["items"][0]["session_id"] == "aws-live-sim-demo"


def test_observer_api_accepts_attached_bundle_json(monkeypatch, tmp_path: Path) -> None:
    bundle = build_mock_observer_session()
    attachment = {
        "metadata": {
            "session_id": "aws-live-sim-private",
            "engine_id": "steamer-card-engine.live-sim.private",
            "session_label": "AWS live(sim) private attachment",
            "market_mode": "live(sim)",
            "symbol": "2330.TW",
            "timeframe": "1m",
        },
        "events": [
            {
                **event.to_dict(),
                "session_id": "aws-live-sim-private",
                "engine_id": "steamer-card-engine.live-sim.private",
                "event_id": f"private-{event.event_id}",
            }
            for event in bundle.events
        ],
    }
    attachment_path = tmp_path / "observer-attachment.json"
    attachment_path.write_text(json.dumps(attachment), encoding="utf-8")

    monkeypatch.setenv("STEAMER_OBSERVER_BUNDLE_JSON", str(attachment_path))
    monkeypatch.setenv("STEAMER_OBSERVER_INCLUDE_MOCK", "0")
    reset_observer_repository_cache()

    client = TestClient(create_app())

    sessions = client.get("/api/observer/sessions")
    assert sessions.status_code == 200
    payload = sessions.json()
    assert payload["items"] == [{
        "session_id": "aws-live-sim-private",
        "engine_id": "steamer-card-engine.live-sim.private",
        "symbol": "2330.TW",
        "market_mode": "live(sim)",
        "freshness_state": "degraded",
    }]

    bootstrap = client.get("/api/observer/sessions/aws-live-sim-private/bootstrap")
    assert bootstrap.status_code == 200
    bootstrap_payload = bootstrap.json()
    assert bootstrap_payload["session_id"] == "aws-live-sim-private"
    assert bootstrap_payload["engine_id"] == "steamer-card-engine.live-sim.private"
    assert bootstrap_payload["chart"]["candles"]
    assert bootstrap_payload["timeline"]

    candles = client.get("/api/observer/sessions/aws-live-sim-private/candles?limit=2")
    assert candles.status_code == 200
    assert len(candles.json()["items"]) == 2

    timeline = client.get("/api/observer/sessions/aws-live-sim-private/timeline?limit=3")
    assert timeline.status_code == 200
    assert len(timeline.json()["items"]) == 3

    with client.websocket_connect("/api/observer/sessions/aws-live-sim-private/stream?after_seq=14") as websocket:
        first = websocket.receive_json()
        second = websocket.receive_json()
        third = websocket.receive_json()

    assert first["seq"] == 15
    assert second["seq"] == 16
    assert third == {"type": "stream_end", "after_seq": 14}

    monkeypatch.delenv("STEAMER_OBSERVER_BUNDLE_JSON", raising=False)
    monkeypatch.delenv("STEAMER_OBSERVER_INCLUDE_MOCK", raising=False)
    reset_observer_repository_cache()


def test_dashboard_fixture_dates_include_recent_manual_live_days() -> None:
    items = list_fixture_dates()
    assert items

    dates = [item["date"] for item in items]
    assert dates == sorted(dates, reverse=True)
    assert len(dates) == len(set(dates))

    assert items[0]["hero"] is True
    assert all(not item["hero"] for item in items[1:])


def test_dashboard_bundle_truthful_empty_transaction_state() -> None:
    bundle = build_day_bundle("2026-03-12")

    assert bundle["daily_summary"]["compare_status"] == "pass"
    assert bundle["transaction_surface"]["empty_state_metadata"]["state"] == "empty"
    assert bundle["compare"]["counts"]["fills"]["baseline"] == 0
    assert bundle["compare"]["counts"]["fills"]["candidate"] == 0
    assert bundle["daily_summary"]["dominant_lane"] == "steamer-card-engine"
    assert bundle["strategy_card_summaries"]
    assert bundle["phase_truth_summary"]["candidate"]["contract_violation_count"] > 0
    assert bundle["phase_truth_summary"]["candidate"]["phase_classifier"] == "twse-session-phase/v1"
    assert "open_discovery_summary" in bundle["phase_truth_summary"]["candidate"]


def test_dashboard_builds_recent_manual_live_bundle_truthfully() -> None:
    bundle = build_day_bundle("2026-04-08")

    assert bundle["daily_summary"]["compare_status"] == "pass"
    assert bundle["daily_summary"]["scenario_id"].startswith("tw-live-sim.twse.2026-04-08.")
    assert bundle["fixture"]["comparison_relpath"].startswith("comparisons/manual-live-paired-20260408")

    truth_contract = bundle["fixture"]["truth_contract"]
    assert truth_contract["hero_day"] == truth_contract["available_fixture_dates"][0]
    assert "2026-04-08" in truth_contract["available_fixture_dates"]

    assert bundle["transaction_surface"]["empty_state_metadata"]["state"] == "empty"
    assert bundle["compare"]["scaffold_placeholders"] == {}
    assert bundle["event_timeline"]


def test_dashboard_surfaces_configured_cards_even_without_activity() -> None:
    bundle = build_day_bundle("2026-04-09")
    strategy_cards = bundle["deck_view"]["strategy"]["cards"]

    assert strategy_cards
    candidate_cards = [row for row in strategy_cards if row["lane"] == "steamer-card-engine"]
    assert candidate_cards
    assert any(row["activity_state"] == "configured-no-activity" for row in candidate_cards)
    assert any(row["card_id"] == "legacy-baseline-card" for row in strategy_cards)


def test_dashboard_flags_pre_open_execution_attempts_as_phase_violations() -> None:
    bundle = build_day_bundle("2026-03-12")

    violation_rows = [
        item for item in bundle["event_timeline"] if item["kind"] == "execution-phase-violation"
    ]

    assert violation_rows
    assert any("pre_open_trial_match" in row["subtitle"] for row in violation_rows)
    assert all(row["status"] == "warn" for row in violation_rows)


def test_strategy_powerhouse_view_surfaces_local_research_truth() -> None:
    surface = build_strategy_powerhouse_view()

    assert surface["boundary"]["execution_authority"] == "none"
    assert surface["proposal"]["proposal_state"] == "proposed-not-active"
    assert surface["metrics"]["card_count"] == 3
    assert surface["architecture_map"]["stages"]
    assert any(stage["stage_id"] == "verifier-run" for stage in surface["architecture_map"]["stages"])
    assert surface["focus_lines"]
    assert any(line["line_id"] == "intraday_failed_auction_short" for line in surface["focus_lines"])
    assert surface["glossary"]
    assert any(item["zh"] == "驗證執行器" for item in surface["glossary"])

    root = repo_root()
    workspace_root = root.parent

    index = build_strategy_history_source_index(
        repo=root,
        family_ids=[
            "tw_vcp_dryup_reclaim",
            "tw_orb_reclaim_long",
            "tw_gap_reclaim_long",
        ],
    )

    proposal_payload = _load_json(index.proposal_plan_path)
    active_payload = _load_json(index.active_plan_path) if index.active_plan_path.exists() else None

    active_truth_state = "present"
    active_targets = list((active_payload or {}).get("targets") or [])
    if active_payload is None:
        active_truth_state = "missing"
    elif not active_targets:
        active_truth_state = "empty"

    assert surface["baton_line"]["active"]["truth_state"] == active_truth_state
    assert surface["baton_line"]["active"]["family"] == (active_payload.get("family") if active_payload else None)
    assert surface["baton_line"]["active"]["prepared_at"] == (active_payload.get("prepared_at") if active_payload else None)
    assert surface["baton_line"]["active"]["source_packet"] == _safe_relpath(
        workspace_root,
        active_payload.get("source_packet") if active_payload else None,
    )

    assert surface["baton_line"]["proposal"]["family"] == proposal_payload.get("family")
    assert surface["baton_line"]["proposal"]["prepared_at"] == proposal_payload.get("prepared_at")

    expected_active_labels = _target_labels(workspace_root, active_payload)
    expected_proposal_labels = _target_labels(workspace_root, proposal_payload)
    assert surface["baton_line"]["active"]["target_labels"] == expected_active_labels
    assert surface["baton_line"]["proposal"]["target_labels"] == expected_proposal_labels

    expected_divergence_state = "unknown"
    expected_family_differs = bool(proposal_payload.get("family"))
    expected_target_differs = bool(proposal_payload.get("targets"))
    if active_truth_state == "present":
        expected_family_differs = str(active_payload.get("family") or "") != str(proposal_payload.get("family") or "")
        active_ids = {str(item.get("variant_id")) for item in (active_payload.get("targets") or [])}
        proposal_ids = {str(item.get("variant_id")) for item in (proposal_payload.get("targets") or [])}
        expected_target_differs = active_ids != proposal_ids
        expected_divergence_state = "diverged" if (expected_family_differs or expected_target_differs) else "aligned"

    assert surface["baton_line"]["divergence"]["state"] == expected_divergence_state
    assert surface["baton_line"]["divergence"]["family_differs"] is expected_family_differs
    assert surface["baton_line"]["divergence"]["target_differs"] is expected_target_differs

    activation = surface["baton_line"].get("activation")
    assert activation is not None
    assert activation["plan_state"] in {"activated", "prepared-only", "unknown"}
    if active_truth_state != "present":
        assert activation["plan_state"] == "unknown"
    else:
        assert activation["plan_state"] == ("activated" if expected_divergence_state == "aligned" else "prepared-only")

    activation_latest_path = workspace_root / STATE_RELATIVE_PATH / "activation_latest.json"
    if activation_latest_path.exists():
        latest_payload = _load_json(activation_latest_path)
        latest = activation["latest"]
        assert activation["latest_pointer_present"] is True
        assert latest is not None
        assert latest["activation_state"] == latest_payload.get("activation_state")
        assert latest["effective_scope"] == latest_payload.get("runtime_window", {}).get("effective_scope")
        assert latest["effective_run_day"] == latest_payload.get("runtime_window", {}).get("effective_run_day")
        assert latest["note"] == latest_payload.get("runtime_window", {}).get("note")
        assert latest["receipt"] == _safe_relpath(workspace_root, latest_payload.get("receipt"))


def test_strategy_history_source_index_indexes_current_three_families() -> None:
    index = build_strategy_history_source_index(
        repo=repo_root(),
        family_ids=[
            "tw_vcp_dryup_reclaim",
            "tw_orb_reclaim_long",
            "tw_gap_reclaim_long",
        ],
    )

    assert re.fullmatch(r"\d{8}", index.proposal_day)
    assert index.proposal_plan_path.exists()
    assert index.active_plan_path.name == "active_deck_plan.json"

    packet_source = index.global_source("packet")
    assert packet_source is not None
    assert packet_source.primary_path is not None
    assert packet_source.primary_path.exists()
    assert packet_source.primary_path.name.endswith("_distinct_families_morning_packet.md")

    verifier_source = index.global_source("verifier")
    assert verifier_source is not None
    assert verifier_source.json_path is not None
    assert verifier_source.json_path.exists()
    assert verifier_source.json_path.name.endswith("_distinct_families_synthetic_verifier.json")

    kinds = {item.kind for item in index.sources_for_family("tw_vcp_dryup_reclaim")}
    assert {"proposal", "packet", "backtest"}.issubset(kinds)


def test_strategy_pipeline_view_surfaces_line_state_and_handoff_gate() -> None:
    surface = build_strategy_pipeline_view()

    assert surface["summary"]["verdict"] == "research-autonomous-no / attach-autonomous-no"
    assert surface["line_state"]["line_id"] == "intraday_failed_auction_short"
    assert surface["canon_flow"]
    assert any(stage["stage_id"] == "verifier-run" for stage in surface["canon_flow"])
    assert surface["components"]
    assert any(component["component_id"] == "live-sim-execution" for component in surface["components"])
    assert surface["autonomous_drivers"]
    assert any(driver["driver_id"] == "runtime-activation" for driver in surface["autonomous_drivers"])
    assert surface["handoff_gate"]["state"] == "blocked"
    assert surface["campaign_state"]["campaign_id"] == "2026-03-tw-intraday-shadow-vcp"
    assert surface["campaign_state"]["dispatchable"] is False
    assert surface["campaign_state"]["research_autonomous"] is False
    assert surface["campaign_state"]["attach_autonomous"] is False
    assert surface["campaign_state"]["runtime_dispatch"]["state"] == "misconfigured_activation"
    assert surface["campaign_state"]["selection"]["policy"] in {"runtime_dispatch", "runtime_fallback", "runtime_target_missing", "index_default", "index_fallback", "runtime_selector_v1/activation_target_not_dispatchable"}
    assert surface["campaign_state"]["selection"]["policy_id"].startswith("runtime_selector_v1/")
    assert isinstance(surface["campaign_state"]["selection"].get("candidate_set"), list)
    assert surface["control_plane"]["runtime_dispatch"]["campaign_id"] == "2026-03-tw-intraday-shadow-vcp"
    assert surface["control_plane"]["runtime_dispatch"]["suggested_campaign_id"] == "2026-04-timesfm-regime-rank-assist"
    assert surface["control_plane"]["runtime_campaign_selection"]["selected_campaign_id"] == "2026-03-tw-intraday-shadow-vcp"
    assert surface["campaign_state"]["runtime_dispatch"]["fallback_used"] is False
    assert surface["campaign_state"]["runtime_dispatch"]["activation_mismatch"] is True
    assert surface["sources"]


def test_strategy_powerhouse_view_explicitly_flags_missing_active_plan_truth(tmp_path: Path) -> None:
    real_repo = repo_root()
    workspace_root = tmp_path
    repo = workspace_root / "steamer-card-engine"
    repo.mkdir()

    (repo / "examples").symlink_to(real_repo / "examples", target_is_directory=True)
    (workspace_root / "StrategyExecuter_Steamer-Antigravity").symlink_to(
        real_repo.parent / "StrategyExecuter_Steamer-Antigravity",
        target_is_directory=True,
    )

    state_dir = workspace_root / STATE_RELATIVE_PATH
    state_dir.mkdir(parents=True)
    proposal_matches = sorted((real_repo.parent / STATE_RELATIVE_PATH).glob("proposed_distinct_families_*.json"))
    assert proposal_matches
    proposal_path = proposal_matches[-1]
    shutil.copy2(proposal_path, state_dir / proposal_path.name)

    surface = build_strategy_powerhouse_view(repo)

    assert surface["baton_line"]["active"]["truth_state"] == "missing"
    assert surface["baton_line"]["active"]["family"] is None
    assert surface["baton_line"]["active"]["targets"] == []
    assert surface["baton_line"]["handoff_readiness"]["state"] == "active-truth-missing"
    assert surface["baton_line"]["divergence"]["state"] == "unknown"
    assert surface["baton_line"]["breadcrumb"]["state"] == "unknown"
    assert surface["baton_line"]["breadcrumb"]["last_baton_source"]["label"] == "unknown / not indexed"
    assert surface["baton_line"]["breadcrumb"]["divergence_freshness"]["state"] == "unknown"
    assert "missing or empty" in surface["baton_line"]["divergence"]["note"]
    assert "do not replace the active paired lane" in surface["baton_line"]["handoff_readiness"]["summary"]

    activation = surface["baton_line"].get("activation")
    assert activation is not None
    assert activation["plan_state"] == "unknown"


def test_dashboard_api_routes() -> None:
    client = TestClient(create_app())

    dates_response = client.get("/api/dates")
    assert dates_response.status_code == 200
    latest_date = dates_response.json()[0]["date"]

    assert dates_response.json()[0]["hero"] is True

    deck_response = client.get("/api/days/2026-03-10/deck")
    assert deck_response.status_code == 200
    deck_payload = deck_response.json()
    assert deck_payload["cover"]["scenario_id"] == "tw-paper-sim.twse.2026-03-10.full-session"
    assert deck_payload["universe"]["calendar"] == "TWSE"
    assert deck_payload["strategy"]["cards"]

    summary_response = client.get("/api/days/2026-03-10/summary")
    assert summary_response.status_code == 200
    assert summary_response.json()["scenario_id"] == "tw-paper-sim.twse.2026-03-10.full-session"

    cards_response = client.get("/api/days/2026-03-10/cards")
    assert cards_response.status_code == 200
    assert cards_response.json()[0]["card_id"] == "legacy-baseline-card"

    card_detail_response = client.get(
        "/api/days/2026-03-10/lanes/steamer-card-engine/cards/legacy-baseline-card"
    )
    assert card_detail_response.status_code == 200
    assert card_detail_response.json()["counts"]["intents"] > 0

    compare_response = client.get("/api/days/2026-03-10/compare")
    assert compare_response.status_code == 200
    assert compare_response.json()["status"] == "pass"

    events_response = client.get("/api/days/2026-03-10/events")
    assert events_response.status_code == 200
    assert events_response.json()["event_timeline"]

    transactions_response = client.get("/api/days/2026-03-10/transactions")
    assert transactions_response.status_code == 200
    assert transactions_response.json()["empty_state_metadata"]["state"] == "empty"

    snapshot_response = client.get("/api/days/2026-03-10/snapshots/scenario")
    assert snapshot_response.status_code == 200
    assert snapshot_response.json()["payload"]["scenario_id"] == "tw-paper-sim.twse.2026-03-10.full-session"

    strategy_powerhouse_response = client.get("/api/strategy-powerhouse")
    assert strategy_powerhouse_response.status_code == 200
    strategy_payload = strategy_powerhouse_response.json()
    assert strategy_payload["metrics"]["card_count"] == 3
    assert strategy_payload["cards"][0]["family_timeline"]
    assert "activation" in strategy_payload["baton_line"]
    assert strategy_payload["architecture_map"]["stages"]
    assert strategy_payload["focus_lines"]
    assert strategy_payload["glossary"]

    strategy_pipeline_response = client.get("/api/strategy-pipeline")
    assert strategy_pipeline_response.status_code == 200
    pipeline_payload = strategy_pipeline_response.json()
    assert pipeline_payload["line_state"]["line_id"] == "intraday_failed_auction_short"
    assert pipeline_payload["components"]
    assert pipeline_payload["autonomous_drivers"]
    assert pipeline_payload["handoff_gate"]["state"] == "blocked"
    assert pipeline_payload["control_plane"]["runtime_dispatch"]["state"] == "misconfigured_activation"
    assert pipeline_payload["campaign_state"]["runtime_dispatch"]["state"] == "misconfigured_activation"
    assert pipeline_payload["control_plane"]["runtime_dispatch"]["suggested_campaign_id"] == "2026-04-timesfm-regime-rank-assist"
    assert pipeline_payload["campaign_state"]["runtime_dispatch"]["activation_mismatch"] is True
    assert pipeline_payload["control_plane"]["runtime_campaign_selection"]["selected_campaign_id"] == "2026-03-tw-intraday-shadow-vcp"
    assert pipeline_payload["control_plane"]["runtime_campaign_selection"].get("policy_id", "").startswith("runtime_selector_v1/")

    # Sanity: latest fixture date stays resolvable.
    latest_summary_response = client.get(f"/api/days/{latest_date}/summary")
    assert latest_summary_response.status_code == 200


def test_dashboard_api_404_for_unknown_day() -> None:
    client = TestClient(create_app())
    response = client.get("/api/days/1999-01-01/summary")
    assert response.status_code == 404


def test_observer_api_seed_routes_and_stream_reconcile_contract() -> None:
    client = TestClient(create_app())

    sessions_response = client.get("/api/observer/sessions")
    assert sessions_response.status_code == 200
    sessions = sessions_response.json()["items"]
    assert sessions
    session_id = sessions[0]["session_id"]

    bootstrap_response = client.get(f"/api/observer/sessions/{session_id}/bootstrap")
    assert bootstrap_response.status_code == 200
    bootstrap = bootstrap_response.json()
    assert bootstrap["schema_version"] == "observer.v0"
    assert bootstrap["latest_seq"] == 14
    assert bootstrap["chart"]["candles"]
    assert bootstrap["chart"]["markers"]
    assert len(bootstrap["timeline"]) == 12

    candles_response = client.get(f"/api/observer/sessions/{session_id}/candles?limit=3")
    assert candles_response.status_code == 200
    candles = candles_response.json()["items"]
    assert len(candles) == 3

    timeline_response = client.get(f"/api/observer/sessions/{session_id}/timeline?limit=5")
    assert timeline_response.status_code == 200
    timeline = timeline_response.json()["items"]
    assert len(timeline) == 5
    assert timeline[0]["seq"] >= timeline[-1]["seq"]

    unknown_bootstrap = client.get("/api/observer/sessions/unknown/bootstrap")
    assert unknown_bootstrap.status_code == 404

    with client.websocket_connect(f"/api/observer/sessions/{session_id}/stream?after_seq=14") as websocket:
        first_event = websocket.receive_json()
        second_event = websocket.receive_json()

    assert first_event["seq"] == 15
    assert first_event["event_type"] == "data_gap_detected"
    assert second_event["seq"] == 16
    assert second_event["event_type"] == "candle_bar"

    with client.websocket_connect(f"/api/observer/sessions/{session_id}/stream?after_seq=abc") as websocket:
        error_payload = websocket.receive_json()

    assert error_payload["type"] == "error"
    assert "invalid after_seq" in error_payload["detail"]


def test_observer_history_api_projects_sanitized_fixture_sessions() -> None:
    client = TestClient(create_app())

    response = client.get("/api/observer/history/sessions?limit=2")
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert payload["count"] <= 2

    first = payload["items"][0]
    assert first["session_id"].startswith("history-")
    assert first["market_mode"] == "replay-static"
    assert first["source_kind"] == "dashboard-fixture-static-projection"
    assert first["source_path_ref"].startswith("runs/steamer-card-engine/")
    assert "workspace" not in first["source_path_ref"]
    assert {"historical", "static", "generated"}.issubset(set(first["tags"]))

    bootstrap = client.get(f"/api/observer/history/sessions/{first['session_id']}/bootstrap")
    assert bootstrap.status_code == 200
    bootstrap_payload = bootstrap.json()
    assert bootstrap_payload["session_id"] == first["session_id"]
    assert bootstrap_payload["market_mode"] == "replay-static"
    assert bootstrap_payload["chart"]["candles"]
    assert bootstrap_payload["timeline"]
    assert bootstrap_payload["provenance"]["labels"] == ["historical", "static", "generated"]
    assert "workspace" not in bootstrap_payload["provenance"]["source_path_ref"]

    candles = client.get(f"/api/observer/history/sessions/{first['session_id']}/candles?limit=3")
    assert candles.status_code == 200
    candle_items = candles.json()["items"]
    assert len(candle_items) == 3
    assert len({item["time"] for item in candle_items}) == len(candle_items)

    bad_cursor = client.get(f"/api/observer/history/sessions/{first['session_id']}/candles?cursor=-1")
    assert bad_cursor.status_code == 400

    timeline = client.get(f"/api/observer/history/sessions/{first['session_id']}/timeline?limit=2")
    assert timeline.status_code == 200
    assert len(timeline.json()["items"]) == 2


def test_observer_history_api_not_found_and_compare_no_synthetic_metrics() -> None:
    client = TestClient(create_app())
    sessions = client.get("/api/observer/history/sessions?limit=2").json()["items"]
    assert len(sessions) >= 2

    missing = client.get("/api/observer/history/sessions/not-a-session/bootstrap")
    assert missing.status_code == 404

    compare = client.get(
        "/api/observer/history/compare",
        params={"left_session_id": sessions[0]["session_id"], "right_session_id": sessions[1]["session_id"]},
    )
    assert compare.status_code == 200
    payload = compare.json()
    assert payload["compare_available"] is False
    assert payload["status"] == "artifact_refs_only"
    assert "counts" not in payload
    assert payload["artifact_refs"]


def test_observer_history_skips_artifacts_outside_repo_root(tmp_path: Path) -> None:
    root = repo_root()
    outside = tmp_path / "external-bundle"
    outside.mkdir()
    fixture = FixtureDay(
        date="2026-01-01",
        comparison_dir=root / "comparisons" / "synthetic-compare",
        baseline_dir=root / "runs" / "baseline-bot" / "2026-01-01" / "baseline",
        candidate_dir=outside,
        baseline_run_id="baseline",
        candidate_run_id="candidate",
        compare_manifest=root / "comparisons" / "synthetic-compare" / "compare-manifest.json",
        diff=root / "comparisons" / "synthetic-compare" / "diff.json",
        summary=root / "comparisons" / "synthetic-compare" / "summary.md",
        compare_status="pass",
        compare_version="test",
        comparison_family="test",
    )

    assert _build_record(fixture, root) is None
