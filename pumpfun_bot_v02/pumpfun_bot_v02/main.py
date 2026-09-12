import asyncio

from config import DATABASE_PATH, MIN_SCORE, START_BALANCE
from database.db import Database
from scanner.pumpportal import PumpPortalScanner
from strategy.scorer import score_new_token
from trading.paper import PaperTrader


async def main():
    db = Database(DATABASE_PATH)
    trader = PaperTrader(db, START_BALANCE)

    async def on_new_token(event: dict):
        mint = event.get("mint")
        if not mint:
            return

        score, reasons = score_new_token(event)

        # Creation-event score is intentionally capped at 65.
        # We store WATCH/SKIP now; later version will add trade-flow enrichment.
        decision = "WATCH" if score >= 40 else "SKIP"
        db.add_signal(
            mint=mint,
            score=score,
            decision=decision,
            reason="; ".join(reasons),
        )
        print(
            f"[SCORE] {event.get('symbol', '?')} "
            f"{score}/100 -> {decision}"
        )

    async def on_trade(event: dict):
        # Placeholder for v0.3: rolling buy/sell flow, wallet count,
        # momentum and simulated exits.
        pass

    print("=" * 60)
    print("Pump.fun Paper Scanner v0.2")
    print(f"DB: {DATABASE_PATH}")
    print(f"Virtual balance: ${trader.balance:.2f}")
    print(f"Auto-entry threshold reserved for enriched score: {MIN_SCORE}")
    print("=" * 60)

    scanner = PumpPortalScanner(
        db=db,
        on_new_token=on_new_token,
        on_trade=on_trade,
    )

    try:
        await scanner.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print("\\nDB stats:", db.stats())


if __name__ == "__main__":
    asyncio.run(main())
