from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any

from steamer_card_engine.paper.receipts import stable_hash, stable_json

LEDGER_SCHEMA_VERSION = "paper-ledger/v1"
EXECUTION_BACKEND = "local-paper-only"
FILL_MODEL = "fixture-immediate-v1"
PNL_MODEL = "fixture-placeholder-v1"


@dataclass(frozen=True, slots=True)
class PaperOrder:
    order_id: str
    run_id: str
    request_id: str
    dedupe_key: str
    case_id: str | None
    symbol: str
    side: str
    quantity: int
    order_type: str
    status: str
    reason_code: str
    stable_reason: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class PaperFill:
    fill_id: str
    order_id: str
    run_id: str
    symbol: str
    side: str
    quantity: int
    fill_price: float
    filled_at: str
    fill_model: str = FILL_MODEL


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS paper_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS paper_runs (
            run_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            adapter_id TEXT NOT NULL,
            fixture_hash TEXT NOT NULL,
            adapter_hash TEXT NOT NULL,
            replay_hash TEXT NOT NULL,
            input_hash TEXT NOT NULL,
            risk_profile_hash TEXT NOT NULL,
            receipt_hash TEXT NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS paper_orders (
            order_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES paper_runs(run_id),
            request_id TEXT NOT NULL,
            dedupe_key TEXT NOT NULL UNIQUE,
            case_id TEXT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            order_type TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('accepted', 'rejected', 'filled', 'cancelled')),
            reason_code TEXT NOT NULL,
            stable_reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS paper_fills (
            fill_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL REFERENCES paper_orders(order_id),
            run_id TEXT NOT NULL REFERENCES paper_runs(run_id),
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            fill_price REAL NOT NULL,
            filled_at TEXT NOT NULL,
            fill_model TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS paper_positions (
            symbol TEXT PRIMARY KEY,
            quantity INTEGER NOT NULL,
            avg_price REAL NOT NULL,
            realized_pnl REAL NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS paper_events (
            event_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            order_id TEXT,
            event_type TEXT NOT NULL,
            event_seq INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            event_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.executemany(
        "INSERT OR IGNORE INTO paper_meta(key, value) VALUES (?, ?)",
        [
            ("schema_version", LEDGER_SCHEMA_VERSION),
            ("created_by", "steamer-card-engine"),
            ("execution_backend", EXECUTION_BACKEND),
            ("no_network", "true"),
        ],
    )


def current_positions(conn: sqlite3.Connection) -> dict[str, int]:
    return {str(row["symbol"]): int(row["quantity"]) for row in conn.execute("SELECT symbol, quantity FROM paper_positions")}


def dedupe_keys_present(conn: sqlite3.Connection, dedupe_keys: list[str]) -> list[str]:
    if not dedupe_keys:
        return []
    placeholders = ",".join("?" for _ in dedupe_keys)
    rows = conn.execute(
        f"SELECT dedupe_key FROM paper_orders WHERE dedupe_key IN ({placeholders})",
        dedupe_keys,
    ).fetchall()
    return [str(row["dedupe_key"]) for row in rows]


def insert_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    created_at: str,
    adapter_id: str,
    fixture_hash: str,
    adapter_hash: str,
    replay_hash: str,
    input_hash: str,
    risk_profile_hash: str,
    receipt_hash: str,
    status: str,
) -> None:
    conn.execute(
        """
        INSERT INTO paper_runs(
            run_id, created_at, adapter_id, fixture_hash, adapter_hash, replay_hash,
            input_hash, risk_profile_hash, receipt_hash, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, created_at, adapter_id, fixture_hash, adapter_hash, replay_hash, input_hash, risk_profile_hash, receipt_hash, status),
    )


def insert_order(conn: sqlite3.Connection, order: PaperOrder) -> None:
    conn.execute(
        """
        INSERT INTO paper_orders(
            order_id, run_id, request_id, dedupe_key, case_id, symbol, side, quantity,
            order_type, status, reason_code, stable_reason, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order.order_id,
            order.run_id,
            order.request_id,
            order.dedupe_key,
            order.case_id,
            order.symbol,
            order.side,
            order.quantity,
            order.order_type,
            order.status,
            order.reason_code,
            order.stable_reason,
            order.created_at,
            order.updated_at,
        ),
    )


def insert_fill(conn: sqlite3.Connection, fill: PaperFill) -> None:
    conn.execute(
        """
        INSERT INTO paper_fills(fill_id, order_id, run_id, symbol, side, quantity, fill_price, filled_at, fill_model)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fill.fill_id,
            fill.order_id,
            fill.run_id,
            fill.symbol,
            fill.side,
            fill.quantity,
            fill.fill_price,
            fill.filled_at,
            fill.fill_model,
        ),
    )
    signed_qty = fill.quantity if fill.side == "buy" else -fill.quantity
    existing = conn.execute("SELECT quantity FROM paper_positions WHERE symbol = ?", (fill.symbol,)).fetchone()
    new_qty = signed_qty + (int(existing["quantity"]) if existing else 0)
    conn.execute(
        """
        INSERT INTO paper_positions(symbol, quantity, avg_price, realized_pnl, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET quantity = excluded.quantity, avg_price = excluded.avg_price,
            realized_pnl = excluded.realized_pnl, updated_at = excluded.updated_at
        """,
        (fill.symbol, new_qty, fill.fill_price if new_qty else 0.0, 0.0, fill.filled_at),
    )


def insert_event(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    order_id: str | None,
    event_type: str,
    event_seq: int,
    payload: dict[str, Any],
    created_at: str,
) -> None:
    payload_json = stable_json(payload)
    event_hash = stable_hash(
        {
            "run_id": run_id,
            "order_id": order_id,
            "event_type": event_type,
            "event_seq": event_seq,
            "payload_json": payload_json,
        }
    )
    event_id = f"paper-event:{event_hash[:16]}"
    conn.execute(
        """
        INSERT INTO paper_events(event_id, run_id, order_id, event_type, event_seq, payload_json, event_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (event_id, run_id, order_id, event_type, event_seq, payload_json, event_hash, created_at),
    )


def audit(conn: sqlite3.Connection) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    meta = {str(row["key"]): str(row["value"]) for row in conn.execute("SELECT key, value FROM paper_meta")}
    expected_meta = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "created_by": "steamer-card-engine",
        "execution_backend": EXECUTION_BACKEND,
        "no_network": "true",
    }
    for key, expected in expected_meta.items():
        if meta.get(key) != expected:
            failures.append({"code": "meta_mismatch", "detail": f"{key} missing or invalid"})

    dangling_fills = conn.execute(
        """
        SELECT f.fill_id FROM paper_fills f
        LEFT JOIN paper_orders o ON o.order_id = f.order_id
        WHERE o.order_id IS NULL
        """
    ).fetchall()
    for row in dangling_fills:
        failures.append({"code": "fill_missing_order", "detail": str(row["fill_id"])})

    missing_fills = conn.execute(
        """
        SELECT o.order_id FROM paper_orders o
        LEFT JOIN paper_fills f ON f.order_id = o.order_id
        WHERE o.status = 'filled' AND f.fill_id IS NULL
        """
    ).fetchall()
    for row in missing_fills:
        failures.append({"code": "filled_order_missing_fill", "detail": str(row["order_id"])})

    bad_events = conn.execute("SELECT event_id, event_hash, run_id, order_id, event_type, event_seq, payload_json FROM paper_events").fetchall()
    for row in bad_events:
        if not row["event_hash"]:
            failures.append({"code": "event_hash_missing", "detail": str(row["event_id"])})
            continue
        expected_hash = stable_hash(
            {
                "run_id": row["run_id"],
                "order_id": row["order_id"],
                "event_type": row["event_type"],
                "event_seq": row["event_seq"],
                "payload_json": row["payload_json"],
            }
        )
        if row["event_hash"] != expected_hash:
            failures.append({"code": "event_hash_mismatch", "detail": str(row["event_id"])})
        try:
            json.loads(str(row["payload_json"]))
        except json.JSONDecodeError:
            failures.append({"code": "event_payload_invalid_json", "detail": str(row["event_id"])})

    fill_qty: dict[str, int] = {}
    for row in conn.execute("SELECT symbol, side, quantity FROM paper_fills"):
        signed = int(row["quantity"]) if row["side"] == "buy" else -int(row["quantity"])
        fill_qty[str(row["symbol"])] = fill_qty.get(str(row["symbol"]), 0) + signed
    pos_qty = current_positions(conn)
    for symbol, quantity in fill_qty.items():
        if pos_qty.get(symbol) != quantity:
            failures.append({"code": "position_reconcile_failed", "detail": symbol})
    for symbol, quantity in pos_qty.items():
        if fill_qty.get(symbol, 0) != quantity:
            failures.append({"code": "position_without_fills", "detail": symbol})

    counts = {
        "orders": int(conn.execute("SELECT COUNT(*) FROM paper_orders").fetchone()[0]),
        "accepted": int(conn.execute("SELECT COUNT(*) FROM paper_orders WHERE status IN ('accepted', 'filled')").fetchone()[0]),
        "rejected": int(conn.execute("SELECT COUNT(*) FROM paper_orders WHERE status = 'rejected'").fetchone()[0]),
        "fills": int(conn.execute("SELECT COUNT(*) FROM paper_fills").fetchone()[0]),
        "cancels": int(conn.execute("SELECT COUNT(*) FROM paper_orders WHERE status = 'cancelled'").fetchone()[0]),
        "events": int(conn.execute("SELECT COUNT(*) FROM paper_events").fetchone()[0]),
    }
    positions = [dict(row) for row in conn.execute("SELECT symbol, quantity, avg_price, realized_pnl FROM paper_positions ORDER BY symbol")]
    return {
        "schema_version": "paper-audit/v1",
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "decision": "pass" if not failures else "fail",
        "counts": counts,
        "account_summary": {
            "positions": positions,
            "realized_pnl": float(sum(float(row["realized_pnl"]) for row in positions)),
            "pnl_model": PNL_MODEL,
        },
        "invariant_failures": failures,
        "no_network": True,
        "topology_changed": False,
    }
