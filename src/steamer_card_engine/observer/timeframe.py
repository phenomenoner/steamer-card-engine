from __future__ import annotations

from datetime import datetime, timezone

from .schema import CandleBar

SUPPORTED_TIMEFRAMES = {"auto", "1m", "5m", "15m"}
_TIMEFRAME_MINUTES = {"auto": 1, "1m": 1, "5m": 5, "15m": 15}


def normalize_timeframe(value: str | None) -> str:
    timeframe = (value or "auto").strip().lower()
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise ValueError(f"invalid timeframe: {value}")
    return timeframe


def _parse_utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def bucket_time(value: str, timeframe: str) -> str:
    normalized = normalize_timeframe(timeframe)
    minutes = _TIMEFRAME_MINUTES[normalized]
    parsed = _parse_utc(value)
    minute = (parsed.minute // minutes) * minutes
    bucketed = parsed.replace(minute=minute, second=0, microsecond=0)
    return bucketed.isoformat().replace("+00:00", "Z")


def aggregate_candles(candles: list[CandleBar], timeframe: str = "auto") -> list[CandleBar]:
    normalized = normalize_timeframe(timeframe)
    if normalized in {"auto", "1m"}:
        return _dedupe_candles(candles, "1m")
    return _dedupe_candles(candles, normalized)


def _dedupe_candles(candles: list[CandleBar], timeframe: str) -> list[CandleBar]:
    buckets: dict[str, list[CandleBar]] = {}
    for candle in sorted(candles, key=lambda item: _parse_utc(item.time)):
        buckets.setdefault(bucket_time(candle.time, timeframe), []).append(candle)

    aggregated: list[CandleBar] = []
    for timestamp, values in buckets.items():
        aggregated.append(
            CandleBar(
                time=timestamp,
                open=values[0].open,
                high=max(item.high for item in values),
                low=min(item.low for item in values),
                close=values[-1].close,
                volume=sum(item.volume for item in values),
            )
        )
    return aggregated


def bootstrap_with_timeframe_chart(payload: dict, candles: list[CandleBar], timeframe: str) -> dict:
    normalized = normalize_timeframe(timeframe)
    if normalized == "auto":
        return payload
    next_payload = dict(payload)
    chart = dict(next_payload.get("chart") or {})
    chart["candles"] = [candle.__dict__.copy() for candle in aggregate_candles(candles, normalized)]
    next_payload["chart"] = chart
    next_payload["timeframe"] = normalized
    return next_payload
