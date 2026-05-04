from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .fixtures import repo_root


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


def _runtime_run_roots(base_root: Path, date: str) -> list[Path]:
    roots: list[Path] = []
    dashed = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    for lane in ("steamer-card-engine", "baseline-bot"):
        local = base_root / "runs" / lane / dashed
        if local.exists():
            roots.extend([item for item in local.iterdir() if item.is_dir() and ("live-sim" in item.name or "neoapi" in item.name)])
    current = Path("/opt/trading/current/data/sim") / date
    if current.exists():
        roots.extend([item for item in current.iterdir() if item.is_dir()])
    return sorted(roots, key=lambda item: item.name, reverse=True)


def _event_logs_for_date(base_root: Path, date: str) -> list[Path]:
    logs: list[Path] = []
    for root in _runtime_run_roots(base_root, date):
        event_log = root / "event-log.jsonl"
        if event_log.exists():
            logs.append(event_log)
    return sorted(logs, key=lambda item: (item.stat().st_mtime, str(item)), reverse=True)


def _parse_event_tick(line: str, symbol: str) -> Tick | None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if event.get("event_type") != "market_tick":
        return None
    raw_symbol = str(event.get("symbol") or event.get("payload", {}).get("symbol") or "").strip()
    if raw_symbol != symbol:
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
    normalized_symbol = symbol.replace(".TW", "").strip()
    cached = _load_cached_bars(base_root, compact_date, normalized_symbol, timeframe)
    if cached is not None:
        return cached
    logs = _event_logs_for_date(base_root, compact_date)
    ticks: list[Tick] = []
    selected_log: Path | None = None
    for log in logs:
        with log.open("r", encoding="utf-8", errors="replace") as file:
            for line in file:
                tick = _parse_event_tick(line, normalized_symbol)
                if tick is not None:
                    ticks.append(tick)
                    selected_log = log
                    if len(ticks) >= max_ticks:
                        break
        if ticks:
            break
    bars = _ticks_to_bars(ticks, timeframe)
    return {
        "date": f"{compact_date[:4]}-{compact_date[4:6]}-{compact_date[6:]}",
        "symbol": normalized_symbol,
        "timeframe": timeframe,
        "source_kind": "runtime-event-log-market-tick" if ticks else "unavailable",
        "source_path": str(selected_log) if selected_log else None,
        "available_event_logs": len(logs),
        "tick_count": len(ticks),
        "bar_count": len(bars),
        "bars": bars,
        "note": None if ticks else "No runtime event-log market_tick records found for selected date/symbol in mounted local sources.",
    }
