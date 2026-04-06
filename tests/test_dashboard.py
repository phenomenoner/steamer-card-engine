from __future__ import annotations

from fastapi.testclient import TestClient

from steamer_card_engine.dashboard import build_day_bundle, create_app, list_fixture_dates


def test_dashboard_fixture_dates_match_truth_contract() -> None:
    dates = [item["date"] for item in list_fixture_dates()]
    assert dates == ["2026-03-12", "2026-03-10", "2026-03-06"]


def test_dashboard_bundle_truthful_empty_transaction_state() -> None:
    bundle = build_day_bundle("2026-03-12")

    assert bundle["daily_summary"]["compare_status"] == "pass"
    assert bundle["transaction_surface"]["empty_state_metadata"]["state"] == "empty"
    assert bundle["compare"]["counts"]["fills"]["baseline"] == 0
    assert bundle["compare"]["counts"]["fills"]["candidate"] == 0
    assert bundle["daily_summary"]["dominant_lane"] == "steamer-card-engine"
    assert bundle["strategy_card_summaries"]


def test_dashboard_api_routes() -> None:
    client = TestClient(create_app())

    dates_response = client.get("/api/dates")
    assert dates_response.status_code == 200
    assert dates_response.json()[0]["date"] == "2026-03-12"

    summary_response = client.get("/api/days/2026-03-10/summary")
    assert summary_response.status_code == 200
    assert summary_response.json()["scenario_id"] == "tw-paper-sim.twse.2026-03-10.full-session"

    cards_response = client.get("/api/days/2026-03-10/cards")
    assert cards_response.status_code == 200
    assert cards_response.json()[0]["card_id"] == "legacy-baseline-card"

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
    response = client.get("/api/days/2026-04-02/summary")
    assert response.status_code == 404
