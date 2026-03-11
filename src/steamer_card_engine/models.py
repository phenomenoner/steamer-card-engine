from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Any, Literal


IntentSide = Literal["buy", "sell", "cover", "reduce", "exit"]
IntentType = Literal["enter", "exit", "adjust", "cancel_request"]
CardStatus = Literal["draft", "replay-only", "operator-approved", "retired"]
AuthMode = Literal["account_password_cert", "account_api_key_cert"]


@dataclass(slots=True)
class Intent:
    intent_id: str
    card_id: str
    symbol: str
    side: IntentSide
    intent_type: IntentType
    reason: str
    confidence: float = 0.0
    size_hint: float | None = None
    tags: tuple[str, ...] = ()


@dataclass(slots=True)
class RiskThreshold:
    mode: str
    value: float


@dataclass(slots=True)
class ForcedExitWindow:
    start_time: time
    end_time: time


@dataclass(slots=True)
class CapitalControls:
    max_order_notional: float
    max_daily_notional: float
    max_open_positions: int


@dataclass(slots=True)
class CardRiskPolicy:
    stop_loss: RiskThreshold
    take_profit: RiskThreshold
    forced_exit: ForcedExitWindow


@dataclass(slots=True)
class CardManifest:
    card_id: str
    name: str
    version: str
    strategy_family: str
    instrument_scope: list[str]
    entry_module: str
    symbol_pool: list[str]
    feature_requirements: list[str]
    parameters: dict[str, Any]
    capital_controls: CapitalControls
    risk_policy: CardRiskPolicy
    status: CardStatus = "draft"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DeckPolicy:
    live_mode: bool = False
    allow_card_symbol_pool: bool = True


@dataclass(slots=True)
class DeckManifest:
    deck_id: str
    market: str
    session: str
    auth_profile: str
    cards: list[str]
    symbol_scope: list[str] = field(default_factory=list)
    policy: DeckPolicy = field(default_factory=DeckPolicy)


@dataclass(slots=True)
class AuthProfile:
    mode: AuthMode
    account: str
    cert_path: str | None = None
    cert_path_env: str | None = None
    cert_password: str | None = None
    cert_password_env: str | None = None
    password: str | None = None
    password_env: str | None = None
    api_key: str | None = None
    api_key_env: str | None = None
    marketdata_enabled: bool = True
    account_query_enabled: bool = True
    trade_enabled: bool = False
    notes: str | None = None


@dataclass(slots=True)
class RecordingConfig:
    enabled: bool = True
    mode: str = "jsonl"


@dataclass(slots=True)
class FinalAuctionFlattenPolicy:
    enabled: bool
    start_time: time
    end_time: time
    order_style: str


@dataclass(slots=True)
class FlattenPolicy:
    final_auction: FinalAuctionFlattenPolicy | None = None


@dataclass(slots=True)
class GlobalRiskConfig:
    max_daily_loss: float | None = None
    max_total_notional: float | None = None
    emergency_stop: RiskThreshold | None = None


@dataclass(slots=True)
class GlobalConfig:
    market: str
    session: str
    live_enabled: bool
    dry_run: bool
    market_data_adapter: str
    broker_adapter: str
    auth_profile: str
    active_account: str
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    flatten_policy: FlattenPolicy = field(default_factory=FlattenPolicy)
    risk: GlobalRiskConfig = field(default_factory=GlobalRiskConfig)
