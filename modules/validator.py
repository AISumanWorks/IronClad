from modules.db_manager import DatabaseManager
from modules.data_handler import DataHandler
from datetime import datetime, timedelta
import pandas as pd
from modules.system_logger import logger

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
            
        logger.log(f"Validating {len(pending)} pending predictions...", "INFO")
        
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
                
                # Check Side (Default to BUY for legacy data)
                side = row.get('side', 'BUY') 
                if side is None: side = 'BUY'

                if side == 'BUY':
                    pnl = (current_price - entry_price) / entry_price
                else: # SELL
                    pnl = (entry_price - current_price) / entry_price
                
                outcome = "WRONG"
                if pnl > 0.001: # > 0.1% profit (Breakeven + fees roughly)
                    outcome = "CORRECT"
                elif pnl < -0.005: # Stop loss logic? Just pure direction for now.
                    outcome = "WRONG"
                else:
                    outcome = "NEUTRAL" # Flat
                    
                logger.log(f"Validated {ticker} ({side}): Entry {entry_price} -> Exit {current_price} ({outcome})", "INFO")
                
                self.db.update_prediction_result(row['id'], outcome, current_price, pnl)
                
                # Feedback to the Brain
                self.db.update_strategy_stats(row['strategy'], outcome, pnl)
                
            except Exception as e:
                logger.log(f"Error validating prediction {row['id']}: {e}", "ERROR")
