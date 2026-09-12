from config import DATABASE_PATH
from database.db import Database

db = Database(DATABASE_PATH)
stats = db.stats()

print("=== SQLite journal ===")
for key, value in stats.items():
    print(f"{key}: {value}")
