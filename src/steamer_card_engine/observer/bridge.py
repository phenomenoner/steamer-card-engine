from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from .schema import (
    CandleBar,
    ChartMarker,
    FillSummary,
    HealthSummary,
    ObserverBootstrap,
    ObserverEvent,
    OrderSummary,
    PositionSummary,
    TimelineEntry,
)


def to_bar_time(value: str) -> str:
    if len(value) < 16 or "T" not in value:
        raise ValueError(f"invalid observer event_time for bar normalization: {value!r}")
    return f"{value[:16]}:00Z"


@dataclass(frozen=True)
class ObserverSessionMetadata:
    session_id: str
    engine_id: str
    session_label: str
    market_mode: str
    symbol: str
    timeframe: str
    symbol_pool: list[str] = field(default_factory=list)
    symbol_pool_source: str | None = None


@dataclass
class ObserverProjectionState:
    latest_seq: int = 0
    freshness_state: str = "fresh"
    generated_at: str = ""
    candles: list[CandleBar] = field(default_factory=list)
    markers: list[ChartMarker] = field(default_factory=list)
    position: PositionSummary = field(
        default_factory=lambda: PositionSummary(
            side="flat",
            quantity=0,
            avg_price=None,
            market_price=None,
            unrealized_pnl=None,
            realized_pnl=None,
        )
    )
    open_orders: list[OrderSummary] = field(default_factory=list)
    last_fill: FillSummary | None = None
    health: HealthSummary = field(
        default_factory=lambda: HealthSummary(
            engine_state="unknown",
            feed_freshness_seconds=0,
            freshness_state="fresh",
            incidents=[],
        )
    )
    timeline: list[TimelineEntry] = field(default_factory=list)


