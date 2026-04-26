from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from steamer_card_engine.dashboard.fixtures import FixtureDay, discover_fixture_days, repo_root

from .bridge import ObserverProjector, ObserverSessionMetadata
from .bridge import to_bar_time
from .schema import CandleBar, ObserverEvent, ObserverSessionBundle
from .timeframe import aggregate_candles, bootstrap_with_timeframe_chart, normalize_timeframe


MAX_HISTORY_SESSIONS = 6
MAX_PROJECTED_TICKS = 80


class ObserverHistoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class HistorySessionRecord:
    session_id: str
    source_kind: str
    source_path_ref: str
    date: str
    generated_at: str
    engine_id: str
    session_label: str
    market_mode: str
    symbol: str
    timeframe: str
    scenario_id: str | None
    deck_id: str | None
    run_type: str
    freshness_state: str
    latest_seq: int
    event_count: int
    candle_count: int
    has_compare: bool
    tags: list[str]
    bundle: ObserverSessionBundle
    compare_ref: str | None

    def summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "source_kind": self.source_kind,
            "source_path_ref": self.source_path_ref,
            "date": self.date,
            "generated_at": self.generated_at,
            "engine_id": self.engine_id,
            "session_label": self.session_label,
            "market_mode": self.market_mode,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "scenario_id": self.scenario_id,
            "deck_id": self.deck_id,
            "run_type": self.run_type,
            "freshness_state": self.freshness_state,
            "latest_seq": self.latest_seq,
            "event_count": self.event_count,
            "candle_count": self.candle_count,
            "has_compare": self.has_compare,
            "tags": self.tags,
        }


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as file:
        return sum(1 for line in file if line.strip())


def _iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                yield json.loads(stripped)


def _resolved_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _safe_relpath(path: Path, root: Path) -> str:
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        return str(resolved.relative_to(root_resolved))
    except ValueError as error:
        raise ObserverHistoryError(f"history artifact path escapes repo root: {path}") from error


def _fixture_is_repo_local(fixture: FixtureDay, root: Path) -> bool:
    runs_root = root / "runs"
    comparisons_root = root / "comparisons"
    return (
        _resolved_under(fixture.candidate_dir, runs_root)
        and _resolved_under(fixture.baseline_dir, runs_root)
        and _resolved_under(fixture.comparison_dir, comparisons_root)
    )


def _pick_symbol_and_ticks(event_log: Path) -> tuple[str, list[dict[str, Any]]]:
    ticks: list[dict[str, Any]] = []
    preferred_symbol = "UNKNOWN"
    for row in _iter_jsonl(event_log) or []:
        if row.get("event_type") != "market_tick":
            continue
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        price = payload.get("price")
        symbol = str(row.get("symbol") or payload.get("symbol") or "").strip()
        if not symbol or not isinstance(price, (int, float)):
            continue
        if preferred_symbol == "UNKNOWN":
            preferred_symbol = symbol
        if symbol != preferred_symbol:
            continue
        ticks.append(row)
        if len(ticks) >= MAX_PROJECTED_TICKS:
            break
    return preferred_symbol, ticks


def _candles_from_ticks(ticks: list[dict[str, Any]]) -> list[CandleBar]:
    buckets: dict[str, list[tuple[float, int]]] = {}
    for row in ticks:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        price = payload.get("price")
        if not isinstance(price, (int, float)):
            continue
        timestamp = str(row.get("event_time_utc") or "")
        try:
            minute = to_bar_time(timestamp)
        except ValueError:
            continue
        size = int(payload.get("size") or payload.get("volume") or 0)
        buckets.setdefault(minute, []).append((float(price), size))

    candles: list[CandleBar] = []
    for minute, values in sorted(buckets.items()):
        prices = [price for price, _size in values]
        candles.append(
            CandleBar(
                time=minute,
                open=prices[0],
                high=max(prices),
                low=min(prices),
                close=prices[-1],
                volume=sum(size for _price, size in values),
            )
        )
    return candles


