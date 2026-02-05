import os
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text

class DatabaseManager:
    def __init__(self, db_name="trading_bot.db"):
        # 1. Check for Render/Cloud Database URL (PostgreSQL)
        self.database_url = os.getenv("DATABASE_URL")
        
        if self.database_url:
            # Handle Render's "postgres://" vs SQLAlchemy's "postgresql://" requirement
            if self.database_url.startswith("postgres://"):
                self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)
            print(" Using Remote Database (PostgreSQL)")
        else:
            # 2. Fallback to Local SQLite
            # Check env var for path override (optional)
            env_path = os.getenv("DB_FILE_PATH")
            if env_path:
                db_name = env_path
                # Ensure directory exists for local file
                db_dir = os.path.dirname(db_name)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
            
            self.database_url = f"sqlite:///{db_name}"
            print(f" Using Local Database (SQLite): {db_name}")

        # Create SQLAlchemy Engine
        self.engine = create_engine(self.database_url)
        self.init_db()

    def get_connection(self):
        """Returns a raw connection-like object or engine connection."""
        return self.engine.connect()

    def init_db(self):
        """Initialize the database tables."""
        with self.get_connection() as conn:
            # Account Table (Balance)
            conn.execute(text('''
                CREATE TABLE IF NOT EXISTS account (
                    id INTEGER PRIMARY KEY,
                    balance REAL,
                    last_updated TIMESTAMP
                )
            '''))
            
            # Initialize balance if empty
            # Note: PostgreSQL counts might need different check, but count(*) is standard
            res = conn.execute(text('SELECT count(*) FROM account'))
            count = res.fetchone()[0]
            if count == 0:
                conn.execute(text('INSERT INTO account (id, balance, last_updated) VALUES (1, 1000000.0, :ts)'), 
                             {"ts": datetime.now()})

            # Positions Table (Current Holdings)
            conn.execute(text('''
                CREATE TABLE IF NOT EXISTS positions (
                    ticker TEXT PRIMARY KEY,
                    qty INTEGER,
                    avg_price REAL
                )
            '''))
            
            # Trades Table (History)
            # Note: AUTOINCREMENT is SQLite specific, usually SERIAL in Postgres.
            # But SQLAlchemy/Standard SQL often handles 'INTEGER PRIMARY KEY' as auto-increment in SQLite,
            # and 'SERIAL' in postgres. 
            # For cross-compatibility with raw SQL, it's tricky.
            # However, standard CREATE TABLE usually works if we don't force 'AUTOINCREMENT' keyword for Postgres.
            # SQLite: INTEGER PRIMARY KEY is auto-increment.
            # Postgres: SERIAL PRIMARY KEY.
            # Hybrid approach: Use simple IDs or rely on table creation via ORM later. 
            # For now, let's try a standard syntax or catch error.
            
            # Simple fix for raw SQL compatibility:
            # Remove AUTOINCREMENT keyword (SQLite handles INTEGER PRIMARY KEY as rowid alias anyway if simple)
            # But for Postgres we need SERIAL.
            
            id_type = "SERIAL" if "postgresql" in self.database_url else "INTEGER PRIMARY KEY AUTOINCREMENT"
            
            conn.execute(text(f'''
                CREATE TABLE IF NOT EXISTS trades (
                    id {id_type},
                    ticker TEXT,
                    side TEXT,
                    price REAL,
                    qty INTEGER,
                    strategy TEXT,
                    timestamp TIMESTAMP,
                    pnl REAL
                )
            '''))
            
            conn.execute(text(f'''
                CREATE TABLE IF NOT EXISTS predictions (
                    id {id_type},
                    ticker TEXT,
                    timestamp TIMESTAMP,
                    predicted_price REAL,
                    actual_price REAL,
                    confidence REAL,
                    strategy TEXT,
                    outcome TEXT DEFAULT 'PENDING',
                    exit_price REAL,
                    pnl_pct REAL
                )
            '''))
            
            # Migrations (Add columns if missing)
            # SQLite doesn't support IF EXISTS in ALTER COLUMN easily, so we try-except
            for col_sql in [
                "ALTER TABLE predictions ADD COLUMN outcome TEXT DEFAULT 'PENDING'",
                "ALTER TABLE predictions ADD COLUMN exit_price REAL",
                "ALTER TABLE predictions ADD COLUMN pnl_pct REAL"
            ]:
                try:
                    conn.execute(text(col_sql))
                except Exception:
                    pass
            
            conn.commit()

    def get_balance(self):
        with self.get_connection() as conn:
            res = conn.execute(text('SELECT balance FROM account WHERE id = 1'))
            row = res.fetchone()
            return row[0] if row else 0.0

    def update_balance(self, amount):
        with self.get_connection() as conn:
            # Transaction is handled by commit
            current = self.get_balance() # This opens new conn, it's fine
            new_bal = current + amount
            conn.execute(text('UPDATE account SET balance = :bal, last_updated = :ts WHERE id = 1'), 
                         {"bal": new_bal, "ts": datetime.now()})
            conn.commit()
            return new_bal

    def get_portfolio(self):
        return pd.read_sql_query("SELECT * FROM positions WHERE qty > 0", self.engine)

    def log_trade(self, ticker, side, price, qty, strategy, pnl=None):
        with self.get_connection() as conn:
            conn.execute(text('''
                INSERT INTO trades (ticker, side, price, qty, strategy, timestamp, pnl)
                VALUES (:ticker, :side, :price, :qty, :strategy, :ts, :pnl)
            '''), {"ticker": ticker, "side": side, "price": price, "qty": qty, 
                   "strategy": strategy, "ts": datetime.now(), "pnl": pnl})
            
            # Update Position
            if side == "BUY":
                row = conn.execute(text('SELECT qty, avg_price FROM positions WHERE ticker = :t'), {"t": ticker}).fetchone()
                if row:
                    old_qty, old_avg = row
                    new_qty = old_qty + qty
                    new_avg = ((old_qty * old_avg) + (qty * price)) / new_qty
                    conn.execute(text('UPDATE positions SET qty = :q, avg_price = :p WHERE ticker = :t'), 
                                 {"q": new_qty, "p": new_avg, "t": ticker})
                else:
                    conn.execute(text('INSERT INTO positions (ticker, qty, avg_price) VALUES (:t, :q, :p)'), 
                                 {"t": ticker, "q": qty, "p": price})
            
            elif side == "SELL":
                row = conn.execute(text('SELECT qty FROM positions WHERE ticker = :t'), {"t": ticker}).fetchone()
                if row:
                    new_qty = row[0] - qty
                    if new_qty <= 0:
                        conn.execute(text('DELETE FROM positions WHERE ticker = :t'), {"t": ticker})
                    else:
                        conn.execute(text('UPDATE positions SET qty = :q WHERE ticker = :t'), 
                                     {"q": new_qty, "t": ticker})
            conn.commit()

    def log_prediction(self, ticker, predicted, actual, confidence, strategy):
        with self.get_connection() as conn:
            conn.execute(text('''
                INSERT INTO predictions (ticker, timestamp, predicted_price, actual_price, confidence, strategy)
                VALUES (:t, :ts, :p, :a, :c, :s)
            '''), {"t": ticker, "ts": datetime.now(), "p": predicted, "a": actual, "c": confidence, "s": strategy})
            conn.commit()

    def update_prediction_result(self, pred_id, outcome, exit_price, pnl_pct):
        with self.get_connection() as conn:
            conn.execute(text('''
                UPDATE predictions 
                SET outcome = :o, exit_price = :e, pnl_pct = :p
                WHERE id = :id
            '''), {"o": outcome, "e": exit_price, "p": pnl_pct, "id": pred_id})
            conn.commit()

    def get_accuracy_stats(self):
        with self.get_connection() as conn:
            correct = conn.execute(text("SELECT count(*) FROM predictions WHERE outcome = 'CORRECT'")).fetchone()[0]
            wrong = conn.execute(text("SELECT count(*) FROM predictions WHERE outcome = 'WRONG'")).fetchone()[0]
            pending = conn.execute(text("SELECT count(*) FROM predictions WHERE outcome = 'PENDING'")).fetchone()[0]
            
            total_validated = correct + wrong
            win_rate = (correct / total_validated * 100) if total_validated > 0 else 0
            
            return {
                "correct": correct,
                "wrong": wrong,
                "total_validated": total_validated,
                "win_rate": round(win_rate, 1),
                "pending": pending
            }

    def get_pending_predictions(self):
        # Allow pandas to read directly from engine
        return pd.read_sql_query("SELECT * FROM predictions WHERE outcome = 'PENDING'", self.engine)

    def get_predictions(self, ticker):
        try:
            # Param style for pandas read_sql might depend on driver, but usually safe to use params arg matches DB style
            # SQLAlchemy handles params mostly
            df = pd.read_sql_query(
                "SELECT * FROM predictions WHERE ticker = %(t)s ORDER BY timestamp DESC LIMIT 100", 
                self.engine, 
                params={"t": ticker}
            )
            
            if df.empty:
                return []

            # FIX: Replace NaN with None
            df = df.astype(object).where(pd.notnull(df), None)
            return df.to_dict(orient='records')
        except Exception as e:
            print(f"DB Error get_predictions: {e}")
            return []
