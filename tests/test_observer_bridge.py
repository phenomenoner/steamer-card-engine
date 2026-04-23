from __future__ import annotations

import pytest

from steamer_card_engine.observer.bridge import (
    ObserverProjectionState,
    ObserverProjector,
    ObserverSessionMetadata,
    to_bar_time,
)
from steamer_card_engine.observer.mock import build_mock_observer_session


def test_observer_projector_rebuilds_bootstrap_from_snapshot_events() -> None:
    bundle = build_mock_observer_session()
    metadata = ObserverSessionMetadata(
        session_id=bundle.bootstrap.session_id,
        engine_id=bundle.bootstrap.engine_id,
        session_label=bundle.bootstrap.session_label,
        market_mode=bundle.bootstrap.market_mode,
        symbol=bundle.bootstrap.symbol,
        timeframe=bundle.bootstrap.timeframe,
    )
    projector = ObserverProjector(timeline_limit=12)

    rebuilt = projector.bootstrap_from_events(
        metadata,
        [event for event in bundle.events if event.seq <= bundle.bootstrap.latest_seq],
    )

    assert rebuilt.latest_seq == bundle.bootstrap.latest_seq
    assert rebuilt.freshness_state == bundle.bootstrap.freshness_state
    assert rebuilt.position == bundle.bootstrap.position
    assert rebuilt.health == bundle.bootstrap.health
    assert rebuilt.last_fill == bundle.bootstrap.last_fill
    assert rebuilt.open_orders == bundle.bootstrap.open_orders
    assert rebuilt.chart == bundle.bootstrap.chart
    assert rebuilt.timeline == bundle.bootstrap.timeline


def test_observer_bridge_normalizes_markers_to_bar_time() -> None:
    bundle = build_mock_observer_session()

    marker_times = [item["time"] for item in bundle.bootstrap.chart["markers"]]

    assert marker_times == ["2026-04-23T09:01:00Z", "2026-04-23T09:02:00Z"]
    assert to_bar_time("2026-04-23T09:03:25Z") == "2026-04-23T09:03:00Z"


def test_to_bar_time_rejects_invalid_timestamp_shape() -> None:
    with pytest.raises(ValueError):
        to_bar_time("bad")


def test_observer_projector_incremental_apply_matches_batch_and_rejects_duplicate_seq() -> None:
    bundle = build_mock_observer_session()
    metadata = ObserverSessionMetadata(
        session_id=bundle.bootstrap.session_id,
        engine_id=bundle.bootstrap.engine_id,
        session_label=bundle.bootstrap.session_label,
        market_mode=bundle.bootstrap.market_mode,
        symbol=bundle.bootstrap.symbol,
        timeframe=bundle.bootstrap.timeframe,
    )
    projector = ObserverProjector(timeline_limit=12)
    state = ObserverProjectionState()
    snapshot_events = [event for event in bundle.events if event.seq <= bundle.bootstrap.latest_seq]

    for event in snapshot_events:
        projector.apply(state, event)

    rebuilt = projector.bootstrap_from_events(metadata, snapshot_events)
    duplicate_event = snapshot_events[-1]
    projector.apply(state, duplicate_event)

    assert state.latest_seq == bundle.bootstrap.latest_seq
    assert rebuilt.chart == bundle.bootstrap.chart
    assert rebuilt.position == bundle.bootstrap.position
    assert rebuilt.open_orders == bundle.bootstrap.open_orders
    assert rebuilt.last_fill == bundle.bootstrap.last_fill
    assert rebuilt.health == bundle.bootstrap.health
    assert rebuilt.timeline == bundle.bootstrap.timeline


def test_observer_projector_health_and_gap_events_update_incidents_incrementally() -> None:
    bundle = build_mock_observer_session()
    projector = ObserverProjector(timeline_limit=12, incident_limit=12)
    state = ObserverProjectionState()

    for event in bundle.events:
        if event.seq in {11, 15}:
            projector.apply(state, event)

    assert "feed_lag_6s" in state.health.incidents
    assert "observer_gap_detected" in state.health.incidents
    assert state.health.feed_freshness_seconds == 11
    assert state.freshness_state == "degraded"
