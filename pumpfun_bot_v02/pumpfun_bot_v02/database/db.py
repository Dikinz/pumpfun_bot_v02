import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self):
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tokens (
                    mint TEXT PRIMARY KEY,
                    name TEXT,
                    symbol TEXT,
                    creator TEXT,
                    signature TEXT,
                    bonding_curve_key TEXT,
                    initial_buy REAL,
                    market_cap_sol REAL,
                    v_sol_in_bonding_curve REAL,
                    v_tokens_in_bonding_curve REAL,
                    discovered_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS market_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mint TEXT,
                    event_type TEXT NOT NULL,
                    tx_type TEXT,
                    trader TEXT,
                    signature TEXT,
                    token_amount REAL,
                    sol_amount REAL,
                    market_cap_sol REAL,
                    received_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_market_events_mint_time
                    ON market_events(mint, received_at);

                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mint TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS paper_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mint TEXT NOT NULL,
                    symbol TEXT,
                    side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
                    price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    notional_usd REAL NOT NULL,
                    pnl_usd REAL DEFAULT 0,
                    pnl_pct REAL DEFAULT 0,
                    balance_after REAL NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_paper_trades_mint_time
                    ON paper_trades(mint, created_at);
                """
            )

    def upsert_token(self, event: dict[str, Any]):
        mint = event.get("mint")
        if not mint:
            return
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO tokens (
                    mint, name, symbol, creator, signature, bonding_curve_key,
                    initial_buy, market_cap_sol, v_sol_in_bonding_curve,
                    v_tokens_in_bonding_curve, discovered_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(mint) DO UPDATE SET
                    name=excluded.name,
                    symbol=excluded.symbol,
                    creator=excluded.creator,
                    signature=COALESCE(excluded.signature, tokens.signature),
                    market_cap_sol=COALESCE(excluded.market_cap_sol, tokens.market_cap_sol),
                    raw_json=excluded.raw_json
                """,
                (
                    mint,
                    event.get("name"),
                    event.get("symbol"),
                    event.get("traderPublicKey") or event.get("creator"),
                    event.get("signature"),
                    event.get("bondingCurveKey"),
                    _float_or_none(event.get("initialBuy")),
                    _float_or_none(event.get("marketCapSol")),
                    _float_or_none(event.get("vSolInBondingCurve")),
                    _float_or_none(event.get("vTokensInBondingCurve")),
                    utc_now(),
                    json.dumps(event, ensure_ascii=False),
                ),
            )

    def add_market_event(self, event_type: str, event: dict[str, Any]):
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO market_events (
                    mint, event_type, tx_type, trader, signature, token_amount,
                    sol_amount, market_cap_sol, received_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.get("mint"),
                    event_type,
                    event.get("txType"),
                    event.get("traderPublicKey"),
                    event.get("signature"),
                    _float_or_none(event.get("tokenAmount")),
                    _extract_sol_amount(event),
                    _float_or_none(event.get("marketCapSol")),
                    utc_now(),
                    json.dumps(event, ensure_ascii=False),
                ),
            )

    def add_signal(self, mint: str, score: int, decision: str, reason: str = ""):
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO signals (mint, score, decision, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (mint, score, decision, reason, utc_now()),
            )

    def add_paper_trade(
        self,
        mint: str,
        symbol: Optional[str],
        side: str,
        price: float,
        quantity: float,
        notional_usd: float,
        balance_after: float,
        pnl_usd: float = 0.0,
        pnl_pct: float = 0.0,
        reason: str = "",
    ):
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO paper_trades (
                    mint, symbol, side, price, quantity, notional_usd,
                    pnl_usd, pnl_pct, balance_after, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mint, symbol, side, price, quantity, notional_usd,
                    pnl_usd, pnl_pct, balance_after, reason, utc_now()
                ),
            )

    def stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            tokens = conn.execute("SELECT COUNT(*) FROM tokens").fetchone()[0]
            events = conn.execute("SELECT COUNT(*) FROM market_events").fetchone()[0]
            trades = conn.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
            pnl = conn.execute(
                "SELECT COALESCE(SUM(pnl_usd), 0) FROM paper_trades WHERE side='SELL'"
            ).fetchone()[0]
            return {
                "tokens_seen": tokens,
                "market_events": events,
                "paper_trade_rows": trades,
                "realized_pnl_usd": round(float(pnl), 6),
            }


def _float_or_none(value: Any) -> Optional[float]:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _extract_sol_amount(event: dict[str, Any]) -> Optional[float]:
    # Different feeds/versions may use different keys.
    for key in ("solAmount", "sol_amount", "amountSol"):
        if key in event:
            return _float_or_none(event[key])
    return None
