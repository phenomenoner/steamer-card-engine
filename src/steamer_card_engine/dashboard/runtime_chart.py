from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from .fixtures import repo_root
from .runtime_sources import configured_runtime_root, discover_runtime_run_roots, runtime_tick_sources


@dataclass(frozen=True)
class Tick:
    time: datetime
    price: float
    size: float


def _parse_date(value: str) -> str:
    text = value.strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return text.replace("-", "")
    return text


def _normalize_symbol(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text[:-3] if text.endswith(".TW") else text


def _configured_runtime_root() -> Path | None:
    return configured_runtime_root()


def _runtime_run_roots(base_root: Path, date: str) -> list[Path]:
    return [item.path for item in discover_runtime_run_roots(base_root, date)]


def _event_logs_for_date(base_root: Path, date: str) -> list[Path]:
    logs: list[Path] = []
    for root in _runtime_run_roots(base_root, date):
        event_log = root / "event-log.jsonl"
        if event_log.exists():
            logs.append(event_log)
    return sorted(logs, key=lambda item: (item.stat().st_mtime, str(item)), reverse=True)


def _tick_logs_for_date(base_root: Path, date: str) -> list[Path]:
    logs: list[Path] = []
    for root in _runtime_run_roots(base_root, date):
        for candidate in runtime_tick_sources(root, date):
            if candidate.name == "event-log.jsonl":
                continue
            if candidate.exists():
                logs.append(candidate)
    return sorted(logs, key=lambda item: (item.stat().st_mtime, str(item)), reverse=True)


def _parse_event_tick(line: str, symbol: str) -> Tick | None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if event.get("event_type") != "market_tick":
        return None
    raw_symbol = _normalize_symbol(event.get("symbol") or event.get("payload", {}).get("symbol") or "")
    if raw_symbol != _normalize_symbol(symbol):
        return None
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    price = payload.get("price", event.get("price"))
    if price is None:
        return None
    try:
        parsed_price = float(price)
    except (TypeError, ValueError):
        return None
    size = payload.get("size", event.get("size", 0))
    try:
        parsed_size = float(size or 0)
    except (TypeError, ValueError):
        parsed_size = 0.0
    raw_time = str(event.get("event_time_utc") or payload.get("time") or "")
    if not raw_time:
        return None
    try:
        if raw_time.endswith("Z"):
            parsed_time = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        else:
            parsed_time = datetime.fromisoformat(raw_time)
    except ValueError:
        return None
    if parsed_time.tzinfo is None:
        parsed_time = parsed_time.replace(tzinfo=timezone.utc)
    return Tick(time=parsed_time.astimezone(timezone.utc), price=parsed_price, size=parsed_size)


def _parse_epoch_like_time(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    # Fubon websocket tick `time` is observed as epoch microseconds;
    # `ws_received_time` is epoch seconds with fractions. Keep this heuristic
    # bounded to common second/millisecond/microsecond/nanosecond scales.
    if numeric > 1_000_000_000_000_000_000:
        numeric = numeric / 1_000_000_000
    elif numeric > 1_000_000_000_000_000:
        numeric = numeric / 1_000_000
    elif numeric > 1_000_000_000_000:
        numeric = numeric / 1_000
    try:
        return datetime.fromtimestamp(numeric, timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def _parse_recorded_tick(line: str, symbol: str) -> Tick | None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    raw_symbol = _normalize_symbol(event.get("symbol") or "")
    if raw_symbol != _normalize_symbol(symbol):
        return None
    price = event.get("price")
    if price is None:
        return None
    try:
        parsed_price = float(price)
    except (TypeError, ValueError):
        return None
    try:
        parsed_size = float(event.get("size") or event.get("volume") or 0)
    except (TypeError, ValueError):
        parsed_size = 0.0
    parsed_time = _parse_epoch_like_time(event.get("time")) or _parse_epoch_like_time(event.get("ws_received_time"))
    if parsed_time is None:
        return None
    return Tick(time=parsed_time.astimezone(timezone.utc), price=parsed_price, size=parsed_size)


def _bucket_start(dt: datetime, timeframe: str) -> datetime:
    minutes = {"1m": 1, "5m": 5, "15m": 15}.get(timeframe, 1)
    minute = (dt.minute // minutes) * minutes
    return dt.replace(minute=minute, second=0, microsecond=0)


def _ticks_to_bars(ticks: list[Tick], timeframe: str) -> list[dict[str, Any]]:
    buckets: dict[datetime, list[Tick]] = {}
    for tick in sorted(ticks, key=lambda item: item.time):
        buckets.setdefault(_bucket_start(tick.time, timeframe), []).append(tick)
    bars: list[dict[str, Any]] = []
    for bucket, values in sorted(buckets.items()):
        prices = [item.price for item in values]
        bars.append(
            {
                "time": bucket.isoformat().replace("+00:00", "Z"),
                "open": prices[0],
                "high": max(prices),
                "low": min(prices),
                "close": prices[-1],
                "volume": sum(item.size for item in values),
                "tick_count": len(values),
            }
        )
    return bars


def _load_cached_bars(base_root: Path, compact_date: str, symbol: str, timeframe: str) -> dict[str, Any] | None:
    cache_path = base_root / "data" / "runtime-bars-cache" / compact_date / f"{symbol}-{timeframe}.json"
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    payload.setdefault("source_kind", "precomputed-runtime-event-log-market-tick")
    payload.setdefault("source_path", str(cache_path))
    return payload


def build_runtime_symbol_bars(
    date: str,
    symbol: str,
    timeframe: str = "1m",
    root: Path | None = None,
    max_ticks: int = 200_000,
) -> dict[str, Any]:
    base_root = root or repo_root()
    compact_date = _parse_date(date)
    normalized_symbol = _normalize_symbol(symbol)
    event_logs = _event_logs_for_date(base_root, compact_date)
    tick_logs = _tick_logs_for_date(base_root, compact_date)
    newest_file_mtime = max((path.stat().st_mtime for path in [*event_logs, *tick_logs]), default=0.0)
    store_path = os.getenv("STEAMER_DASHBOARD_RUNTIME_DB")
    if store_path:
        from .runtime_store import build_runtime_symbol_bars_from_store, runtime_store_date_updated_epoch

        stored = build_runtime_symbol_bars_from_store(store_path, compact_date, normalized_symbol, timeframe=timeframe, max_ticks=max_ticks)
        store_updated_at = runtime_store_date_updated_epoch(store_path, compact_date) or 0.0
        if stored is not None and store_updated_at >= newest_file_mtime:
            return stored
    ticks: list[Tick] = []
    selected_log: Path | None = None
    source_kind = "unavailable"
    for log in event_logs:
        matched: deque[Tick] = deque(maxlen=max_ticks)
        with log.open("r", encoding="utf-8", errors="replace") as file:
            for line in file:
                tick = _parse_event_tick(line, normalized_symbol)
                if tick is not None:
                    matched.append(tick)
        if matched:
            ticks = list(matched)
            selected_log = log
            source_kind = "runtime-event-log-market-tick"
            break
    if not ticks:
        for log in tick_logs:
            matched: deque[Tick] = deque(maxlen=max_ticks)
            with log.open("r", encoding="utf-8", errors="replace") as file:
                for line in file:
                    tick = _parse_recorded_tick(line, normalized_symbol)
                    if tick is not None:
                        matched.append(tick)
            if matched:
                ticks = list(matched)
                selected_log = log
                source_kind = "runtime-ticks-jsonl"
                break
    cached = None if ticks else _load_cached_bars(base_root, compact_date, normalized_symbol, timeframe)
    if cached is not None:
        return cached
    bars = _ticks_to_bars(ticks, timeframe)
    return {
        "date": f"{compact_date[:4]}-{compact_date[4:6]}-{compact_date[6:]}",
        "symbol": normalized_symbol,
        "timeframe": timeframe,
        "source_kind": source_kind,
        "source_path": str(selected_log) if selected_log else None,
        "available_event_logs": len(event_logs),
        "available_tick_logs": len(tick_logs),
        "tick_count": len(ticks),
        "bar_count": len(bars),
        "bars": bars,
        "note": None if ticks else "No runtime tick records found for selected date/symbol in mounted local sources.",
    }
