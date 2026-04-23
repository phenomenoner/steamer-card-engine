from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache

from .bridge import ObserverProjector, ObserverSessionMetadata
from .schema import CandleBar, ObserverEvent, ObserverSessionBundle


def _event(
    seq: int,
    event_type: str,
    event_time: str,
    freshness_state: str,
    **partial_data,
) -> ObserverEvent:
    return ObserverEvent(
        schema_version="observer.v0",
        session_id="aws-live-sim-demo",
        engine_id="steamer-card-engine.live-sim",
        seq=seq,
        event_id=f"evt-{seq:04d}",
        event_type=event_type,
        event_time=event_time,
        ingest_time=event_time,
        partial_data=partial_data,
        freshness_state=freshness_state,
    )


@lru_cache(maxsize=1)
def build_mock_observer_session() -> ObserverSessionBundle:
    candles = [
        CandleBar(time="2026-04-23T09:00:00Z", open=142.4, high=142.8, low=142.2, close=142.7, volume=1200),
        CandleBar(time="2026-04-23T09:01:00Z", open=142.7, high=143.1, low=142.6, close=143.0, volume=1550),
        CandleBar(time="2026-04-23T09:02:00Z", open=143.0, high=143.4, low=142.9, close=143.3, volume=1710),
        CandleBar(time="2026-04-23T09:03:00Z", open=143.3, high=143.5, low=143.0, close=143.1, volume=1380),
        CandleBar(time="2026-04-23T09:04:00Z", open=143.1, high=143.6, low=143.0, close=143.5, volume=1880),
        CandleBar(time="2026-04-23T09:05:00Z", open=143.5, high=143.9, low=143.3, close=143.8, volume=2140),
    ]

    events = [
        _event(1, "session_started", "2026-04-23T08:59:58Z", "fresh", title="Session started", summary="Observer session opened for one live(sim) engine.", engine_state="healthy"),
        _event(2, "engine_state_changed", "2026-04-23T09:00:00Z", "fresh", title="Engine healthy", summary="Engine is attached to market feed and producing sanitized output.", engine_state="healthy"),
        _event(3, "candle_bar", "2026-04-23T09:00:00Z", "fresh", title="09:00 candle", summary="Opening minute closed.", candle=asdict(candles[0])),
        _event(4, "decision_recorded", "2026-04-23T09:01:10Z", "fresh", title="Long bias armed", summary="Coarse decision label only, no alpha internals.", decision_label="watch-long", confidence_band="operator-visible-medium"),
        _event(5, "order_submitted", "2026-04-23T09:01:15Z", "fresh", title="Buy order submitted", summary="Passive entry order submitted.", order={"order_id": "ord-001", "side": "buy", "quantity": 100, "limit_price": 143.05, "status": "submitted", "filled_quantity": 0, "submitted_at": "2026-04-23T09:01:15Z"}),
        _event(6, "order_acknowledged", "2026-04-23T09:01:16Z", "fresh", title="Buy order working", summary="Order acknowledged by broker sim.", order={"order_id": "ord-001", "side": "buy", "quantity": 100, "limit_price": 143.05, "status": "working", "filled_quantity": 0, "submitted_at": "2026-04-23T09:01:15Z"}),
        _event(7, "candle_bar", "2026-04-23T09:01:00Z", "fresh", title="09:01 candle", summary="Momentum continuation.", candle=asdict(candles[1])),
        _event(8, "fill_received", "2026-04-23T09:02:03Z", "fresh", title="Entry fill", summary="Entry fill received.", fill={"fill_id": "fill-001", "side": "buy", "quantity": 100, "price": 143.06, "filled_at": "2026-04-23T09:02:03Z"}),
        _event(9, "position_updated", "2026-04-23T09:02:04Z", "fresh", title="Long 100", summary="Position opened.", position={"side": "long", "quantity": 100, "avg_price": 143.06, "market_price": 143.3, "unrealized_pnl": 24.0, "realized_pnl": 0.0}),
        _event(10, "candle_bar", "2026-04-23T09:02:00Z", "fresh", title="09:02 candle", summary="Follow-through candle.", candle=asdict(candles[2])),
        _event(11, "health_alert", "2026-04-23T09:03:25Z", "lagging", title="Feed lag noticed", summary="Feed freshness degraded but observer still attached.", incident="feed_lag_6s", feed_freshness_seconds=6),
        _event(12, "candle_bar", "2026-04-23T09:03:00Z", "lagging", title="09:03 candle", summary="Minor pullback.", candle=asdict(candles[3])),
        _event(13, "operator_visible_note", "2026-04-23T09:04:10Z", "fresh", title="Position protected", summary="Protective stop moved to break-even band.", note="Protective logic updated; presentation-safe note only."),
        _event(14, "candle_bar", "2026-04-23T09:04:00Z", "fresh", title="09:04 candle", summary="Recovery candle.", candle=asdict(candles[4])),
        _event(15, "data_gap_detected", "2026-04-23T09:05:05Z", "degraded", title="Gap detected", summary="One heartbeat missed, recovery path engaged.", missing_seq_window="none", gap_seconds=11),
        _event(16, "candle_bar", "2026-04-23T09:05:00Z", "degraded", title="09:05 candle", summary="Observer remains coherent under degraded freshness.", candle=asdict(candles[5])),
    ]

    snapshot_seq = 14
    snapshot_events = [event for event in events if event.seq <= snapshot_seq]
    projector = ObserverProjector(timeline_limit=12)
    metadata = ObserverSessionMetadata(
        session_id="aws-live-sim-demo",
        engine_id="steamer-card-engine.live-sim",
        session_label="AWS live(sim) observer demo",
        market_mode="live(sim)",
        symbol="2330.TW",
        timeframe="1m",
    )
    bootstrap = projector.bootstrap_from_events(metadata, snapshot_events)
    return ObserverSessionBundle(bootstrap=bootstrap, candles=candles, events=events)


def list_mock_sessions() -> list[dict[str, str]]:
    bundle = build_mock_observer_session()
    return [{
        "session_id": bundle.bootstrap.session_id,
        "engine_id": bundle.bootstrap.engine_id,
        "symbol": bundle.bootstrap.symbol,
        "market_mode": bundle.bootstrap.market_mode,
        "freshness_state": bundle.bootstrap.freshness_state,
    }]


def observer_bootstrap_payload() -> dict:
    return build_mock_observer_session().bootstrap.to_dict()


def observer_candles_payload(limit: int = 500) -> dict:
    candles = build_mock_observer_session().candles[-limit:]
    return {
        "session_id": "aws-live-sim-demo",
        "items": [asdict(item) for item in candles],
    }


def observer_timeline_payload(limit: int = 200) -> dict:
    timeline = build_mock_observer_session().bootstrap.timeline[:limit]
    return {
        "session_id": "aws-live-sim-demo",
        "items": [asdict(item) for item in timeline],
    }


def observer_stream_events(after_seq: int = 0) -> list[dict]:
    events = [event.to_dict() for event in build_mock_observer_session().events if event.seq > after_seq]
    return events
