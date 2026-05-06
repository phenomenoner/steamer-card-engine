from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runtime_chart import _normalize_symbol, _parse_date
from .runtime_sources import discover_runtime_run_roots, runtime_tick_sources
from .runtime_store import build_runtime_symbol_bars_from_store, runtime_store_date_updated_epoch


@dataclass(frozen=True)
class RuntimeFreshnessSnapshot:
    date: str
    symbol: str
    state: str
    raw_latest_tick_utc: str | None
    raw_latest_file_mtime_utc: str | None
    store_updated_at_utc: str | None
    api_latest_bar_utc: str | None
    lag_seconds: float | None
    source_count: int
    notes: list[str]

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _iso_from_epoch(epoch: float | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def _latest_tick_epoch_from_file(path: Path, symbol: str) -> float | None:
    from .runtime_chart import _parse_event_tick, _parse_recorded_tick
    import json

    latest: float | None = None
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", errors="replace") as file:
        for line in file:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload_body = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
            raw_symbol = _normalize_symbol(payload.get("symbol") or payload_body.get("symbol"))
            if raw_symbol != _normalize_symbol(symbol):
                continue
            tick = _parse_event_tick(line, symbol) if payload.get("event_type") == "market_tick" else _parse_recorded_tick(line, symbol)
            if tick is None:
                continue
            epoch = tick.time.astimezone(timezone.utc).timestamp()
            latest = epoch if latest is None else max(latest, epoch)
    return latest


def build_runtime_freshness_snapshot(root: Path, db_path: str | Path | None, date: str, symbol: str, lag_threshold_seconds: int = 300) -> RuntimeFreshnessSnapshot:
    compact = _parse_date(date)
    normalized_symbol = _normalize_symbol(symbol)
    raw_latest_tick: float | None = None
    raw_latest_mtime: float | None = None
    source_count = 0
    notes: list[str] = []
    for run_root in discover_runtime_run_roots(root, compact):
        for source in runtime_tick_sources(run_root.path, compact):
            if not source.exists():
                continue
            source_count += 1
            raw_latest_mtime = max(raw_latest_mtime or 0.0, source.stat().st_mtime)
            latest = _latest_tick_epoch_from_file(source, normalized_symbol)
            if latest is not None:
                raw_latest_tick = max(raw_latest_tick or 0.0, latest)
    store_updated = runtime_store_date_updated_epoch(db_path, compact) if db_path else None
    api_latest_bar: float | None = None
    if db_path:
        stored = build_runtime_symbol_bars_from_store(db_path, compact, normalized_symbol, timeframe="1m")
        if stored and stored.get("bars"):
            last_time = stored["bars"][-1].get("time")
            if isinstance(last_time, str):
                try:
                    api_latest_bar = datetime.fromisoformat(last_time.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
                except ValueError:
                    notes.append(f"invalid api latest bar time: {last_time}")
    lag_seconds = None
    state = "unknown"
    if raw_latest_tick is None:
        state = "no-raw-ticks"
    elif api_latest_bar is None:
        state = "import-missing"
        notes.append("raw ticks exist but runtime store has no API bars for this date/symbol")
    else:
        lag_seconds = max(0.0, raw_latest_tick - api_latest_bar)
        state = "lagging" if lag_seconds > lag_threshold_seconds else "fresh"
    if source_count == 0:
        notes.append("no tick sources discovered for date")
    return RuntimeFreshnessSnapshot(
        date=f"{compact[:4]}-{compact[4:6]}-{compact[6:]}",
        symbol=normalized_symbol,
        state=state,
        raw_latest_tick_utc=_iso_from_epoch(raw_latest_tick),
        raw_latest_file_mtime_utc=_iso_from_epoch(raw_latest_mtime),
        store_updated_at_utc=_iso_from_epoch(store_updated),
        api_latest_bar_utc=_iso_from_epoch(api_latest_bar),
        lag_seconds=lag_seconds,
        source_count=source_count,
        notes=notes,
    )
