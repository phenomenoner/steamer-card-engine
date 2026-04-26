from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
import json
import os
from pathlib import Path
import tomllib
from typing import Any

from .bridge import ObserverProjector, ObserverSessionMetadata
from .mock import build_mock_observer_session
from .schema import CandleBar, ObserverBootstrap, ObserverEvent, ObserverSessionBundle
from .timeframe import aggregate_candles, bootstrap_with_timeframe_chart, normalize_timeframe


def _coerce_symbol_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    symbols: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        symbol = item.strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return symbols


def _coerce_optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _bundle_pool_source_label(raw_source: str | None) -> str:
    if raw_source is None:
        return "observer-bundle-metadata"
    if raw_source.startswith("observer-bundle-metadata"):
        return raw_source
    return f"observer-bundle-metadata:{raw_source}"


def _load_fixture_or_deck_symbol_pool() -> tuple[list[str], str]:
    try:
        from steamer_card_engine.dashboard.fixtures import discover_fixture_days, repo_root
    except Exception:
        return ([], "observer-sessions-fallback")

    root = repo_root()
    fixtures = discover_fixture_days(root)
    for fixture in fixtures:
        scenario_spec_path = fixture.candidate_dir / "scenario-spec.json"
        if scenario_spec_path.exists():
            try:
                scenario_spec = json.loads(scenario_spec_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                scenario_spec = None
            if isinstance(scenario_spec, dict):
                symbol_set = scenario_spec.get("symbol_set")
                if isinstance(symbol_set, dict):
                    symbols = _coerce_symbol_list(symbol_set.get("symbols"))
                    if symbols:
                        return (symbols, "dashboard-fixture-symbol-set-sample")
                legacy_symbols = _coerce_symbol_list(scenario_spec.get("symbols"))
                if legacy_symbols:
                    return (legacy_symbols, "dashboard-fixture-symbol-list-sample")

        config_snapshot_path = fixture.candidate_dir / "config-snapshot.json"
        if not config_snapshot_path.exists():
            continue
        try:
            config_snapshot = json.loads(config_snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(config_snapshot, dict):
            continue
        deck_id = str(config_snapshot.get("deck_id") or "").strip()
        if not deck_id:
            continue
        deck_path = root / "examples" / "decks" / f"{deck_id}.toml"
        if not deck_path.exists():
            continue
        try:
            with deck_path.open("rb") as file:
                deck_payload = tomllib.load(file)
        except (OSError, tomllib.TOMLDecodeError):
            continue
        if not isinstance(deck_payload, dict):
            continue
        deck_symbols = _coerce_symbol_list(deck_payload.get("symbol_scope"))
        if deck_symbols:
            return (deck_symbols, "dashboard-deck-symbol-scope-sample")

    return ([], "observer-sessions-fallback")


class ObserverRepositoryError(RuntimeError):
    pass


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ObserverRepositoryError(f"observer bundle not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ObserverRepositoryError(f"observer bundle is not valid JSON: {path}") from error


def _metadata_from_payload(payload: dict, path: Path) -> ObserverSessionMetadata:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ObserverRepositoryError(f"observer bundle missing metadata object: {path}")
    try:
        return ObserverSessionMetadata(
            session_id=str(metadata["session_id"]),
            engine_id=str(metadata["engine_id"]),
            session_label=str(metadata["session_label"]),
            market_mode=str(metadata["market_mode"]),
            symbol=str(metadata["symbol"]),
            timeframe=str(metadata["timeframe"]),
            symbol_pool=_coerce_symbol_list(metadata.get("symbol_pool")),
            symbol_pool_source=_coerce_optional_text(metadata.get("symbol_pool_source")),
        )
    except KeyError as error:
        raise ObserverRepositoryError(f"observer bundle metadata missing field {error.args[0]!r}: {path}") from error


def _events_from_payload(payload: dict, path: Path) -> list[ObserverEvent]:
    events = payload.get("events")
    if not isinstance(events, list):
        raise ObserverRepositoryError(f"observer bundle missing events list: {path}")
    try:
        return [ObserverEvent(**item) for item in events if isinstance(item, dict)]
    except TypeError as error:
        raise ObserverRepositoryError(f"observer bundle has invalid event shape: {path}") from error


def _candles_from_payload(payload: dict, path: Path, events: list[ObserverEvent]) -> list[CandleBar]:
    candles = payload.get("candles")
    if candles is None:
        candle_rows = []
        for event in events:
            candle = event.partial_data.get("candle")
            if isinstance(candle, dict):
                candle_rows.append(CandleBar(**candle))
        return candle_rows
    if not isinstance(candles, list):
        raise ObserverRepositoryError(f"observer bundle candles must be a list when present: {path}")
    try:
        return [CandleBar(**item) for item in candles if isinstance(item, dict)]
    except TypeError as error:
        raise ObserverRepositoryError(f"observer bundle has invalid candle shape: {path}") from error


def _bootstrap_from_payload(
    payload: dict,
    path: Path,
    metadata: ObserverSessionMetadata,
    events: list[ObserverEvent],
) -> ObserverBootstrap:
    bootstrap = payload.get("bootstrap")
    if bootstrap is not None:
        if not isinstance(bootstrap, dict):
            raise ObserverRepositoryError(f"observer bundle bootstrap must be an object: {path}")
        try:
            return ObserverBootstrap(
                schema_version=bootstrap["schema_version"],
                session_id=bootstrap["session_id"],
                engine_id=bootstrap["engine_id"],
                session_label=bootstrap["session_label"],
                market_mode=bootstrap["market_mode"],
                symbol=bootstrap["symbol"],
                timeframe=bootstrap["timeframe"],
                generated_at=bootstrap["generated_at"],
                latest_seq=bootstrap["latest_seq"],
                freshness_state=bootstrap["freshness_state"],
                chart=bootstrap["chart"],
                position=payload_position(bootstrap.get("position")),
                open_orders=[payload_order(item) for item in bootstrap.get("open_orders") or []],
                last_fill=payload_fill(bootstrap.get("last_fill")),
                health=payload_health(bootstrap.get("health")),
                timeline=[payload_timeline(item) for item in bootstrap.get("timeline") or []],
            )
        except (KeyError, TypeError) as error:
            raise ObserverRepositoryError(f"observer bundle has invalid bootstrap shape: {path}") from error

    projector = ObserverProjector(timeline_limit=12)
    return projector.bootstrap_from_events(metadata, events)


def payload_position(value: object):
    from .schema import PositionSummary

    if not isinstance(value, dict):
        raise TypeError("position payload must be an object")
    return PositionSummary(**value)


def payload_order(value: object):
    from .schema import OrderSummary

    if not isinstance(value, dict):
        raise TypeError("order payload must be an object")
    return OrderSummary(**value)


def payload_fill(value: object):
    from .schema import FillSummary

    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("fill payload must be an object")
    return FillSummary(**value)


def payload_health(value: object):
    from .schema import HealthSummary

    if not isinstance(value, dict):
        raise TypeError("health payload must be an object")
    return HealthSummary(**value)


def payload_timeline(value: object):
    from .schema import TimelineEntry

    if not isinstance(value, dict):
        raise TypeError("timeline payload must be an object")
    return TimelineEntry(**value)


def load_bundle_from_json(path: Path) -> ObserverSessionBundle:
    payload = _load_json(path)
    metadata = _metadata_from_payload(payload, path)
    events = sorted(_events_from_payload(payload, path), key=lambda item: item.seq)
    candles = _candles_from_payload(payload, path, events)
    bootstrap = _bootstrap_from_payload(payload, path, metadata, events)

    if bootstrap.session_id != metadata.session_id:
        raise ObserverRepositoryError(f"observer bundle bootstrap/session metadata mismatch: {path}")
    if bootstrap.engine_id != metadata.engine_id:
        raise ObserverRepositoryError(f"observer bundle engine metadata mismatch: {path}")

    return ObserverSessionBundle(bootstrap=bootstrap, candles=candles, events=events, metadata=metadata)


class ObserverSessionRepository:
    def __init__(self, bundles: dict[str, ObserverSessionBundle]):
        self._bundles = bundles
        self._fixture_pool_symbols, self._fixture_pool_source = _load_fixture_or_deck_symbol_pool()

    def _bundle_metadata_symbol_pool(self) -> tuple[list[str], str] | None:
        seen: set[str] = set()
        merged_symbols: list[str] = []
        source_kinds: list[str] = []

        for bundle in self._bundles.values():
            metadata = bundle.metadata
            if metadata is None or not metadata.symbol_pool:
                continue
            for symbol in metadata.symbol_pool:
                normalized = str(symbol).strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                merged_symbols.append(normalized)
            source_label = _bundle_pool_source_label(metadata.symbol_pool_source)
            if source_label not in source_kinds:
                source_kinds.append(source_label)

        if not merged_symbols:
            return None
        if len(source_kinds) == 1:
            return merged_symbols, source_kinds[0]
        return merged_symbols, "observer-bundle-metadata:mixed"

    def list_sessions(self) -> list[dict[str, str]]:
        return [
            {
                "session_id": bundle.bootstrap.session_id,
                "engine_id": bundle.bootstrap.engine_id,
                "symbol": bundle.bootstrap.symbol,
                "market_mode": bundle.bootstrap.market_mode,
                "freshness_state": bundle.bootstrap.freshness_state,
            }
            for bundle in self._bundles.values()
        ]

    def list_sessions_payload(self) -> dict[str, Any]:
        items = self.list_sessions()
        fallback_symbols = sorted({item["symbol"] for item in items if isinstance(item.get("symbol"), str) and item["symbol"].strip()})

        metadata_pool = self._bundle_metadata_symbol_pool()
        if metadata_pool is not None:
            pool_symbols, source_kind = metadata_pool
        elif self._fixture_pool_symbols:
            pool_symbols = self._fixture_pool_symbols
            source_kind = self._fixture_pool_source
        else:
            pool_symbols = fallback_symbols
            source_kind = "observer-sessions-fallback"

        return {
            "items": items,
            "default_session_id": items[0]["session_id"] if items else None,
            "symbol_pool": {
                "source_kind": source_kind,
                "symbol_count": len(pool_symbols),
                "top_symbols": pool_symbols[:5],
                "sample_symbols": pool_symbols[:8],
            },
        }

    def require_bundle(self, session_id: str) -> ObserverSessionBundle:
        try:
            return self._bundles[session_id]
        except KeyError as error:
            raise KeyError(f"unknown observer session: {session_id}") from error

    def bootstrap_payload(self, session_id: str, timeframe: str = "auto") -> dict:
        bundle = self.require_bundle(session_id)
        return bootstrap_with_timeframe_chart(bundle.bootstrap.to_dict(), bundle.candles, timeframe)

    def candles_payload(self, session_id: str, limit: int = 500, timeframe: str = "auto") -> dict:
        bundle = self.require_bundle(session_id)
        normalized_timeframe = normalize_timeframe(timeframe)
        candles = aggregate_candles(bundle.candles, normalized_timeframe)
        limit = max(1, min(limit, 1000))
        return {
            "session_id": session_id,
            "timeframe": normalized_timeframe,
            "items": [asdict(item) for item in candles[-limit:]],
        }

    def timeline_payload(self, session_id: str, limit: int = 200) -> dict:
        bundle = self.require_bundle(session_id)
        limit = max(1, min(limit, 500))
        return {
            "session_id": session_id,
            "items": [asdict(item) for item in bundle.bootstrap.timeline[:limit]],
        }

    def stream_events(self, session_id: str, after_seq: int = 0) -> list[dict]:
        bundle = self.require_bundle(session_id)
        return [event.to_dict() for event in bundle.events if event.seq > after_seq]


@lru_cache(maxsize=1)
def observer_repository_from_env() -> ObserverSessionRepository:
    bundles: dict[str, ObserverSessionBundle] = {}

    include_mock = os.environ.get("STEAMER_OBSERVER_INCLUDE_MOCK", "1").strip().lower() not in {"0", "false", "no"}
    if include_mock:
        mock_bundle = build_mock_observer_session()
        bundles[mock_bundle.bootstrap.session_id] = mock_bundle

    raw_paths = os.environ.get("STEAMER_OBSERVER_BUNDLE_JSON", "").strip()
    for raw_path in [item.strip() for item in raw_paths.split(os.pathsep) if item.strip()]:
        path = Path(raw_path)
        bundle = load_bundle_from_json(path)
        bundles[bundle.bootstrap.session_id] = bundle

    return ObserverSessionRepository(bundles)


def reset_observer_repository_cache() -> None:
    observer_repository_from_env.cache_clear()
