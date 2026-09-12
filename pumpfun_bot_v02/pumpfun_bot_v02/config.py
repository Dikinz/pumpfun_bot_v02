import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

START_BALANCE = 30.0
POSITION_SIZE = 5.0
MIN_SCORE = 75
STOP_LOSS = -0.12
TAKE_PROFIT_1 = 0.20
TAKE_PROFIT_2 = 0.40
MAX_POSITIONS = 2
MODE = "PAPER"

PUMPPORTAL_API_KEY = os.getenv("PUMPPORTAL_API_KEY", "").strip()
ENABLE_METERED_TRADE_STREAM = (
    os.getenv("ENABLE_METERED_TRADE_STREAM", "false").strip().lower() == "true"
)

DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "data/trades.db"))
