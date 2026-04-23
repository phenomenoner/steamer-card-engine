from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal


SchemaVersion = Literal["observer.v0"]
FreshnessState = Literal["fresh", "lagging", "stale", "degraded"]
ObserverEventType = Literal[
    "session_started",
    "candle_bar",
    "decision_recorded",
    "order_submitted",
    "order_acknowledged",
    "fill_received",
    "position_updated",
    "engine_state_changed",
    "health_alert",
    "data_gap_detected",
    "operator_visible_note",
    "session_ended",
]


@dataclass(frozen=True)
class CandleBar:
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class ChartMarker:
    time: str
    position: Literal["aboveBar", "belowBar", "inBar"]
    shape: Literal["arrowUp", "arrowDown", "circle", "square"]
    color: str
    text: str
    event_id: str


@dataclass(frozen=True)
class PositionSummary:
    side: Literal["flat", "long", "short"]
    quantity: int
    avg_price: float | None
    market_price: float | None
    unrealized_pnl: float | None
    realized_pnl: float | None


@dataclass(frozen=True)
class OrderSummary:
    order_id: str
    status: str
    side: str
    quantity: int
    limit_price: float | None
    filled_quantity: int
    submitted_at: str


@dataclass(frozen=True)
class FillSummary:
    fill_id: str
    side: str
    quantity: int
    price: float
    filled_at: str


@dataclass(frozen=True)
class HealthSummary:
    engine_state: str
    feed_freshness_seconds: int
    freshness_state: FreshnessState
    incidents: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TimelineEntry:
    seq: int
    event_time: str
    event_type: ObserverEventType
    title: str
    summary: str
    freshness_state: FreshnessState
    status: str


@dataclass(frozen=True)
class ObserverEvent:
    schema_version: SchemaVersion
    session_id: str
    engine_id: str
    seq: int
    event_id: str
    event_type: ObserverEventType
    event_time: str
    ingest_time: str
    partial_data: dict[str, Any]
    freshness_state: FreshnessState

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ObserverBootstrap:
    schema_version: SchemaVersion
    session_id: str
    engine_id: str
    session_label: str
    market_mode: str
    symbol: str
    timeframe: str
    generated_at: str
    latest_seq: int
    freshness_state: FreshnessState
    chart: dict[str, Any]
    position: PositionSummary
    open_orders: list[OrderSummary]
    last_fill: FillSummary | None
    health: HealthSummary
    timeline: list[TimelineEntry]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ObserverSessionBundle:
    bootstrap: ObserverBootstrap
    candles: list[CandleBar]
    events: list[ObserverEvent]


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
