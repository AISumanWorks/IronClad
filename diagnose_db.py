from modules.db_manager import DatabaseManager
import pandas as pd
try:
    db = DatabaseManager()
    print("Tables:", pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", db.engine))
    print("Trying to fetch history...")
    df = db.get_trade_history()
    print("History fetched successfully.")
    print(df)
except Exception as e:
    print(f"CRITICAL ERROR: {e}")
