"""Ensemble voting database — per-scanner trade tracking.

SQLite with WAL mode. One table: trades. All writes are atomic.
No ORM — raw sqlite3 is zero-copy and stdlib-only.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


CREATE_TRADES = """
CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    scanner_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit REAL NOT NULL,
    position_size REAL,
    risk_amount REAL,
    rr_ratio REAL,
    status TEXT DEFAULT 'OPEN',
    entry_time TEXT NOT NULL,
    exit_time TEXT,
    exit_price REAL,
    pnl REAL,
    r_multiple REAL,
    outcome TEXT,
    notes TEXT,
    extras TEXT
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_trades_scanner_status ON trades(scanner_id, status);",
    "CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);",
]


class EnsembleDB:
    """Manages the ensemble's SQLite database."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._create_schema()

    def _create_schema(self) -> None:
        self._conn.execute(CREATE_TRADES)
        for index in INDEXES:
            self._conn.execute(index)
        self._conn.commit()

    # ── writes ──────────────────────────────────────────────

    def insert_trade(self, trade: dict[str, Any]) -> None:
        """Insert a new trade row."""
        columns = ", ".join(trade.keys())
        placeholders = ", ".join("?" for _ in trade)
        self._conn.execute(
            f"INSERT INTO trades ({columns}) VALUES ({placeholders})",
            list(trade.values()),
        )
        self._conn.commit()

    def update_trade(self, trade_id: str, **fields: Any) -> None:
        """Update fields on an existing trade."""
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        self._conn.execute(
            f"UPDATE trades SET {sets} WHERE id = ?",
            [*fields.values(), trade_id],
        )
        self._conn.commit()

    # ── reads ───────────────────────────────────────────────

    def get_open_trades(self, scanner_id: str | None = None) -> list[dict]:
        """Return all open trades, optionally filtered by scanner."""
        if scanner_id:
            rows = self._conn.execute(
                "SELECT * FROM trades WHERE status = 'OPEN' AND scanner_id = ? ORDER BY entry_time DESC",
                (scanner_id,),
            )
        else:
            rows = self._conn.execute(
                "SELECT * FROM trades WHERE status = 'OPEN' ORDER BY entry_time DESC"
            )
        return [dict(r) for r in rows]

    def get_closed_trades(
        self, scanner_id: str | None = None, limit: int = 100
    ) -> list[dict]:
        """Return closed trades, optionally filtered by scanner."""
        if scanner_id:
            rows = self._conn.execute(
                "SELECT * FROM trades WHERE status != 'OPEN' AND scanner_id = ? "
                "ORDER BY exit_time DESC LIMIT ?",
                (scanner_id, limit),
            )
        else:
            rows = self._conn.execute(
                "SELECT * FROM trades WHERE status != 'OPEN' ORDER BY exit_time DESC LIMIT ?",
                (limit,),
            )
        return [dict(r) for r in rows]

    def get_scanner_stats(
        self, scanner_id: str, window_days: int = 30
    ) -> dict[str, Any]:
        """Return aggregate stats for a scanner over the recent window."""
        rows = self._conn.execute(
            """
            SELECT
                COUNT(*) AS trade_count,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) AS losses,
                SUM(pnl) AS total_pnl,
                SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) AS gross_win,
                SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END) AS gross_loss,
                AVG(r_multiple) AS avg_r
            FROM trades
            WHERE scanner_id = ? AND status != 'OPEN'
              AND exit_time >= datetime('now', ? || ' days')
            """,
            (scanner_id, f"-{window_days}"),
        ).fetchone()
        result = dict(rows)
        # Coerce None → 0 for sums
        for k in (
            "trade_count",
            "wins",
            "losses",
            "total_pnl",
            "gross_win",
            "gross_loss",
        ):
            if result.get(k) is None:
                result[k] = 0
        result["avg_r"] = result.get("avg_r") or 0.0
        return result

    def close(self) -> None:
        """Commit and close the connection."""
        self._conn.commit()
        self._conn.close()
