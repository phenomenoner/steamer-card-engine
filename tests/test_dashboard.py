from __future__ import annotations

from pathlib import Path
import json
import re
import shutil
import tomllib

from fastapi.testclient import TestClient

from steamer_card_engine.dashboard import build_day_bundle, create_app, list_fixture_dates
from steamer_card_engine.dashboard.fixtures import repo_root
from steamer_card_engine.dashboard.history_source_index import STATE_RELATIVE_PATH, build_strategy_history_source_index
from steamer_card_engine.dashboard.strategy_powerhouse import build_strategy_powerhouse_view


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

    # Sanity: latest fixture date stays resolvable.
    latest_summary_response = client.get(f"/api/days/{latest_date}/summary")
    assert latest_summary_response.status_code == 200


def test_dashboard_api_404_for_unknown_day() -> None:
    client = TestClient(create_app())
    response = client.get("/api/days/1999-01-01/summary")
    assert response.status_code == 404
