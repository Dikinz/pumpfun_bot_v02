# Pump.fun Paper Scanner v0.2

Real-time scanner for newly created Pump.fun tokens + SQLite journal.
No wallet, seed phrase or private key is required.

## 1. Windows setup

```powershell
cd pumpfun_bot_v02
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
copy .env.example .env
py main.py
```

Stop with `Ctrl+C`.

## 2. What it stores

SQLite database defaults to:

`data/trades.db`

Tables:
- `tokens` — discovered token launches
- `market_events` — creation/trade events
- `signals` — score and WATCH/SKIP decision
- `paper_trades` — simulated BUY/SELL journal

View summary:

```powershell
py show_stats.py
```

Open the database with DB Browser for SQLite if you want to inspect rows manually.

## 3. Data mode

Default:
- `subscribeNewToken`: ON
- metered `subscribeTokenTrade`: OFF

This means the scanner can discover real new launches without subscribing to
the paid per-token trade firehose.

If you explicitly want the metered trade stream, set in `.env`:

```env
PUMPPORTAL_API_KEY=your_key_here
ENABLE_METERED_TRADE_STREAM=true
```

Do NOT put seed phrases or wallet private keys in this project.

## 4. Important strategy note

The creation event alone does not contain enough information to make a robust
entry decision. v0.2 intentionally caps the creation score below the 75-point
entry threshold. The next version should enrich WATCH candidates with:
- rolling buy/sell flow
- unique wallets
- momentum
- creator activity
- holder concentration
- liquidity / graduation state
- exit simulation

This prevents the paper trader from pretending that incomplete data is a
high-confidence signal.
