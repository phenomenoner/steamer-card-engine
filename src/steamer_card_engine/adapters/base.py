from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable, Literal


@dataclass(slots=True)
class MarketEvent:
    event_id: str
    symbol: str
    event_type: Literal["tick", "quote", "trade", "session"]
    last_price: float | None = None
    bid: float | None = None
    ask: float | None = None
    volume: float | None = None
    source: str = "unknown"


@dataclass(slots=True)
class ExecutionRequest:
    request_id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int
    order_type: str = "market"
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class BrokerReceipt:
    request_id: str
    status: str
    broker_order_id: str | None = None
    message: str = ""


class MarketDataAdapter(ABC):
    adapter_id: str

    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def subscribe(self, symbols: list[str]) -> None:
        pass

    @abstractmethod
    def unsubscribe(self, symbols: list[str]) -> None:
        pass

    @abstractmethod
    def iter_events(self) -> Iterable[MarketEvent]:
        pass


class BrokerAdapter(ABC):
    adapter_id: str

    @abstractmethod
    def submit(self, request: ExecutionRequest) -> BrokerReceipt:
        pass

    @abstractmethod
    def cancel(self, broker_order_id: str) -> BrokerReceipt:
        pass
