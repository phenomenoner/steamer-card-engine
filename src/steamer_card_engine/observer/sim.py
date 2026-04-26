from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .bridge import ObserverProjector, ObserverSessionMetadata
from .schema import CandleBar, ObserverEvent, ObserverSessionBundle, utc_now_iso


class SimObserverError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SimObserverError(f"missing JSON file: {path}") from error
    except json.JSONDecodeError as error:
        raise SimObserverError(f"invalid JSON file: {path}") from error


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except FileNotFoundError as error:
        raise SimObserverError(f"missing JSONL file: {path}") from error
    except json.JSONDecodeError as error:
        raise SimObserverError(f"invalid JSONL file: {path}") from error


def _timestamp_or_now(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    return utc_now_iso()


def _build_candles(event_rows: list[dict[str, Any]]) -> tuple[str, list[CandleBar], dict[str, float]]:
    symbol = "UNKNOWN"
    latest_prices: dict[str, float] = {}
    candles_by_minute: dict[tuple[str, str], list[float]] = {}

    for row in event_rows:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        symbol = str(row.get("symbol") or payload.get("symbol") or symbol)
        event_time = str(row.get("event_time_utc") or "")
        price = payload.get("price")
        if event_time and isinstance(price, (int, float)):
            minute = event_time[:16] + ":00Z"
            candles_by_minute.setdefault((symbol, minute), []).append(float(price))
            latest_prices[symbol] = float(price)

    candles: list[CandleBar] = []
    for (candle_symbol, minute), prices in sorted(candles_by_minute.items(), key=lambda item: item[0][1]):
        if candle_symbol != symbol:
            continue
        candles.append(
            CandleBar(
                time=minute,
                open=prices[0],
                high=max(prices),
                low=min(prices),
                close=prices[-1],
                volume=len(prices),
            )
        )
    return symbol, candles, latest_prices


def _order_side_for_order(order_id: str, execution_rows: list[dict[str, Any]]) -> str:
    for row in execution_rows:
        if f"order-{row['exec_request_id']}" == order_id:
            return str(row.get("side") or "buy")
    return "buy"


def build_sim_observer_bundle(
    *,
    bundle_dir: Path,
    session_id: str,
    engine_id: str = "steamer-card-engine.sim",
    session_label: str = "Steamer simulated observer",
    market_mode: str = "sim",
    timeframe: str = "1m",
) -> ObserverSessionBundle:
    event_rows = _load_jsonl(bundle_dir / "event-log.jsonl")
    execution_rows = _load_jsonl(bundle_dir / "execution-log.jsonl")
    lifecycle_rows = _load_jsonl(bundle_dir / "order-lifecycle.jsonl")
    fill_rows = _load_jsonl(bundle_dir / "fills.jsonl")
    position_rows = _load_jsonl(bundle_dir / "positions.jsonl")
    pnl_summary = _load_json(bundle_dir / "pnl-summary.json") if (bundle_dir / "pnl-summary.json").exists() else {}

    symbol, candles, latest_prices = _build_candles(event_rows)
    started_at = _timestamp_or_now(event_rows[0].get("event_time_utc") if event_rows else None)

    events: list[ObserverEvent] = []
    seq = 1

    def add(event_type: str, event_time: str, event_id: str, partial_data: dict[str, Any]) -> None:
        nonlocal seq
        events.append(
            ObserverEvent(
                schema_version="observer.v0",
                session_id=session_id,
                engine_id=engine_id,
                seq=seq,
                event_id=event_id,
                event_type=event_type,
                event_time=event_time,
                ingest_time=utc_now_iso(),
                partial_data=partial_data,
                freshness_state="fresh",
            )
        )
        seq += 1

    add(
        "session_started",
        started_at,
        "sim-session-started",
        {
            "title": "Sim session started",
            "summary": "Observer attached to simulated lifecycle bundle.",
        },
    )

    for candle in candles:
        add(
            "candle_bar",
            candle.time,
            f"candle-{candle.time}",
            {
                "title": f"{candle.time[11:16]} candle",
                "summary": f"Simulated candle for {symbol}.",
                "candle": asdict(candle),
            },
        )

    for row in execution_rows:
        event_time = _timestamp_or_now(row.get("request_time_utc"))
        add(
            "order_submitted",
            event_time,
            f"order-submitted-{row['exec_request_id']}",
            {
                "title": "Sim order submitted",
                "summary": f"{str(row['side']).upper()} request for {row['symbol']}.",
                "order": {
                    "order_id": f"order-{row['exec_request_id']}",
                    "status": "submitted",
                    "side": row["side"],
                    "quantity": int(float(row.get("qty") or 0.0)),
                    "limit_price": row.get("limit_price"),
                    "filled_quantity": 0,
                    "submitted_at": event_time,
                },
            },
        )

    for row in lifecycle_rows:
        state = str(row.get("state") or "")
        if state == "new":
            title = "Sim order acknowledged"
            status = "working"
        elif state == "filled":
            title = "Sim order filled"
            status = "filled"
        else:
            continue
        event_time = _timestamp_or_now(row.get("event_time_utc"))
        add(
            "order_acknowledged",
            event_time,
            f"lifecycle-{row['lifecycle_event_id']}",
            {
                "title": title,
                "summary": f"Lifecycle state {state} for simulated order.",
                "order": {
                    "order_id": row["order_id"],
                    "status": status,
                    "side": _order_side_for_order(str(row["order_id"]), execution_rows),
                    "quantity": int(float(row.get("cum_qty") or row.get("leaves_qty") or 0.0)),
                    "limit_price": None,
                    "filled_quantity": int(float(row.get("cum_qty") or 0.0)),
                    "submitted_at": event_time,
                },
            },
        )

    for row in fill_rows:
        event_time = _timestamp_or_now(row.get("fill_time_utc"))
        add(
            "fill_received",
            event_time,
            f"fill-{row['fill_id']}",
            {
                "title": "Sim fill received",
                "summary": f"Simulated fill for {row['symbol']}.",
                "fill": {
                    "fill_id": row["fill_id"],
                    "side": row["side"],
                    "quantity": int(float(row["qty"])),
                    "price": float(row["price"]),
                    "filled_at": event_time,
                },
            },
        )

    for row in position_rows:
        event_time = _timestamp_or_now(row.get("event_time_utc"))
        market_price = latest_prices.get(str(row["symbol"]), float(row.get("avg_cost") or 0.0))
        net_qty = float(row["net_qty"])
        add(
            "position_updated",
            event_time,
            f"position-{row['position_event_id']}",
            {
                "title": "Sim position updated",
                "summary": f"Net qty now {net_qty} for {row['symbol']}.",
                "position": {
                    "side": "flat" if net_qty == 0 else "long" if net_qty > 0 else "short",
                    "quantity": int(abs(net_qty)),
                    "avg_price": float(row.get("avg_cost") or 0.0) if net_qty != 0 else None,
                    "market_price": market_price if net_qty != 0 else None,
                    "unrealized_pnl": None,
                    "realized_pnl": float(row.get("realized_pnl_net") or 0.0),
                },
            },
        )

    summary_time = _timestamp_or_now(position_rows[-1].get("event_time_utc") if position_rows else started_at)
    add(
        "operator_visible_note",
        summary_time,
        "sim-session-summary",
        {
            "title": "Sim summary",
            "summary": f"Entries={pnl_summary.get('entry_count', 0)} exits={pnl_summary.get('exit_count', 0)}.",
            "note": "sim-fill-v1",
        },
    )

    metadata = ObserverSessionMetadata(
        session_id=session_id,
        engine_id=engine_id,
        session_label=session_label,
        market_mode=market_mode,
        symbol=f"{symbol}.TW",
        timeframe=timeframe,
    )
    bootstrap = ObserverProjector(timeline_limit=12).bootstrap_from_events(metadata, events)
    return ObserverSessionBundle(bootstrap=bootstrap, candles=candles, events=events)


def write_sim_observer_bundle_json(*, bundle: ObserverSessionBundle, output_path: Path) -> None:
    payload = {
        "metadata": {
            "session_id": bundle.bootstrap.session_id,
            "engine_id": bundle.bootstrap.engine_id,
            "session_label": bundle.bootstrap.session_label,
            "market_mode": bundle.bootstrap.market_mode,
            "symbol": bundle.bootstrap.symbol,
            "timeframe": bundle.bootstrap.timeframe,
        },
        "events": [event.to_dict() for event in bundle.events],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(serialized)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, output_path)
        try:
            dir_fd = os.open(output_path.parent, os.O_RDONLY)
        except OSError:
            dir_fd = None
        if dir_fd is not None:
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
