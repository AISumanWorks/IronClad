import sqlite3
import pandas as pd
from datetime import datetime

import os

class DatabaseManager:
    def __init__(self, db_name="trading_bot.db"):
        # Check env var for Render/Cloud persistence
        # Check env var for Render/Cloud persistence
        env_path = os.getenv("DB_FILE_PATH")
        if env_path:
            self.db_name = env_path
            print(f"Using Database at: {self.db_name}")
            
            # Ensure directory exists
            db_dir = os.path.dirname(self.db_name)
            if db_dir and not os.path.exists(db_dir):
                print(f"WARNING: Directory {db_dir} does not exist. Attempting to create...")
                try:
                    os.makedirs(db_dir, exist_ok=True)
                    print(f"Created directory: {db_dir}")
                except Exception as e:
                    print(f"CRITICAL ERROR: Could not create directory {db_dir}. Persistance might fail. Error: {e}")
                    # Fallback to local if creation fails? 
                    # Maybe better to crash so user fixes the mount.
        else:
            self.db_name = db_name
            
        try:
            self.init_db()
        except sqlite3.OperationalError as e:
            print(f"CRITICAL SQLITE ERROR: {e}")
            print(f"Failed to open database at {self.db_name}")
            print("Troubleshooting: Check if the directory exists and has write permissions.")
            if "/data" in self.db_name:
                print("RENDER TIP: Did you accidentally enable the Env Var without adding the Disk?")
            raise e

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_db(self):
        """Initialize the database tables."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Account Table (Balance)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY,
                balance REAL,
                last_updated TIMESTAMP
            )
        ''')
        
        # Initialize balance if empty (10 Lakh)
        cursor.execute('SELECT count(*) FROM account')
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO account (balance, last_updated) VALUES (?, ?)', 
                           (1000000.0, datetime.now()))

        # Positions Table (Current Holdings)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                ticker TEXT PRIMARY KEY,
                qty INTEGER,
                avg_price REAL
            )
        ''')
        
        # Trades Table (History)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                side TEXT, -- BUY / SELL
                price REAL,
                qty INTEGER,
                strategy TEXT,
                timestamp TIMESTAMP,
                pnl REAL -- Only for SELL trades
            )
        ''')
        
        # AI Predictions Table (Learning)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                timestamp TIMESTAMP,
                predicted_price REAL,
                actual_price REAL,
                confidence REAL,
                strategy TEXT,
                outcome TEXT DEFAULT 'PENDING', -- CORRECT, WRONG, PENDING
                exit_price REAL,
                pnl_pct REAL
            )
        ''')
        
        # Migration: Add columns if they don't exist (for existing DB)
        try:
            cursor.execute("ALTER TABLE predictions ADD COLUMN outcome TEXT DEFAULT 'PENDING'")
        except: pass
        try:
            cursor.execute("ALTER TABLE predictions ADD COLUMN exit_price REAL")
        except: pass
        try:
            cursor.execute("ALTER TABLE predictions ADD COLUMN pnl_pct REAL")
        except: pass
        
        conn.commit()
        conn.close()

    def get_balance(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT balance FROM account WHERE id = 1')
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else 0.0

    def update_balance(self, amount):
        """Adds amount to balance (can be negative)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        current = self.get_balance()
        new_bal = current + amount
        cursor.execute('UPDATE account SET balance = ?, last_updated = ? WHERE id = 1', (new_bal, datetime.now()))
        conn.commit()
        conn.close()
        return new_bal

    def get_portfolio(self):
        conn = self.get_connection()
        df = pd.read_sql_query("SELECT * FROM positions WHERE qty > 0", conn)
        conn.close()
        return df

    def log_trade(self, ticker, side, price, qty, strategy, pnl=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trades (ticker, side, price, qty, strategy, timestamp, pnl)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, side, price, qty, strategy, datetime.now(), pnl))
        
        # Update Position
        if side == "BUY":
            # Check existing
            cursor.execute('SELECT qty, avg_price FROM positions WHERE ticker = ?', (ticker,))
            row = cursor.fetchone()
            if row:
                old_qty, old_avg = row
                new_qty = old_qty + qty
                new_avg = ((old_qty * old_avg) + (qty * price)) / new_qty
                cursor.execute('UPDATE positions SET qty = ?, avg_price = ? WHERE ticker = ?', (new_qty, new_avg, ticker))
            else:
                cursor.execute('INSERT INTO positions (ticker, qty, avg_price) VALUES (?, ?, ?)', (ticker, qty, price))
        
        elif side == "SELL":
            cursor.execute('SELECT qty FROM positions WHERE ticker = ?', (ticker,))
            row = cursor.fetchone()
            if row:
                new_qty = row[0] - qty
                if new_qty <= 0:
                    cursor.execute('DELETE FROM positions WHERE ticker = ?', (ticker,))
                else:
                    cursor.execute('UPDATE positions SET qty = ? WHERE ticker = ?', (new_qty, ticker))
                    
        conn.commit()
        conn.close()

    def log_prediction(self, ticker, predicted, actual, confidence, strategy):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO predictions (ticker, timestamp, predicted_price, actual_price, confidence, strategy)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (ticker, datetime.now(), predicted, actual, confidence, strategy))
        conn.commit()
        conn.close()

        conn.commit()
        conn.close()

    def update_prediction_result(self, pred_id, outcome, exit_price, pnl_pct):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE predictions 
            SET outcome = ?, exit_price = ?, pnl_pct = ?
            WHERE id = ?
        ''', (outcome, exit_price, pnl_pct, pred_id))
        conn.commit()
        conn.close()

    def get_accuracy_stats(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Calculate stats
        cursor.execute("SELECT count(*) FROM predictions WHERE outcome = 'CORRECT'")
        correct = cursor.fetchone()[0]
        
        cursor.execute("SELECT count(*) FROM predictions WHERE outcome = 'WRONG'")
        wrong = cursor.fetchone()[0]
        
        total_validated = correct + wrong
        win_rate = (correct / total_validated * 100) if total_validated > 0 else 0
        
        cursor.execute("SELECT count(*) FROM predictions WHERE outcome = 'PENDING'")
        pending = cursor.fetchone()[0]
        
        conn.close()
        return {
            "correct": correct,
            "wrong": wrong,
            "total_validated": total_validated,
            "win_rate": round(win_rate, 1),
            "pending": pending
        }


    def get_pending_predictions(self):
        conn = self.get_connection()
        # Get predictions older than 15 minutes that are still PENDING
        # We handle time filter in python or sql. SQL is better but requires string manipulation for timestamp
        # Let's simple fetch all PENDING and filter in Python Validator logic
        df = pd.read_sql_query("SELECT * FROM predictions WHERE outcome = 'PENDING'", conn)
        conn.close()
        return df

    def get_predictions(self, ticker):
        conn = self.get_connection()
        # Get last 100 predictions
        try:
            df = pd.read_sql_query("SELECT * FROM predictions WHERE ticker = ? ORDER BY timestamp DESC LIMIT 100", conn, params=(ticker,))
            conn.close()
            # Convert timestamp to unix if needed or let frontend handle
            return df.to_dict(orient='records')
        except:
             conn.close()
             return []
