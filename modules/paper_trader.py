from modules.db_manager import DatabaseManager
import pandas as pd

class PaperTrader:
    def __init__(self):
        self.db = DatabaseManager()

    def get_account_summary(self):
        balance = self.db.get_balance()
        positions = self.db.get_portfolio()
        
        # Calculate Equity (simplified, needs live price ideally)
        # We will update equity in the main loop or just return balance + cost_basis for now
        equity = balance 
        if not positions.empty:
            equity += (positions['qty'] * positions['avg_price']).sum()
            
        return {
            "cash": balance,
            "equity": equity,
            "positions_count": len(positions)
        }

    def execute_trade(self, ticker, side, price, qty, strategy="manual"):
        """
        Executes a paper trade.
        """
        try:
            total_cost = price * qty
            
            if side == "BUY":
                if self.db.get_balance() < total_cost:
                    return {"status": "error", "message": "Insufficient Funds"}
                
                self.db.update_balance(-total_cost)
                self.db.log_trade(ticker, side, price, qty, strategy)
                return {"status": "success", "message": f"Bought {qty} {ticker}"}
            
            elif side == "SELL":
                # Check holdings
                positions = self.db.get_portfolio()
                if ticker not in positions['ticker'].values:
                     return {"status": "error", "message": "No position to sell"}
                
                current_qty = positions[positions['ticker'] == ticker]['qty'].values[0]
                if qty > current_qty:
                    return {"status": "error", "message": "Insufficient Quantity"}
                
                # Calculate PnL
                avg_buy_price = positions[positions['ticker'] == ticker]['avg_price'].values[0]
                pnl = (price - avg_buy_price) * qty
                
                self.db.update_balance(total_cost) # Add cash back
                self.db.log_trade(ticker, side, price, qty, strategy, pnl=pnl)
                return {"status": "success", "message": f"Sold {qty} {ticker}. PnL: {pnl:.2f}"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_holdings(self):
        return self.db.get_portfolio().to_dict(orient='records')

    def get_history(self):
        df = self.db.get_trade_history()
        if df.empty: return []
        
        # Sanitize for JSON: Replace Infinity and NaN with None
        # Note: JSON standard doesn't support Infinity or NaN
        import numpy as np
        df.replace([np.inf, -np.inf, np.nan], None, inplace=True)
        
        return df.to_dict(orient='records')
