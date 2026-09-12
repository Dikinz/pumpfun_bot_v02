from dataclasses import dataclass
from typing import Optional

from database.db import Database


@dataclass
class Position:
    mint: str
    symbol: str
    entry_price: float
    quantity: float
    cost_usd: float


class PaperTrader:
    def __init__(self, db: Database, starting_balance: float = 30.0):
        self.db = db
        self.balance = float(starting_balance)
        self.positions: dict[str, Position] = {}

    def buy(
        self,
        mint: str,
        symbol: str,
        price: float,
        notional_usd: float,
        reason: str = "",
    ) -> bool:
        if mint in self.positions or price <= 0 or notional_usd <= 0:
            return False
        if self.balance < notional_usd:
            return False

        quantity = notional_usd / price
        self.balance -= notional_usd
        self.positions[mint] = Position(
            mint=mint,
            symbol=symbol,
            entry_price=price,
            quantity=quantity,
            cost_usd=notional_usd,
        )
        self.db.add_paper_trade(
            mint=mint,
            symbol=symbol,
            side="BUY",
            price=price,
            quantity=quantity,
            notional_usd=notional_usd,
            balance_after=self.balance,
            reason=reason,
        )
        return True

    def sell(
        self,
        mint: str,
        price: float,
        reason: str = "",
    ) -> Optional[float]:
        pos = self.positions.get(mint)
        if not pos or price <= 0:
            return None

        proceeds = pos.quantity * price
        pnl_usd = proceeds - pos.cost_usd
        pnl_pct = (price / pos.entry_price) - 1.0

        self.balance += proceeds
        self.db.add_paper_trade(
            mint=mint,
            symbol=pos.symbol,
            side="SELL",
            price=price,
            quantity=pos.quantity,
            notional_usd=proceeds,
            balance_after=self.balance,
            pnl_usd=pnl_usd,
            pnl_pct=pnl_pct,
            reason=reason,
        )
        del self.positions[mint]
        return pnl_usd
