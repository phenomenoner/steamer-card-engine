from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from .runtime_chart import (
    Tick,
    _normalize_symbol,
    _parse_date,
    _parse_epoch_like_time,
    _parse_event_tick,
    _parse_recorded_tick,
    _runtime_run_roots,
    _ticks_to_bars,
)

SCHEMA_VERSION = "steamer-dashboard-runtime-store-v9"


@dataclass(frozen=True)
class RuntimeImportReceipt:
    db_path: str
    root: str
    dates: list[str]
    run_count: int
    tick_count: int
    decision_count: int
    order_count: int


def connect_runtime_store(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    ensure_runtime_store_schema(conn)
    return conn


def _table_sql(conn: sqlite3.Connection, table: str) -> str | None:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return str(row[0]) if row and row[0] else None


def ensure_runtime_store_schema(conn: sqlite3.Connection) -> None:
    ticks_sql = _table_sql(conn, "ticks")
    aggregates_sql = _table_sql(conn, "decision_aggregates")
    if ticks_sql and ("source_id" not in ticks_sql or (aggregates_sql is not None and "reason_code" not in aggregates_sql)):
        # v7 normalizes source file paths and adds tick fingerprints. Rebuild
        # artifact tables together; importer is snapshot/idempotent and will
        # repopulate rows from runtime files.
        for table in ("ticks", "decisions", "orders", "decision_aggregates", "source_files"):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            lane TEXT,
            source_root TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            started_at TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS source_files (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL,
            first_seen_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ticks (
            run_id TEXT NOT NULL,
            date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            ts_epoch REAL NOT NULL,
            price REAL NOT NULL,
            size REAL NOT NULL DEFAULT 0,
            source_id INTEGER NOT NULL,
            source_line INTEGER NOT NULL,
            tick_fingerprint TEXT NOT NULL,
            PRIMARY KEY (run_id, source_id, source_line),
            UNIQUE (run_id, tick_fingerprint),
            FOREIGN KEY (run_id) REFERENCES runs(run_id),
            FOREIGN KEY (source_id) REFERENCES source_files(source_id)
        );
        CREATE INDEX IF NOT EXISTS idx_ticks_date_symbol_ts ON ticks(date, symbol, ts_epoch);
        CREATE TABLE IF NOT EXISTS decisions (
            run_id TEXT NOT NULL,
            date TEXT NOT NULL,
            symbol TEXT,
            ts_utc TEXT,
            gate TEXT,
            enter INTEGER,
            reason TEXT,
            state_json TEXT,
            source_path TEXT NOT NULL,
            source_line INTEGER NOT NULL,
            PRIMARY KEY (run_id, source_path, source_line),
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );
        CREATE INDEX IF NOT EXISTS idx_decisions_date_symbol_ts ON decisions(date, symbol, ts_utc);
        CREATE TABLE IF NOT EXISTS orders (
            run_id TEXT NOT NULL,
            date TEXT NOT NULL,
            symbol TEXT,
            ts_utc TEXT,
            side TEXT,
            qty REAL,
            price REAL,
            status TEXT,
            raw_json TEXT NOT NULL,
            source_path TEXT NOT NULL,
            source_line INTEGER NOT NULL,
            PRIMARY KEY (run_id, source_path, source_line),
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );
        CREATE INDEX IF NOT EXISTS idx_orders_date_symbol_ts ON orders(date, symbol, ts_utc);
        CREATE TABLE IF NOT EXISTS decision_aggregates (
            run_id TEXT NOT NULL,
            date TEXT NOT NULL,
            symbol TEXT,
            gate TEXT,
            reason_code TEXT NOT NULL,
            reason_sample TEXT,
            enter INTEGER,
            count INTEGER NOT NULL,
            first_ts_utc TEXT,
            last_ts_utc TEXT,
            PRIMARY KEY (run_id, date, symbol, gate, reason_code, enter),
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );
        CREATE INDEX IF NOT EXISTS idx_decision_aggregates_date_symbol ON decision_aggregates(date, symbol);
        """
    )
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("schema", SCHEMA_VERSION))
    conn.commit()


def _epoch_from_epoch_like(value: Any) -> float | None:
    parsed = _parse_epoch_like_time(value)
    if parsed is None:
        return None
    return parsed.astimezone(timezone.utc).timestamp()


def _iso_from_epoch_like(value: Any) -> str | None:
    parsed = _parse_epoch_like_time(value)
    if parsed is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _file_line_records(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as file:
        for line_no, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield line_no, payload


def _runtime_run_id(date: str, run_root: Path) -> str:
    return f"{date}:{_lane_for_run_root(run_root)}:{run_root.name}"


def _lane_for_run_root(run_root: Path) -> str:
    parts = run_root.parts
    if "runs" in parts:
        idx = parts.index("runs")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    configured_root = os.getenv("STEAMER_DASHBOARD_RUNTIME_ROOT")
    if configured_root and str(run_root).startswith(str(Path(configured_root))):
        return "configured-runtime-root"
    return "unknown"


def _upsert_run(conn: sqlite3.Connection, date: str, run_root: Path) -> str:
    run_id = _runtime_run_id(date, run_root)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    conn.execute(
        """
        INSERT INTO runs(run_id, date, lane, source_root, source_kind, started_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            lane=excluded.lane,
            source_root=excluded.source_root,
            source_kind=excluded.source_kind,
            updated_at=excluded.updated_at
        """,
        (run_id, f"{date[:4]}-{date[4:6]}-{date[6:]}", _lane_for_run_root(run_root), str(run_root), "runtime-files", None, now),
    )
    return run_id


def _purge_run_artifacts(conn: sqlite3.Connection, run_id: str) -> None:
    for table in ("ticks", "decisions", "orders", "decision_aggregates"):
        conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))


def _source_kind(path: Path) -> str:
    if path.name == "event-log.jsonl":
        return "event-log"
    if path.name == "ticks.jsonl":
        return "ticks-jsonl"
    if path.name == "decisions.jsonl":
        return "decisions-jsonl"
    if path.name == "orders.jsonl":
        return "orders-jsonl"
    return "runtime-file"


def _source_id(conn: sqlite3.Connection, path: Path) -> int:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    conn.execute(
        "INSERT OR IGNORE INTO source_files(path, kind, first_seen_at) VALUES (?, ?, ?)",
        (str(path), _source_kind(path), now),
    )
    return int(conn.execute("SELECT source_id FROM source_files WHERE path = ?", (str(path),)).fetchone()[0])


def _tick_fingerprint(date: str, symbol: str, tick: Tick) -> str:
    ts = f"{tick.time.astimezone(timezone.utc).timestamp():.6f}"
    return "|".join((date, _normalize_symbol(symbol), ts, f"{tick.price:.6f}", f"{tick.size:.6f}"))


def import_runtime_files_once(db_path: str | Path, root: str | Path, dates: list[str] | None = None) -> RuntimeImportReceipt:
    root_path = Path(root)
    conn = connect_runtime_store(db_path)
    compact_dates = [_parse_date(item) for item in dates] if dates else _discover_dates(root_path)
    run_count = tick_count = decision_count = order_count = 0
    with conn:
        for date in compact_dates:
            for run_root in _runtime_run_roots(root_path, date):
                run_id = _upsert_run(conn, date, run_root)
                _purge_run_artifacts(conn, run_id)
                run_count += 1
                data_dir = run_root / "data" / date
                for tick_path in (data_dir / "ticks.jsonl", run_root / "ticks.jsonl", run_root / "event-log.jsonl"):
                    tick_count += _import_tick_source(conn, run_id, date, tick_path)
                decision_path = data_dir / "decisions.jsonl"
                decision_count += _import_decisions(conn, run_id, date, decision_path)
                _import_decision_aggregates(conn, run_id, date, decision_path)
                order_count += _import_orders(conn, run_id, date, data_dir / "orders.jsonl")
    conn.close()
    return RuntimeImportReceipt(
        db_path=str(db_path),
        root=str(root),
        dates=[f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in compact_dates],
        run_count=run_count,
        tick_count=tick_count,
        decision_count=decision_count,
        order_count=order_count,
    )


def _discover_dates(root: Path) -> list[str]:
    dates: set[str] = set()
    lanes = [root / "runs" / "steamer-card-engine", root / "runs" / "baseline-bot"]
    configured_root = os.getenv("STEAMER_DASHBOARD_RUNTIME_ROOT")
    if configured_root:
        lanes.append(Path(configured_root))
    for lane in lanes:
        if not lane.exists():
            continue
        for item in lane.iterdir():
            if item.is_dir() and len(item.name) == 8 and item.name.isdigit():
                dates.add(item.name)
            elif item.is_dir() and len(item.name) == 10 and item.name[4] == "-" and item.name[7] == "-":
                dates.add(item.name.replace("-", ""))
    return sorted(dates, reverse=True)


def _tick_row(conn: sqlite3.Connection, run_id: str, date: str, tick: Tick, source_path: Path, line_no: int, symbol: str) -> tuple[Any, ...]:
    normalized_symbol = _normalize_symbol(symbol)
    return (
        run_id,
        f"{date[:4]}-{date[4:6]}-{date[6:]}",
        normalized_symbol,
        tick.time.astimezone(timezone.utc).timestamp(),
        tick.price,
        tick.size,
        _source_id(conn, source_path),
        line_no,
        _tick_fingerprint(date, normalized_symbol, tick),
    )


def _import_tick_source(conn: sqlite3.Connection, run_id: str, date: str, path: Path) -> int:
    rows: list[tuple[Any, ...]] = []
    for line_no, payload in _file_line_records(path):
        payload_body = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        raw_symbol = _normalize_symbol(payload.get("symbol") or payload_body.get("symbol"))
        if not raw_symbol:
            continue
        line = json.dumps(payload, ensure_ascii=False)
        tick = _parse_event_tick(line, raw_symbol) if payload.get("event_type") == "market_tick" else _parse_recorded_tick(line, raw_symbol)
        if tick is not None:
            rows.append(_tick_row(conn, run_id, date, tick, path, line_no, raw_symbol))
    conn.executemany(
        """
        INSERT OR IGNORE INTO ticks(run_id, date, symbol, ts_epoch, price, size, source_id, source_line, tick_fingerprint)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


def _import_decisions(conn: sqlite3.Connection, run_id: str, date: str, path: Path) -> int:
    rows: list[tuple[Any, ...]] = []
    for line_no, payload in _file_line_records(path):
        if payload.get("enter") is not True:
            continue
        symbol = _normalize_symbol(payload.get("symbol") or "") or None
        state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
        ts = _iso_from_epoch_like(state.get("now_ts") if isinstance(state, dict) else None) or _iso_from_epoch_like(payload.get("time") or payload.get("ts") or payload.get("timestamp"))
        rows.append((run_id, f"{date[:4]}-{date[4:6]}-{date[6:]}", symbol, ts, payload.get("gate"), 1, payload.get("reason"), None, str(path), line_no))
    conn.executemany(
        """
        INSERT OR REPLACE INTO decisions(run_id, date, symbol, ts_utc, gate, enter, reason, state_json, source_path, source_line)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


def _decision_ts(payload: dict[str, Any]) -> str | None:
    state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
    return _iso_from_epoch_like(state.get("now_ts") if isinstance(state, dict) else None) or _iso_from_epoch_like(
        payload.get("time") or payload.get("ts") or payload.get("timestamp")
    )


def _normalize_reason_code(reason: Any) -> str:
    text = str(reason or "unknown").strip()
    if not text:
        return "unknown"
    head = text.split(":", 1)[0].strip()
    return head or "unknown"


def _import_decision_aggregates(conn: sqlite3.Connection, run_id: str, date: str, path: Path) -> int:
    aggregates: dict[tuple[Any, ...], dict[str, Any]] = {}
    dashed_date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    for _, payload in _file_line_records(path):
        symbol = _normalize_symbol(payload.get("symbol") or "") or None
        gate = payload.get("gate")
        reason_sample = str(payload.get("reason") or "unknown")
        reason_code = _normalize_reason_code(reason_sample)
        enter = 1 if payload.get("enter") is True else 0 if payload.get("enter") is False else None
        ts = _decision_ts(payload)
        key = (run_id, dashed_date, symbol, gate, reason_code, enter)
        item = aggregates.setdefault(key, {"count": 0, "first": ts, "last": ts, "sample": reason_sample})
        item["count"] += 1
        if ts and (item["first"] is None or ts < item["first"]):
            item["first"] = ts
        if ts and (item["last"] is None or ts > item["last"]):
            item["last"] = ts
    rows = [(*key[:5], item["sample"], key[5], item["count"], item["first"], item["last"]) for key, item in aggregates.items()]
    conn.executemany(
        """
        INSERT OR REPLACE INTO decision_aggregates(run_id, date, symbol, gate, reason_code, reason_sample, enter, count, first_ts_utc, last_ts_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


def _import_orders(conn: sqlite3.Connection, run_id: str, date: str, path: Path) -> int:
    rows: list[tuple[Any, ...]] = []
    for line_no, payload in _file_line_records(path):
        symbol = _normalize_symbol(payload.get("symbol") or "") or None
        rows.append((run_id, f"{date[:4]}-{date[4:6]}-{date[6:]}", symbol, _iso_from_epoch_like(payload.get("time") or payload.get("ts") or payload.get("timestamp")), payload.get("side"), payload.get("qty") or payload.get("quantity"), payload.get("price"), payload.get("status"), json.dumps(payload, ensure_ascii=False, sort_keys=True), str(path), line_no))
    conn.executemany(
        """
        INSERT OR REPLACE INTO orders(run_id, date, symbol, ts_utc, side, qty, price, status, raw_json, source_path, source_line)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


def runtime_store_date_updated_epoch(db_path: str | Path, date: str) -> float | None:
    path = Path(db_path)
    if not path.exists():
        return None
    compact_date = _parse_date(date)
    dashed_date = f"{compact_date[:4]}-{compact_date[4:6]}-{compact_date[6:]}"
    conn = sqlite3.connect(path)
    row = conn.execute("SELECT MAX(updated_at) FROM runs WHERE date = ?", (dashed_date,)).fetchone()
    conn.close()
    if not row or not row[0]:
        return None
    text = str(row[0])
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
    except ValueError:
        return None


def build_runtime_symbol_bars_from_store(db_path: str | Path, date: str, symbol: str, timeframe: str = "1m", max_ticks: int = 200_000) -> dict[str, Any] | None:
    path = Path(db_path)
    if not path.exists():
        return None
    compact_date = _parse_date(date)
    dashed_date = f"{compact_date[:4]}-{compact_date[4:6]}-{compact_date[6:]}"
    normalized_symbol = _normalize_symbol(symbol)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT t.ts_epoch, t.price, t.size, sf.path AS source_path
        FROM ticks t
        JOIN source_files sf ON sf.source_id = t.source_id
        WHERE t.date = ? AND t.symbol = ?
        ORDER BY t.ts_epoch DESC
        LIMIT ?
        """,
        (dashed_date, normalized_symbol, max_ticks),
    ).fetchall()
    run_count = conn.execute("SELECT COUNT(*) FROM runs WHERE date = ?", (dashed_date,)).fetchone()[0]
    conn.close()
    if not rows:
        return None
    rows = list(reversed(rows))
    ticks = [Tick(time=datetime.fromtimestamp(float(row["ts_epoch"]), timezone.utc), price=float(row["price"]), size=float(row["size"] or 0)) for row in rows]
    bars = _ticks_to_bars(ticks, timeframe)
    source_paths = sorted({str(row["source_path"]) for row in rows if row["source_path"]})
    return {
        "date": dashed_date,
        "symbol": normalized_symbol,
        "timeframe": timeframe,
        "source_kind": "runtime-store-sqlite-ticks",
        "source_path": str(path),
        "source_paths": source_paths[:5],
        "store_run_count": run_count,
        "tick_count": len(ticks),
        "bar_count": len(bars),
        "bars": bars,
        "truncated": len(rows) >= max_ticks,
        "note": None,
    }


def build_decision_aggregates_from_store(db_path: str | Path, date: str, symbol: str | None = None, limit: int = 100) -> dict[str, Any] | None:
    path = Path(db_path)
    if not path.exists():
        return None
    compact_date = _parse_date(date)
    dashed_date = f"{compact_date[:4]}-{compact_date[4:6]}-{compact_date[6:]}"
    normalized_symbol = _normalize_symbol(symbol) if symbol else None
    where = "date = ?"
    params: list[Any] = [dashed_date]
    if normalized_symbol:
        where += " AND symbol = ?"
        params.append(normalized_symbol)
    params.append(limit)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"""
        SELECT date, symbol, gate, reason_code, reason_sample, enter, count, first_ts_utc, last_ts_utc
        FROM decision_aggregates
        WHERE {where}
        ORDER BY count DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    conn.close()
    return {
        "date": dashed_date,
        "symbol": normalized_symbol,
        "source_kind": "runtime-store-sqlite-decision-aggregates",
        "aggregate_count": len(rows),
        "aggregates": [dict(row) for row in rows],
    }


def build_runtime_dates_catalog_from_store(db_path: str | Path) -> dict[str, Any] | None:
    path = Path(db_path)
    if not path.exists():
        return None
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT r.date, COUNT(DISTINCT r.run_id) AS run_count, COUNT(t.tick_fingerprint) AS tick_count
        FROM runs r
        LEFT JOIN ticks t ON t.run_id = r.run_id
        GROUP BY r.date
        ORDER BY r.date DESC
        """
    ).fetchall()
    conn.close()
    dates = [
        {
            "date": str(row["date"]),
            "local_run_count": int(row["run_count"] or 0),
            "db_tick_count": int(row["tick_count"] or 0),
            "lanes": {},
            "s3_archive_present": False,
            "s3_manifest_present": False,
            "watchlist_present": False,
            "fixture_compare_present": False,
            "fixture_compare_status": None,
            "comparison_family": None,
            "preferred": True,
        }
        for row in rows
    ]
    return {
        "source_kind": "runtime-store-sqlite-catalog",
        "date_count": len(dates),
        "runtime_date_count": len(dates),
        "fixture_dates": [],
        "dates": dates,
        "notes": ["Runtime dates are sourced from STEAMER_DASHBOARD_RUNTIME_DB catalog."],
    }
