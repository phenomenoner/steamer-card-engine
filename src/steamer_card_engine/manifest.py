from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import time
from pathlib import Path
from typing import Any
import tomllib

from steamer_card_engine.models import (
    AuthMode,
    AuthProfile,
    CapitalControls,
    CardManifest,
    CardRiskPolicy,
    DeckManifest,
    DeckPolicy,
    FinalAuctionFlattenPolicy,
    FlattenPolicy,
    ForcedExitWindow,
    GlobalConfig,
    GlobalRiskConfig,
    RecordingConfig,
    RiskThreshold,
)


CARD_STATUSES = {"draft", "replay-only", "operator-approved", "retired"}
AUTH_MODES = {"account_password_cert", "account_api_key_cert"}


class ManifestValidationError(ValueError):
    def __init__(self, manifest_type: str, path: Path, errors: list[str]) -> None:
        self.manifest_type = manifest_type
        self.path = path
        self.errors = errors
        joined = "\n".join(f"- {error}" for error in errors)
        super().__init__(f"Invalid {manifest_type} manifest: {path}\n{joined}")


def _load_toml(path: Path, manifest_type: str) -> dict[str, Any]:
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except FileNotFoundError as exc:
        raise ManifestValidationError(manifest_type, path, ["file not found"]) from exc
    except tomllib.TOMLDecodeError as exc:
        raise ManifestValidationError(manifest_type, path, [f"toml parse error: {exc}"]) from exc

    if not isinstance(data, dict):
        raise ManifestValidationError(manifest_type, path, ["top-level TOML object must be a table"])
    return data


def _require_str(payload: dict[str, Any], key: str, errors: list[str]) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"`{key}` must be a non-empty string")
        return ""
    return value.strip()


def _optional_str(payload: dict[str, Any], key: str, errors: list[str]) -> str | None:
    if key not in payload:
        return None
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    errors.append(f"`{key}` must be a non-empty string when set")
    return None


def _require_bool(payload: dict[str, Any], key: str, errors: list[str]) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        errors.append(f"`{key}` must be a boolean")
        return False
    return value


def _optional_bool(payload: dict[str, Any], key: str, default: bool, errors: list[str]) -> bool:
    if key not in payload:
        return default
    value = payload.get(key)
    if not isinstance(value, bool):
        errors.append(f"`{key}` must be a boolean when set")
        return default
    return value


def _require_positive_number(payload: dict[str, Any], key: str, errors: list[str]) -> float:
    value = payload.get(key)
    if not isinstance(value, (int, float)):
        errors.append(f"`{key}` must be a number")
        return 0.0
    if value <= 0:
        errors.append(f"`{key}` must be > 0")
        return float(value)
    return float(value)


def _optional_positive_number(
    payload: dict[str, Any], key: str, errors: list[str]
) -> float | None:
    if key not in payload:
        return None
    value = payload.get(key)
    if not isinstance(value, (int, float)):
        errors.append(f"`{key}` must be a number when set")
        return None
    if value <= 0:
        errors.append(f"`{key}` must be > 0 when set")
        return None
    return float(value)


def _require_int(payload: dict[str, Any], key: str, errors: list[str], minimum: int) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        errors.append(f"`{key}` must be an integer")
        return minimum
    if value < minimum:
        errors.append(f"`{key}` must be >= {minimum}")
    return value


def _require_table(payload: dict[str, Any], key: str, errors: list[str]) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        errors.append(f"`{key}` must be a table")
        return {}
    return value


def _optional_table(payload: dict[str, Any], key: str, errors: list[str]) -> dict[str, Any] | None:
    if key not in payload:
        return None
    value = payload.get(key)
    if not isinstance(value, dict):
        errors.append(f"`{key}` must be a table when set")
        return None
    return value


def _require_str_list(payload: dict[str, Any], key: str, errors: list[str]) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        errors.append(f"`{key}` must be an array of non-empty strings")
        return []
    cleaned = [item.strip() for item in value]
    if len(set(cleaned)) != len(cleaned):
        errors.append(f"`{key}` must not contain duplicates")
    return cleaned


def _parse_time(value: Any, key: str, errors: list[str]) -> time:
    if not isinstance(value, str):
        errors.append(f"`{key}` must be a HH:MM:SS string")
        return time(0, 0, 0)
    try:
        parsed = time.fromisoformat(value)
    except ValueError:
        errors.append(f"`{key}` must use HH:MM:SS format")
        return time(0, 0, 0)

    if parsed.tzinfo is not None:
        errors.append(f"`{key}` must not include timezone")
        return time(0, 0, 0)
    return parsed