def _event(seq: int, session_id: str, engine_id: str, event_type: str, event_time: str, **partial_data: Any) -> ObserverEvent:
    return ObserverEvent(
        schema_version="observer.v0",
        session_id=session_id,
        engine_id=engine_id,
        seq=seq,
        event_id=f"hist-{session_id}-{seq:04d}",
        event_type=event_type,
        event_time=event_time,
        ingest_time=event_time,
        partial_data=partial_data,
        freshness_state="stale",
    )


def _build_record(fixture: FixtureDay, root: Path) -> HistorySessionRecord | None:
    if not _fixture_is_repo_local(fixture, root):
        return None

    bundle_dir = fixture.candidate_dir
    run_manifest = _load_json(bundle_dir / "run-manifest.json")
    scenario_spec = _load_json(bundle_dir / "scenario-spec.json")
    config = _load_json(bundle_dir / "config-snapshot.json")

    session_id = f"history-{fixture.date}-{fixture.candidate_run_id}"
    engine_id = "steamer-card-engine.history-static"
    run_type = str(run_manifest.get("run_type") or "live-sim")
    source_ref = _safe_relpath(bundle_dir, root)
    compare_ref = _safe_relpath(fixture.comparison_dir, root)
    symbol, ticks = _pick_symbol_and_ticks(bundle_dir / "event-log.jsonl")
    if not ticks:
        return None

    start_time = str(ticks[0].get("event_time_utc"))
    end_time = str(run_manifest.get("ended_at_utc") or ticks[-1].get("event_time_utc"))
    candles = _candles_from_ticks(ticks)
    if not candles:
        return None
    events: list[ObserverEvent] = [
        _event(
            1,
            session_id,
            engine_id,
            "session_started",
            start_time,
            title="Historical session loaded",
            summary="Static replay projected from a sanitized dashboard fixture bundle.",
            engine_state="historical-static",
        )
    ]
    for index, (row, candle) in enumerate(zip(ticks, candles), start=2):
        events.append(
            _event(
                index,
                session_id,
                engine_id,
                "candle_bar",
                candle.time,
                title=f"{symbol} tick projection",
                summary="Recorded market tick projected as an observer-compatible static candle.",
                candle=asdict(candle),
            )
        )
    events.append(
        _event(
            len(events) + 1,
            session_id,
            engine_id,
            "session_ended",
            end_time,
            title="Historical session ended",
            summary="Replay-static projection complete. No websocket or execution authority is attached.",
        )
    )

    metadata = ObserverSessionMetadata(
        session_id=session_id,
        engine_id=engine_id,
        session_label=f"{fixture.date} {run_type} replay history",
        market_mode="replay-static",
        symbol=symbol,
        timeframe="tick-projection",
    )
    projector = ObserverProjector(timeline_limit=20, candle_limit=MAX_PROJECTED_TICKS)
    bootstrap = projector.bootstrap_from_events(metadata, events)
    bundle = ObserverSessionBundle(bootstrap=bootstrap, candles=candles, events=events)

    event_count = _count_jsonl(bundle_dir / "event-log.jsonl")
    deck_id = config.get("deck_id")
    scenario_id = scenario_spec.get("scenario_id")
    return HistorySessionRecord(
        session_id=session_id,
        source_kind="dashboard-fixture-static-projection",
        source_path_ref=source_ref,
        date=fixture.date,
        generated_at=bootstrap.generated_at,
        engine_id=engine_id,
        session_label=metadata.session_label,
        market_mode=metadata.market_mode,
        symbol=symbol,
        timeframe=metadata.timeframe,
        scenario_id=str(scenario_id) if scenario_id is not None else None,
        deck_id=str(deck_id) if deck_id is not None else None,
        run_type=run_type,
        freshness_state=bootstrap.freshness_state,
        latest_seq=bootstrap.latest_seq,
        event_count=event_count,
        candle_count=len(candles),
        has_compare=True,
        tags=["historical", "static", "generated", fixture.compare_status, fixture.comparison_family],
        bundle=bundle,
        compare_ref=compare_ref,
    )


