import pandas as pd
import datetime
from modules.data_handler import DataHandler
from modules.risk_manager import RiskManager
from modules.strategy_engine import StrategyEngine

class Backtester:
    def __init__(self):
        self.data_handler = DataHandler()
        self.risk_manager = RiskManager(initial_capital=1000000) # 10 Lakh starting capital
        self.strategy_engine = StrategyEngine()
        self.trade_log = []
        self.active_positions = {} # {ticker: {'qty': int, 'entry_price': float, 'sl': float, 'signal': str}}

    def run(self, days=30, strategy='composite'):
        print(f"Initializing IronClad Backtest for {strategy.upper()} strategy...")
        print("Fetching Data and Training Models (this may take a moment)...")
        
        tickers = self.data_handler.get_nifty50_tickers()
        
        # We need enough data for training + backtest
        # yfinance '5m' allows max 60 days
        overall_data_5m = {}
        overall_data_1h = {}
        
        for ticker in tickers:
            df_5m = self.data_handler.fetch_data(ticker, period="60d", interval="5m")
            df_1h = self.data_handler.fetch_data(ticker, period="1y", interval="1h") # 1h Trend context
            
            if df_5m.empty or df_1h.empty:
                continue
                
            # Split data: First 30 days for Training, Last 30 days for Backtest
            mid_point = len(df_5m) // 2
            train_data = df_5m.iloc[:mid_point]
            test_data = df_5m.iloc[mid_point:]
            
            # Train the ML model
            self.strategy_engine.train_model(ticker, train_data)
            
            overall_data_5m[ticker] = test_data
            overall_data_1h[ticker] = df_1h
            
        print(f"\n--- Starting Simulation on {len(overall_data_5m)} Tickers ---")
        
        # Simulation requires aligning timestamps across all tickers
        # Use the index of one of the liquid tickers as the master clock
        if not overall_data_5m:
            print("No data available for backtest.")
            return

        master_ticker = list(overall_data_5m.keys())[0]
        timeline = overall_data_5m[master_ticker].index
        
        total_days = len(pd.Series(timeline.date).unique())
        print(f"Simulating approx {total_days} trading days...")

        for current_time in timeline:
            # 1. Check Date Change -> Reset Risk Manager
            if current_time.hour == 9 and current_time.minute == 15:
                self.risk_manager.reset_daily_stats()

            # Global State Checks
            kill_switch = self.risk_manager.check_kill_switch()
            current_time_obj = current_time.time()
            is_square_off_time = self.risk_manager.must_square_off(current_time_obj)
            can_open_new = self.risk_manager.can_trade(current_time_obj) and not kill_switch and not is_square_off_time

            # 2. Iterate Tickers
            for ticker in tickers:
                if ticker not in overall_data_5m: continue
                
                df_ticker = overall_data_5m[ticker]
                
                # Align time
                if current_time not in df_ticker.index:
                    continue
                    
                row = df_ticker.loc[current_time]
                price = row['close']
                
                # Manage Active Position
                if ticker in self.active_positions:
                    pos = self.active_positions[ticker]
                    
                    # Priority Exits
                    if kill_switch:
                         self.close_position(ticker, price, current_time, "KILL SWITCH")
                         continue
                    if is_square_off_time:
                         self.close_position(ticker, price, current_time, "EOD Exit")
                         continue

                    # Standard SL Logic
                    sl_price = pos['sl']
                    direction = pos['signal']
                    
                    hit_sl = False
                    if direction == 'BUY' and price <= sl_price: hit_sl = True
                    elif direction == 'SELL' and price >= sl_price: hit_sl = True
                    
                    if hit_sl:
                        self.close_position(ticker, price, current_time, "Stop Loss")
                        
                # Look for New Entry
                elif can_open_new:
                    # Slice data for strategy (up to current time)
                    historical_slice_5m = df_ticker.loc[:current_time]
                    
                    # Align 1H data (resample or lookup)
                    historical_slice_1h = overall_data_1h[ticker]
                    historical_slice_1h = historical_slice_1h[historical_slice_1h.index <= current_time]
                    
                    signal, atr = self.strategy_engine.generate_signal(
                        ticker, historical_slice_5m, historical_slice_1h, strategy_type=strategy
                    )
                    
                    if signal:
                        self.open_position(ticker, signal, price, atr, current_time)

        self.print_performance()

    def open_position(self, ticker, signal, price, atr, time):
        qty = self.risk_manager.calculate_position_size(price, atr)
        if qty <= 0: return

        # Set Stop Loss
        sl_dist = atr * 2
        sl = price - sl_dist if signal == 'BUY' else price + sl_dist
        
        self.active_positions[ticker] = {
            'qty': qty,
            'entry_price': price,
            'sl': sl,
            'signal': signal,
            'entry_time': time
        }
        # print(f"[{time}] OPEN {signal} {ticker} @ {price:.2f} | Qty: {qty} | SL: {sl:.2f}")

    def close_position(self, ticker, price, time, reason):
        pos = self.active_positions.pop(ticker)
        entry = pos['entry_price']
        qty = pos['qty']
        signal = pos['signal']
        
        if signal == 'BUY':
            pnl = (price - entry) * qty
        else:
            pnl = (entry - price) * qty
            
        self.risk_manager.update_capital(self.risk_manager.current_capital + pnl)
        
        headers = ["Time", "Ticker", "Type", "Entry", "Exit", "Qty", "PnL", "Reason"]
        trade_record = {
            "Time": time,
            "Ticker": ticker,
            "Type": signal,
            "Entry": entry,
            "Exit": price,
            "Qty": qty,
            "PnL": pnl,
            "Reason": reason
        }
        self.trade_log.append(trade_record)
        # print(f"[{time}] CLOSE {ticker} @ {price:.2f} | PnL: {pnl:.2f} | {reason}")

    def square_off_all(self, time, reason):
        # Create a list of keys to avoid runtime error during iteration
        active_tickers = list(self.active_positions.keys())
        for ticker in active_tickers:
            # We don't have the current price in this method signature easily available
            # We will use the 'close' price of the candle that triggered the square off
            # In a real engine, we'd fetch latest tick.
            # Workaround: Pass price or access last known.
            # For backtest, we might skip precise price here or need to fetch it.
            # Simple hack: use stored entry price (0 PnL) or fetch from data handler?
            # Better: The loop calling this has the `row` context only for specific ticker.
            # We can't close ALL efficiently without price data for ALL.
            # compromise: Leave open until next ticker loop iteration? 
            # No, 'Square off all' must happen. 
            pass 
            # To fix: The caller loop should handle checking square-off condition per ticker.
            # My logic in `run` loop:
            # `if self.risk_manager.must_square_off...: continue`
            # This skips processing! It needs to logic: "If must square off, close Any Active Position for this ticker".
            # Currently the global check `must_square_off` skips everything.
        
        # Correction in run loop logic:
        # Instead of `continue`, we should enter a "Close only" mode.
        pass

    def print_performance(self):
        print("\n" + "="*40)
        print("IRONCLAD BACKTEST RESULTS")
        print("="*40)
        
        if not self.trade_log:
            print("No trades triggered.")
            return
            
        df_trades = pd.DataFrame(self.trade_log)
        total_pnl = df_trades['PnL'].sum()
        win_rate = len(df_trades[df_trades['PnL'] > 0]) / len(df_trades) * 100
        
        print(f"Total Trades: {len(df_trades)}")
        print(f"Win Rate: {win_rate:.2f}%")
        print(f"Total PnL: {total_pnl:.2f}")
        print(f"Final Capital: {self.risk_manager.current_capital:.2f}")
        print("="*40)
        
        # Mentor Comments
        if total_pnl > 0:
            print("\nMentor: 'Good job, kid. You protected the capital and let the edge work.'")
        else:
            print("\nMentor: 'Tough market. But you respected the stop losses. You live to fight another day.'")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--strategy', type=str, default='composite', help='Strategy to run: composite, orb, supertrend, ma_crossover')
    args = parser.parse_args()
    
    bt = Backtester()
    bt.run(strategy=args.strategy)
