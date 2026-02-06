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
            # FORCE ABSOLUTE PATH to avoid CWD issues
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # go up from modules/
            db_path = os.path.join(base_dir, "trading_bot.db")
            
            self.database_url = f"sqlite:///{db_path}"
            print(f" Using Local Database (SQLite): {db_path}")

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
            
            # Strategy Performance Table (The Brain)
            conn.execute(text(f'''
                CREATE TABLE IF NOT EXISTS strategy_stats (
                    strategy TEXT PRIMARY KEY,
                    total_trades INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0.0,
                    avg_pnl REAL DEFAULT 0.0,
                    trust_score REAL DEFAULT 0.5,
                    last_updated TIMESTAMP
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
                "SELECT * FROM predictions WHERE ticker = :t ORDER BY timestamp DESC LIMIT 100", 
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
    def update_strategy_stats(self, strategy, outcome, pnl_pct):
        """
        Updates the 'Brain' on how a strategy performed.
        """
        with self.get_connection() as conn:
            # Check if exists
            # Explicit select for robustness
            row = conn.execute(text("SELECT total_trades, wins, losses, win_rate, avg_pnl, trust_score FROM strategy_stats WHERE strategy = :s"), {"s": strategy}).fetchone()
            
            if not row:
                conn.execute(text("INSERT INTO strategy_stats (strategy, trust_score) VALUES (:s, 0.5)"), {"s": strategy})
                # Default values
                total, wins, losses, win_rate, avg_pnl, trust_score = 0, 0, 0, 0.0, 0.0, 0.5
            else:
                total, wins, losses, win_rate, avg_pnl, trust_score = row

            total = total + 1
            wins = wins + (1 if outcome == 'CORRECT' else 0)
            losses = losses + (1 if outcome == 'WRONG' else 0)
            
            # Rolling Average PnL (Simple approx)
            current_avg_pnl = avg_pnl
            new_avg_pnl = ((current_avg_pnl * (total - 1)) + pnl_pct) / total
            
            win_rate = (wins / total * 100) if total > 0 else 0
            
            # TRUST SCORE ENGINE
            # Start at 0.5. Max 1.0. Min 0.1.
            # Win increases score, Loss decreases.
            # We use a learning rate of 0.05
            current_score = row[6]
            if outcome == 'CORRECT':
                new_score = min(1.0, current_score + 0.05)
            elif outcome == 'WRONG':
                new_score = max(0.1, current_score - 0.05)
            else:
                new_score = current_score # Neutral
                
            conn.execute(text('''
                UPDATE strategy_stats 
                SET total_trades = :t, wins = :w, losses = :l, 
                    win_rate = :wr, avg_pnl = :ap, trust_score = :ts, last_updated = :time
                WHERE strategy = :s
            '''), {
                "t": total, "w": wins, "l": losses, "wr": win_rate, 
                "ap": new_avg_pnl, "ts": new_score, "time": datetime.now(), "s": strategy
            })
            conn.commit()

    def get_strategy_stats(self):
        return pd.read_sql_query("SELECT * FROM strategy_stats ORDER BY trust_score DESC", self.engine)

    def get_trade_history(self):
        """Returns all executed trades."""
        return pd.read_sql_query("SELECT * FROM trades ORDER BY timestamp DESC LIMIT 50", self.engine)

    def reset_simulation(self):
        """
        Resets the database for a fresh start.
        Clears trades, positions, predictions, stats, and resets balance.
        """
        with self.get_connection() as conn:
            conn.execute(text("DELETE FROM trades"))
            conn.execute(text("DELETE FROM positions"))
            conn.execute(text("DELETE FROM predictions"))
            conn.execute(text("DELETE FROM strategy_stats"))
            
            # Reset Balance to 1 Lakh (1,00,000)
            conn.execute(text("UPDATE account SET balance = 100000.0, last_updated = :ts WHERE id = 1"), {"ts": datetime.now()})
            
            conn.commit()
            print("✅ Database Reset Complete (Balance: 1,00,000)")