class ObserverHistoryRepository:
    def __init__(self, records: list[HistorySessionRecord]):
        self._records = sorted(records, key=lambda item: (item.date, item.session_id), reverse=True)
        self._by_id = {record.session_id: record for record in self._records}

    def list_sessions(self, limit: int = 20, cursor: str | None = None) -> dict[str, Any]:
        limit = max(1, min(limit, 50))
        start = 0
        if cursor:
            try:
                start = max(0, int(cursor))
            except ValueError as error:
                raise ObserverHistoryError(f"invalid cursor: {cursor}") from error
        end = start + limit
        items = [record.summary() for record in self._records[start:end]]
        return {"items": items, "next_cursor": str(end) if end < len(self._records) else None, "count": len(items), "total": len(self._records)}

    def require_record(self, session_id: str) -> HistorySessionRecord:
        try:
            return self._by_id[session_id]
        except KeyError as error:
            raise KeyError(f"unknown observer history session: {session_id}") from error

    def bootstrap_payload(self, session_id: str, timeframe: str = "auto") -> dict[str, Any]:
        record = self.require_record(session_id)
        payload = bootstrap_with_timeframe_chart(record.bundle.bootstrap.to_dict(), record.bundle.candles, timeframe)
        payload["provenance"] = {
            "source_kind": record.source_kind,
            "source_path_ref": record.source_path_ref,
            "compare_ref": record.compare_ref,
            "labels": ["historical", "static", "generated"],
        }
        return payload

    def _cursor_start(self, cursor: str | None) -> int:
        if cursor is None:
            return 0
        try:
            start = int(cursor)
        except ValueError as error:
            raise ObserverHistoryError(f"invalid cursor: {cursor}") from error
        if start < 0:
            raise ObserverHistoryError(f"invalid cursor: {cursor}")
        return start

    def candles_payload(self, session_id: str, limit: int = 500, cursor: str | None = None, timeframe: str = "auto") -> dict[str, Any]:
        record = self.require_record(session_id)
        normalized_timeframe = normalize_timeframe(timeframe)
        candles = aggregate_candles(record.bundle.candles, normalized_timeframe)
        limit = max(1, min(limit, 1000))
        start = self._cursor_start(cursor)
        end = start + limit
        items = candles[start:end]
        return {"session_id": session_id, "timeframe": normalized_timeframe, "items": [asdict(item) for item in items], "next_cursor": str(end) if end < len(candles) else None}

    def timeline_payload(self, session_id: str, limit: int = 200, cursor: str | None = None) -> dict[str, Any]:
        record = self.require_record(session_id)
        limit = max(1, min(limit, 500))
        start = self._cursor_start(cursor)
        timeline = sorted(record.bundle.bootstrap.timeline, key=lambda item: item.seq)
        end = start + limit
        items = timeline[start:end]
        return {"session_id": session_id, "items": [asdict(item) for item in items], "next_cursor": str(end) if end < len(timeline) else None}

    def compare_payload(self, left_session_id: str, right_session_id: str) -> dict[str, Any]:
        left = self.require_record(left_session_id)
        right = self.require_record(right_session_id)
        return {
            "status": "artifact_refs_only",
            "compare_available": False,
            "reason": "MVP exposes existing compare artifact references only; no synthetic deltas are generated.",
            "left": left.summary(),
            "right": right.summary(),
            "artifact_refs": [ref for ref in [left.compare_ref, right.compare_ref] if ref],
        }


@lru_cache(maxsize=1)
def observer_history_repository() -> ObserverHistoryRepository:
    root = repo_root()
    records: list[HistorySessionRecord] = []
    for fixture in discover_fixture_days(root)[:MAX_HISTORY_SESSIONS]:
        try:
            record = _build_record(fixture, root)
        except (OSError, json.JSONDecodeError, ObserverHistoryError, KeyError, ValueError):
            continue
        if record is not None:
            records.append(record)
    return ObserverHistoryRepository(records)


def reset_observer_history_repository_cache() -> None:
    observer_history_repository.cache_clear()
