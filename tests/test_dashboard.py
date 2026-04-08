from __future__ import annotations

from pathlib import Path
import shutil

from fastapi.testclient import TestClient

from steamer_card_engine.dashboard import build_day_bundle, create_app, list_fixture_dates
from steamer_card_engine.dashboard.fixtures import repo_root
from steamer_card_engine.dashboard.strategy_powerhouse import build_strategy_powerhouse_view


def test_dashboard_fixture_dates_include_recent_manual_live_days() -> None:
    dates = [item["date"] for item in list_fixture_dates()]

    assert dates == [
        "2026-04-08",
        "2026-04-02",
        "2026-04-01",
        "2026-03-31",
        "2026-03-30",
        "2026-03-27",
        "2026-03-26",
        "2026-03-25",
        "2026-03-24",
        "2026-03-20",
        "2026-03-12",
        "2026-03-10",
        "2026-03-06",
    ]


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
    assert bundle["fixture"]["truth_contract"]["hero_day"] == "2026-04-08"
    assert bundle["fixture"]["truth_contract"]["available_fixture_dates"][0] == "2026-04-08"
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
    assert surface["baton_line"]["active"]["truth_state"] == "present"
    assert surface["baton_line"]["active"]["family"] == "tw_vcp_dryup_plus_reclaim"
    assert surface["baton_line"]["active"]["target_labels"] == [
        "tw-cash-vcp-dryup-reclaim-s2 (tw_vcp_dryup_plus_reclaim_s2)",
        "tw-cash-vcp-dryup-reclaim-s5 (tw_vcp_dryup_plus_reclaim_s5)",
        "tw-cash-vcp-dryup-reclaim-s10 (tw_vcp_dryup_plus_reclaim_s10)",
    ]
    assert surface["baton_line"]["proposal"]["target_labels"] == [
        "tw-cash-vcp-dryup-reclaim-bounded (tw_vcp_dryup_reclaim_bounded)",
        "tw-cash-orb-reclaim-long-5m (tw_orb_reclaim_long_5m)",
        "tw-cash-gap-reclaim-long-3m (tw_gap_reclaim_long_3m)",
    ]
    assert surface["baton_line"]["handoff_readiness"]["state"] == "proposed-read-only"
    assert surface["baton_line"]["divergence"]["state"] == "diverged"
    assert surface["baton_line"]["divergence"]["family_differs"] is True
    assert surface["baton_line"]["divergence"]["target_differs"] is True
    assert "priority-1 observation proposal" in surface["baton_line"]["handoff_readiness"]["summary"]
    assert "HOLD until a recorded trigger exists beyond synthetic proof" in surface["baton_line"]["handoff_readiness"]["summary"]
    assert surface["metrics"]["card_count"] == 3
    assert surface["metrics"]["hold_count"] == 1
    assert surface["metrics"]["history_event_count"] >= 13
    assert surface["metrics"]["verifier_receipt_count"] == 3

    cards = {card["candidate_id"]: card for card in surface["cards"]}
    assert cards["tw_orb_reclaim_long_5m"]["status"] == "ready"
    assert cards["tw_gap_reclaim_long_3m"]["status"] == "synthetic-proven"
    assert cards["tw_vcp_dryup_reclaim_bounded"]["status"] == "hold"
    assert cards["tw_vcp_dryup_reclaim_bounded"]["current_gate"] == "needs-real-trigger"
    assert cards["tw_vcp_dryup_reclaim_bounded"]["latest_packet"]["kind"] == "gate-analysis"
    assert cards["tw_gap_reclaim_long_3m"]["validation_status"] == "synthetic-proven"
    assert cards["tw_gap_reclaim_long_3m"]["latest_packet"]["kind"] == "parameter-estimate"
    assert cards["tw_orb_reclaim_long_5m"]["verifier_history"][0]["status"] == "contract-only"
    assert any(event["kind"] == "plan" for event in cards["tw_gap_reclaim_long_3m"]["family_timeline"])
    assert any(link["kind"] == "verifier" for link in cards["tw_gap_reclaim_long_3m"]["related_links"])


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

    state_dir = workspace_root / ".state" / "steamer" / "card-engine-morning-paired-lane"
    state_dir.mkdir(parents=True)
    shutil.copy2(
        real_repo.parent
        / ".state"
        / "steamer"
        / "card-engine-morning-paired-lane"
        / "proposed_distinct_families_20260409.json",
        state_dir / "proposed_distinct_families_20260409.json",
    )

    surface = build_strategy_powerhouse_view(repo)

    assert surface["baton_line"]["active"]["truth_state"] == "missing"
    assert surface["baton_line"]["active"]["family"] is None
    assert surface["baton_line"]["active"]["targets"] == []
    assert surface["baton_line"]["handoff_readiness"]["state"] == "active-truth-missing"
    assert surface["baton_line"]["divergence"]["state"] == "unknown"
    assert "missing or empty" in surface["baton_line"]["divergence"]["note"]
    assert "do not replace the active paired lane" in surface["baton_line"]["handoff_readiness"]["summary"]


def test_dashboard_api_routes() -> None:
    client = TestClient(create_app())

    dates_response = client.get("/api/dates")
    assert dates_response.status_code == 200
    assert dates_response.json()[0]["date"] == "2026-04-08"
    assert dates_response.json()[0]["comparison_family"] == "manual-live-paired"

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
    assert strategy_payload["metrics"]["history_event_count"] >= 13
    assert strategy_payload["cards"][0]["family_timeline"]
    assert strategy_payload["baton_line"]["active"]["family"] == "tw_vcp_dryup_plus_reclaim"
    assert strategy_payload["baton_line"]["active"]["targets"][0]["deck_id"] == "tw-cash-vcp-dryup-reclaim-s2"
    assert strategy_payload["baton_line"]["proposal"]["targets"][0]["deck_id"] == "tw-cash-vcp-dryup-reclaim-bounded"
    assert strategy_payload["baton_line"]["handoff_readiness"]["state"] == "proposed-read-only"
    assert strategy_payload["baton_line"]["divergence"]["state"] == "diverged"


def test_dashboard_api_404_for_unknown_day() -> None:
    client = TestClient(create_app())
    response = client.get("/api/days/2026-04-09/summary")
    assert response.status_code == 404
