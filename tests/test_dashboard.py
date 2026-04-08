from __future__ import annotations

from fastapi.testclient import TestClient

from steamer_card_engine.dashboard import build_day_bundle, create_app, list_fixture_dates


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


def test_dashboard_api_404_for_unknown_day() -> None:
    client = TestClient(create_app())
    response = client.get("/api/days/2026-04-09/summary")
    assert response.status_code == 404
