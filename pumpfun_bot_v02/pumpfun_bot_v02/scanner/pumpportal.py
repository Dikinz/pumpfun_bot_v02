import asyncio
import json
import random
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import quote

import websockets
from websockets.exceptions import ConnectionClosed

from config import ENABLE_METERED_TRADE_STREAM, PUMPPORTAL_API_KEY
from database.db import Database


EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


class PumpPortalScanner:
    BASE_URL = "wss://pumpportal.fun/api/data"

    def __init__(
        self,
        db: Database,
        on_new_token: EventCallback | None = None,
        on_trade: EventCallback | None = None,
    ):
        self.db = db
        self.on_new_token = on_new_token
        self.on_trade = on_trade
        self._trade_subscriptions: set[str] = set()
        self._running = True

    @property
    def url(self) -> str:
        if PUMPPORTAL_API_KEY:
            return f"{self.BASE_URL}?api-key={quote(PUMPPORTAL_API_KEY)}"
        return self.BASE_URL

    async def stop(self):
        self._running = False

    async def run_forever(self):
        attempt = 0
        while self._running:
            try:
                await self._run_once()
                attempt = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                attempt += 1
                delay = min(60, (2 ** min(attempt, 5)) + random.random())
                print(f"[WS] ошибка: {exc!r}; reconnect через {delay:.1f}s")
                await asyncio.sleep(delay)

    async def _run_once(self):
        print("[WS] подключение к PumpPortal...")
        async with websockets.connect(
            self.url,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=10,
            max_size=2_000_000,
        ) as ws:
            print("[WS] подключено")
            await ws.send(json.dumps({"method": "subscribeNewToken"}))
            print("[WS] subscribeNewToken активирован")

            # Restore subscriptions after reconnect.
            if ENABLE_METERED_TRADE_STREAM and self._trade_subscriptions:
                await ws.send(
                    json.dumps({
                        "method": "subscribeTokenTrade",
                        "keys": sorted(self._trade_subscriptions),
                    })
                )

            async for raw in ws:
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    print("[WS] пропущено не-JSON сообщение")
                    continue

                if not isinstance(event, dict):
                    continue

                # PumpPortal can send status/error frames without a mint.
                if event.get("errors") or event.get("error"):
                    print("[WS] API error:", event)
                    continue

                tx_type = str(event.get("txType", "")).lower()

                if tx_type == "create":
                    await self._handle_new_token(event, ws)
                elif tx_type in {"buy", "sell"}:
                    await self._handle_trade(event)
                elif event.get("mint") and event.get("name"):
                    # Defensive fallback for a creation frame whose txType changes.
                    await self._handle_new_token(event, ws)
                else:
                    print("[WS] status:", event)

    async def _handle_new_token(self, event: dict[str, Any], ws):
        self.db.upsert_token(event)
        self.db.add_market_event("TOKEN_CREATED", event)

        mint = event.get("mint", "")
        symbol = event.get("symbol") or "?"
        name = event.get("name") or "?"
        mc = event.get("marketCapSol")

        print(f"[NEW] {symbol} | {name} | {mint} | MC_SOL={mc}")

        if self.on_new_token:
            await self.on_new_token(event)

        # Paid stream is OFF by default. If enabled, subscribe on SAME socket.
        if (
            ENABLE_METERED_TRADE_STREAM
            and PUMPPORTAL_API_KEY
            and mint
            and mint not in self._trade_subscriptions
        ):
            self._trade_subscriptions.add(mint)
            await ws.send(json.dumps({
                "method": "subscribeTokenTrade",
                "keys": [mint],
            }))

    async def _handle_trade(self, event: dict[str, Any]):
        self.db.add_market_event("TOKEN_TRADE", event)
        if self.on_trade:
            await self.on_trade(event)
