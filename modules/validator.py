from modules.db_manager import DatabaseManager
from modules.data_handler import DataHandler
from datetime import datetime, timedelta
import pandas as pd

class PredictionValidator:
    def __init__(self):
        self.db = DatabaseManager()
        self.data = DataHandler()
        self.validation_horizon_minutes = 15 # Check strictly after 15 mins
        
    def validate(self):
        """
        Main loop to check pending predictions.
        """
        pending = self.db.get_pending_predictions()
        if pending.empty:
            return 
            
        print(f"[{datetime.now()}] Validating {len(pending)} pending predictions...")
        
        for index, row in pending.iterrows():
            try:
                # Parse timestamp
                # DB stores ISO format string usually: '2026-02-04T17:15:00.123456'
                pred_time = datetime.fromisoformat(row['timestamp'])
                
                # Check if enough time has passed
                if datetime.now() < pred_time + timedelta(minutes=self.validation_horizon_minutes):
                    continue
                    
                # Enough time passed. Let's get current price (Exit Price)
                # We can fetch 1m candle or just latest
                ticker = row['ticker']
                current_price = self.data.get_latest_price(ticker)
                
                if not current_price:
                    continue
                    
                entry_price = row['actual_price'] # Price at prediction time
                
                # Logic: Did it go up? (Assuming all predictions are Long/Buy for now as per strategy)
                # If we had Short signals, we'd need 'side' in prediction table or strategy info.
                # Assuming BUY for now.
                
                pnl = (current_price - entry_price) / entry_price
                
                outcome = "WRONG"
                if pnl > 0.001: # > 0.1% profit (Breakeven + fees roughly)
                    outcome = "CORRECT"
                elif pnl < -0.005: # Stop loss logic? Just pure direction for now.
                    outcome = "WRONG"
                else:
                    outcome = "NEUTRAL" # Flat
                    
                print(f"Validated {ticker}: Entry {entry_price} -> Exit {current_price} ({outcome})")
                
                self.db.update_prediction_result(row['id'], outcome, current_price, pnl)
                
                # Feedback to the Brain
                self.db.update_strategy_stats(row['strategy'], outcome, pnl)
                
            except Exception as e:
                print(f"Error validating prediction {row['id']}: {e}")