class ObserverProjector:
    def __init__(self, timeline_limit: int = 12, incident_limit: int = 12, candle_limit: int = 200):
        self.timeline_limit = timeline_limit
        self.incident_limit = incident_limit
        self.candle_limit = candle_limit

    def apply(self, state: ObserverProjectionState, event: ObserverEvent) -> None:
        if event.seq <= state.latest_seq:
            return

        state.latest_seq = event.seq
        state.freshness_state = event.freshness_state
        state.generated_at = event.event_time
        state.health = replace(state.health, freshness_state=event.freshness_state)

        timeline_entry = TimelineEntry(
            seq=event.seq,
            event_time=event.event_time,
            event_type=event.event_type,
            title=str(event.partial_data.get("title", event.event_type)),
            summary=str(event.partial_data.get("summary", "")),
            freshness_state=event.freshness_state,
            status="warn" if event.freshness_state in {"lagging", "stale", "degraded"} else "ok",
        )
        state.timeline = [timeline_entry, *state.timeline][: self.timeline_limit]

        if event.event_type == "candle_bar" and isinstance(event.partial_data.get("candle"), dict):
            candle = CandleBar(**event.partial_data["candle"])
            candle_map = {item.time: item for item in state.candles}
            candle_map[candle.time] = candle
            state.candles = sorted(candle_map.values(), key=lambda item: item.time)[-self.candle_limit :]
            if state.position.quantity:
                state.position = replace(state.position, market_price=candle.close)

        if event.event_type == "order_submitted" and isinstance(event.partial_data.get("order"), dict):
            order = OrderSummary(**event.partial_data["order"])
            state.open_orders = [order, *[item for item in state.open_orders if item.order_id != order.order_id]]
            state.markers = self._merge_marker(
                state.markers,
                ChartMarker(
                    time=to_bar_time(event.event_time),
                    position="aboveBar" if order.side == "sell" else "belowBar",
                    shape="arrowDown" if order.side == "sell" else "arrowUp",
                    color="#ff6b6b" if order.side == "sell" else "#5ef3b1",
                    text=f"{order.side.upper()} SUBMIT",
                    event_id=event.event_id,
                ),
            )

        if event.event_type == "order_acknowledged" and isinstance(event.partial_data.get("order"), dict):
            order = OrderSummary(**event.partial_data["order"])
            if any(item.order_id == order.order_id for item in state.open_orders):
                state.open_orders = [order if item.order_id == order.order_id else item for item in state.open_orders]

        if event.event_type == "fill_received" and isinstance(event.partial_data.get("fill"), dict):
            fill = FillSummary(**event.partial_data["fill"])
            state.last_fill = fill
            state.markers = self._merge_marker(
                state.markers,
                ChartMarker(
                    time=to_bar_time(event.event_time),
                    position="aboveBar" if fill.side == "sell" else "belowBar",
                    shape="circle",
                    color="#ffcd81" if fill.side == "sell" else "#80c2ff",
                    text=f"FILL {fill.quantity}",
                    event_id=event.event_id,
                ),
            )

        if event.event_type == "position_updated" and isinstance(event.partial_data.get("position"), dict):
            state.position = PositionSummary(**event.partial_data["position"])

        if event.event_type == "engine_state_changed":
            state.health = replace(
                state.health,
                engine_state=str(event.partial_data.get("engine_state", state.health.engine_state)),
            )

        if event.event_type == "health_alert":
            feed_age = event.partial_data.get("feed_freshness_seconds")
            if isinstance(feed_age, int):
                state.health = replace(state.health, feed_freshness_seconds=feed_age)
            incident = event.partial_data.get("incident")
            if isinstance(incident, str):
                state.health = replace(
                    state.health,
                    incidents=[*state.health.incidents, incident][-self.incident_limit :],
                )

        if event.event_type == "data_gap_detected":
            state.health = replace(
                state.health,
                incidents=[*state.health.incidents, "observer_gap_detected"][-self.incident_limit :],
            )
            gap_seconds = event.partial_data.get("gap_seconds")
            if isinstance(gap_seconds, int):
                state.health = replace(state.health, feed_freshness_seconds=gap_seconds)

    def bootstrap_from_events(
        self,
        metadata: ObserverSessionMetadata,
        events: list[ObserverEvent],
    ) -> ObserverBootstrap:
        state = ObserverProjectionState()
        for event in sorted(events, key=lambda item: item.seq):
            self.apply(state, event)

        last_price = state.position.market_price
        if last_price is None and state.candles:
            last_price = state.candles[-1].close

        return ObserverBootstrap(
            schema_version="observer.v0",
            session_id=metadata.session_id,
            engine_id=metadata.engine_id,
            session_label=metadata.session_label,
            market_mode=metadata.market_mode,
            symbol=metadata.symbol,
            timeframe=metadata.timeframe,
            generated_at=state.generated_at,
            latest_seq=state.latest_seq,
            freshness_state=state.freshness_state,
            chart={
                "candles": [self._asdict_candle(item) for item in state.candles],
                "markers": [self._asdict_marker(item) for item in state.markers],
                "position_band": {
                    "side": state.position.side,
                    "avg_price": state.position.avg_price,
                    "last_price": last_price,
                },
            },
            position=state.position,
            open_orders=state.open_orders,
            last_fill=state.last_fill,
            health=state.health,
            timeline=state.timeline,
        )

    @staticmethod
    def _merge_marker(markers: list[ChartMarker], marker: ChartMarker) -> list[ChartMarker]:
        merged = [*markers, marker]
        merged.sort(key=lambda item: (item.time, item.event_id))
        return merged

    @staticmethod
    def _asdict_candle(candle: CandleBar) -> dict[str, Any]:
        return {
            "time": candle.time,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }

    @staticmethod
    def _asdict_marker(marker: ChartMarker) -> dict[str, Any]:
        return {
            "time": marker.time,
            "position": marker.position,
            "shape": marker.shape,
            "color": marker.color,
            "text": marker.text,
            "event_id": marker.event_id,
        }