def _ensure_credential_pair(
    *,
    payload: dict[str, Any],
    field: str,
    env_field: str,
    label: str,
    errors: list[str],
) -> tuple[str | None, str | None]:
    value = _optional_str(payload, field, errors)
    env_value = _optional_str(payload, env_field, errors)
    if not value and not env_value:
        errors.append(f"{label} requires either `{field}` or `{env_field}`")
    return value, env_value


def _parse_risk_threshold(payload: dict[str, Any], prefix: str, errors: list[str]) -> RiskThreshold:
    mode = _require_str(payload, "mode", errors)
    value = _require_positive_number(payload, "value", errors)
    if not mode:
        errors.append(f"`{prefix}.mode` must be set")
    return RiskThreshold(mode=mode, value=value)


def _to_primitive(value: Any) -> Any:
    if isinstance(value, time):
        return value.isoformat()
    if is_dataclass(value):
        return {key: _to_primitive(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _to_primitive(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_primitive(item) for item in value]
    return value


def to_dict(model: Any) -> dict[str, Any]:
    return _to_primitive(model)


def load_auth_profile(path: str | Path) -> AuthProfile:
    resolved = Path(path)
    errors: list[str] = []
    payload = _load_toml(resolved, "auth_profile")

    raw_mode = _require_str(payload, "mode", errors)
    mode: AuthMode | str = raw_mode
    if raw_mode not in AUTH_MODES:
        errors.append(f"`mode` must be one of {sorted(AUTH_MODES)}")

    account = _require_str(payload, "account", errors)
    cert_path, cert_path_env = _ensure_credential_pair(
        payload=payload,
        field="cert_path",
        env_field="cert_path_env",
        label="certificate path",
        errors=errors,
    )
    cert_password, cert_password_env = _ensure_credential_pair(
        payload=payload,
        field="cert_password",
        env_field="cert_password_env",
        label="certificate password",
        errors=errors,
    )

    password = _optional_str(payload, "password", errors)
    password_env = _optional_str(payload, "password_env", errors)
    api_key = _optional_str(payload, "api_key", errors)
    api_key_env = _optional_str(payload, "api_key_env", errors)

    if raw_mode == "account_password_cert":
        if not password and not password_env:
            errors.append("`account_password_cert` mode requires `password` or `password_env`")
        if api_key or api_key_env:
            errors.append("`account_password_cert` mode must not include api key fields")
    if raw_mode == "account_api_key_cert":
        if not api_key and not api_key_env:
            errors.append("`account_api_key_cert` mode requires `api_key` or `api_key_env`")
        if password or password_env:
            errors.append("`account_api_key_cert` mode must not include password fields")

    marketdata_enabled = _optional_bool(payload, "marketdata_enabled", True, errors)
    account_query_enabled = _optional_bool(payload, "account_query_enabled", True, errors)
    trade_enabled = _optional_bool(payload, "trade_enabled", False, errors)
    notes = _optional_str(payload, "notes", errors)

    if errors:
        raise ManifestValidationError("auth_profile", resolved, errors)

    return AuthProfile(
        mode=mode,
        account=account,
        cert_path=cert_path,
        cert_path_env=cert_path_env,
        cert_password=cert_password,
        cert_password_env=cert_password_env,
        password=password,
        password_env=password_env,
        api_key=api_key,
        api_key_env=api_key_env,
        marketdata_enabled=marketdata_enabled,
        account_query_enabled=account_query_enabled,
        trade_enabled=trade_enabled,
        notes=notes,
    )


def load_card_manifest(path: str | Path) -> CardManifest:
    resolved = Path(path)
    errors: list[str] = []
    payload = _load_toml(resolved, "card")

    card_id = _require_str(payload, "card_id", errors)
    name = _require_str(payload, "name", errors)
    version = _require_str(payload, "version", errors)
    strategy_family = _require_str(payload, "strategy_family", errors)
    status = _require_str(payload, "status", errors)
    if status and status not in CARD_STATUSES:
        errors.append(f"`status` must be one of {sorted(CARD_STATUSES)}")

    instrument_scope = _require_str_list(payload, "instrument_scope", errors)
    entry_module = _require_str(payload, "entry_module", errors)
    symbol_pool = _require_str_list(payload, "symbol_pool", errors)
    feature_requirements = _require_str_list(payload, "feature_requirements", errors)

    parameters = payload.get("parameters", {})
    if not isinstance(parameters, dict):
        errors.append("`parameters` must be a table")
        parameters = {}

    capital_controls_payload = _require_table(payload, "capital_controls", errors)
    capital_controls = CapitalControls(
        max_order_notional=_require_positive_number(
            capital_controls_payload, "max_order_notional", errors
        ),
        max_daily_notional=_require_positive_number(
            capital_controls_payload, "max_daily_notional", errors
        ),
        max_open_positions=_require_int(capital_controls_payload, "max_open_positions", errors, 1),
    )

    risk_payload = _require_table(payload, "risk_policy", errors)
    stop_loss_payload = _require_table(risk_payload, "stop_loss", errors)
    take_profit_payload = _require_table(risk_payload, "take_profit", errors)
    forced_exit_payload = _require_table(risk_payload, "forced_exit", errors)

    stop_loss = _parse_risk_threshold(stop_loss_payload, "risk_policy.stop_loss", errors)
    take_profit = _parse_risk_threshold(take_profit_payload, "risk_policy.take_profit", errors)

    forced_exit = ForcedExitWindow(
        start_time=_parse_time(forced_exit_payload.get("start_time"), "start_time", errors),
        end_time=_parse_time(forced_exit_payload.get("end_time"), "end_time", errors),
    )
    if forced_exit.start_time >= forced_exit.end_time:
        errors.append("`risk_policy.forced_exit.start_time` must be earlier than end_time")

    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("`metadata` must be a table when set")
        metadata = {}

    if errors:
        raise ManifestValidationError("card", resolved, errors)

    return CardManifest(
        card_id=card_id,
        name=name,
        version=version,
        strategy_family=strategy_family,
        instrument_scope=instrument_scope,
        status=status,
        entry_module=entry_module,
        symbol_pool=symbol_pool,
        feature_requirements=feature_requirements,
        parameters=parameters,
        capital_controls=capital_controls,
        risk_policy=CardRiskPolicy(
            stop_loss=stop_loss,
            take_profit=take_profit,
            forced_exit=forced_exit,
        ),
        metadata=metadata,
    )


def load_deck_manifest(path: str | Path) -> DeckManifest:
    resolved = Path(path)
    errors: list[str] = []
    payload = _load_toml(resolved, "deck")

    deck_id = _require_str(payload, "deck_id", errors)
    market = _require_str(payload, "market", errors)
    session = _require_str(payload, "session", errors)
    auth_profile = _require_str(payload, "auth_profile", errors)
    cards = _require_str_list(payload, "cards", errors)
    symbol_scope = _require_str_list(payload, "symbol_scope", errors)

    policy_payload = _optional_table(payload, "policy", errors) or {}
    policy = DeckPolicy(
        live_mode=_optional_bool(policy_payload, "live_mode", False, errors),
        allow_card_symbol_pool=_optional_bool(
            policy_payload, "allow_card_symbol_pool", True, errors
        ),
    )

    if errors:
        raise ManifestValidationError("deck", resolved, errors)

    return DeckManifest(
        deck_id=deck_id,
        market=market,
        session=session,
        auth_profile=auth_profile,
        cards=cards,
        symbol_scope=symbol_scope,
        policy=policy,
    )


def load_global_config(path: str | Path) -> GlobalConfig:
    resolved = Path(path)
    errors: list[str] = []
    payload = _load_toml(resolved, "global")

    market = _require_str(payload, "market", errors)
    session = _require_str(payload, "session", errors)
    live_enabled = _require_bool(payload, "live_enabled", errors)
    dry_run = _require_bool(payload, "dry_run", errors)
    market_data_adapter = _require_str(payload, "market_data_adapter", errors)
    broker_adapter = _require_str(payload, "broker_adapter", errors)
    auth_profile = _require_str(payload, "auth_profile", errors)
    active_account = _require_str(payload, "active_account", errors)

    recording_payload = _optional_table(payload, "recording", errors) or {}
    recording = RecordingConfig(
        enabled=_optional_bool(recording_payload, "enabled", True, errors),
        mode=_optional_str(recording_payload, "mode", errors) or "jsonl",
    )

    flatten_payload = _optional_table(payload, "flatten_policy", errors) or {}
    final_auction_payload = _optional_table(flatten_payload, "final_auction", errors)
    final_auction: FinalAuctionFlattenPolicy | None = None
    if final_auction_payload is not None:
        final_auction = FinalAuctionFlattenPolicy(
            enabled=_optional_bool(final_auction_payload, "enabled", False, errors),
            start_time=_parse_time(
                final_auction_payload.get("start_time"), "flatten_policy.final_auction.start_time", errors
            ),
            end_time=_parse_time(
                final_auction_payload.get("end_time"), "flatten_policy.final_auction.end_time", errors
            ),
            order_style=_require_str(final_auction_payload, "order_style", errors),
        )
        if final_auction.start_time >= final_auction.end_time:
            errors.append("`flatten_policy.final_auction.start_time` must be earlier than end_time")

    risk_payload = _optional_table(payload, "risk", errors) or {}
    emergency_payload = _optional_table(risk_payload, "emergency_stop", errors)
    emergency_stop: RiskThreshold | None = None
    if emergency_payload is not None:
        emergency_stop = _parse_risk_threshold(emergency_payload, "risk.emergency_stop", errors)

    risk = GlobalRiskConfig(
        max_daily_loss=_optional_positive_number(risk_payload, "max_daily_loss", errors),
        max_total_notional=_optional_positive_number(risk_payload, "max_total_notional", errors),
        emergency_stop=emergency_stop,
    )

    if errors:
        raise ManifestValidationError("global", resolved, errors)

    return GlobalConfig(
        market=market,
        session=session,
        live_enabled=live_enabled,
        dry_run=dry_run,
        market_data_adapter=market_data_adapter,
        broker_adapter=broker_adapter,
        auth_profile=auth_profile,
        active_account=active_account,
        recording=recording,
        flatten_policy=FlattenPolicy(final_auction=final_auction),
        risk=risk,
    )


def load_cards_from_dir(cards_dir: str | Path) -> dict[str, CardManifest]:
    directory = Path(cards_dir)
    cards: dict[str, CardManifest] = {}
    if not directory.exists() or not directory.is_dir():
        return cards

    for path in sorted(directory.glob("*.toml")):
        card = load_card_manifest(path)
        cards[card.card_id] = card
    return cards


def summarize_auth_profile(profile: AuthProfile) -> dict[str, Any]:
    auth_mode = "password+cert" if profile.mode == "account_password_cert" else "api_key+cert"
    return {
        "mode": profile.mode,
        "auth_mode_label": auth_mode,
        "account": profile.account,
        "marketdata_enabled": profile.marketdata_enabled,
        "account_query_enabled": profile.account_query_enabled,
        "trade_enabled": profile.trade_enabled,
        "safety_boundary": "trade_disabled" if not profile.trade_enabled else "trade_enabled",
        "cert_source": "inline" if profile.cert_path else "env",
        "secret_sources": {
            "password": bool(profile.password or profile.password_env),
            "api_key": bool(profile.api_key or profile.api_key_env),
            "cert_password": bool(profile.cert_password or profile.cert_password_env),
        },
    }


def summarize_card_manifest(card: CardManifest) -> dict[str, Any]:
    return {
        "card_id": card.card_id,
        "name": card.name,
        "version": card.version,
        "status": card.status,
        "strategy_family": card.strategy_family,
        "entry_module": card.entry_module,
        "instrument_scope": card.instrument_scope,
        "symbol_pool": card.symbol_pool,
        "feature_requirements": card.feature_requirements,
        "parameter_keys": sorted(card.parameters.keys()),
        "capital_controls": to_dict(card.capital_controls),
        "risk_policy": to_dict(card.risk_policy),
    }


def summarize_deck_manifest(
    deck: DeckManifest,
    cards_by_id: dict[str, CardManifest] | None = None,
) -> dict[str, Any]:
    cards_by_id = cards_by_id or {}
    missing_cards = [card_id for card_id in deck.cards if card_id not in cards_by_id]
    resolved_cards = [cards_by_id[card_id] for card_id in deck.cards if card_id in cards_by_id]

    merged_symbol_scope = set(deck.symbol_scope)
    merged_feature_requirements: set[str] = set()

    if deck.policy.allow_card_symbol_pool:
        for card in resolved_cards:
            merged_symbol_scope.update(card.symbol_pool)
            merged_feature_requirements.update(card.feature_requirements)

    return {
        "deck_id": deck.deck_id,
        "market": deck.market,
        "session": deck.session,
        "auth_profile": deck.auth_profile,
        "cards_total": len(deck.cards),
        "enabled_cards": deck.cards,
        "missing_cards": missing_cards,
        "symbol_scope": sorted(deck.symbol_scope),
        "merged_symbol_scope": sorted(merged_symbol_scope),
        "merged_feature_requirements": sorted(merged_feature_requirements),
        "policy": to_dict(deck.policy),
    }


def summarize_global_config(config: GlobalConfig) -> dict[str, Any]:
    final_auction = config.flatten_policy.final_auction
    final_auction_summary = None
    if final_auction:
        final_auction_summary = {
            "enabled": final_auction.enabled,
            "window": f"{final_auction.start_time.isoformat()}-{final_auction.end_time.isoformat()}",
            "order_style": final_auction.order_style,
        }

    risk_summary = {
        "max_daily_loss": config.risk.max_daily_loss,
        "max_total_notional": config.risk.max_total_notional,
        "emergency_stop": to_dict(config.risk.emergency_stop)
        if config.risk.emergency_stop
        else None,
    }

    return {
        "market": config.market,
        "session": config.session,
        "live_enabled": config.live_enabled,
        "dry_run": config.dry_run,
        "market_data_adapter": config.market_data_adapter,
        "broker_adapter": config.broker_adapter,
        "auth_profile": config.auth_profile,
        "active_account": config.active_account,
        "recording": to_dict(config.recording),
        "flatten_policy": {"final_auction": final_auction_summary},
        "risk": risk_summary,
    }
