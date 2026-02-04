import pandas as pd
import datetime

class RiskManager:
    """
    The 'Survival' Code. 
    Handles position sizing, kill switches, and time-based rules.
    """
    
    def __init__(self, initial_capital: float, max_daily_loss_pct: float = 0.02, risk_per_trade_pct: float = 0.01):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.daily_starting_capital = initial_capital
        self.max_daily_loss_pct = max_daily_loss_pct
        self.risk_per_trade_pct = risk_per_trade_pct
        self.kill_switch_active = False

    def update_capital(self, new_capital: float):
        """Updates current capital after a trade close."""
        self.current_capital = new_capital

    def reset_daily_stats(self):
        """Resets daily markers (called at start of day)."""
        self.daily_starting_capital = self.current_capital
        self.kill_switch_active = False

    def check_kill_switch(self):
        """
        The Circuit Breaker.
        Returns True if trading should stop for the day.
        """
        if self.kill_switch_active:
            return True
        
        daily_loss = self.daily_starting_capital - self.current_capital
        loss_limit = self.daily_starting_capital * self.max_daily_loss_pct
        
        if daily_loss >= loss_limit:
            print(f"⚠️ KILL SWITCH ACTIVATED! Daily loss: {daily_loss:.2f} > Limit: {loss_limit:.2f}")
            self.kill_switch_active = True
            return True
            
        return False

    def calculate_position_size(self, price: float, atr: float, stop_loss_multiplier: float = 2.0):
        """
        Volatility-Based Sizing.
        Calculates number of shares based on ATR risk.
        """
        if self.check_kill_switch():
            return 0

        risk_amount = self.current_capital * self.risk_per_trade_pct
        stop_loss_dist = atr * stop_loss_multiplier
        
        if stop_loss_dist == 0:
            return 0
            
        shares = int(risk_amount / stop_loss_dist)
        
        # Additional safety: Never put more than 20% of capital in one trade (optional but wise)
        max_cost = self.current_capital * 0.20
        if shares * price > max_cost:
            shares = int(max_cost / price)
            
        return shares

    def can_trade(self, current_time: datetime.time):
        """
        Time Rules: No new trades after 2:45 PM IST.
        """
        cutoff_time = datetime.time(14, 45) # 2:45 PM
        return current_time < cutoff_time

    def must_square_off(self, current_time: datetime.time):
        """
        Time Rules: Square off all positions at 3:15 PM IST.
        """
        square_off_time = datetime.time(15, 15) # 3:15 PM
        return current_time >= square_off_time
