import pandas as pd
import datetime
import time
import sys
from modules.data_handler import DataHandler
from modules.strategy_engine import StrategyEngine

def print_header():
    print("\n" + "="*80)
    print(f"IRONCLAD LIVE DASHBOARD | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print(f"{'TICKER':<15} | {'PRICE':<10} | {'TREND (1H)':<12} | {'SIGNAL':<8} | {'CONFIDENCE':<10} | {'ATR':<8}")
    print("-" * 80)

def main():
    print("Initializing System...")
    data_handler = DataHandler()
    strategy_engine = StrategyEngine()
    
    tickers = data_handler.get_nifty50_tickers()
    
    # Optional: Fast mode for testing - limit tickers
    # tickers = tickers[:5] 
    
    print(f"Tracking {len(tickers)} assets. Training models on latest data...")
    
    # Pre-train models (could be optimized to load from disk in future)
    # We need enough data to train
    training_data_buffer = {}
    
    for i, ticker in enumerate(tickers):
        sys.stdout.write(f"\rTraining [{i+1}/{len(tickers)}] {ticker}...")
        sys.stdout.flush()
        
        # Fetch valid training data
        df = data_handler.fetch_data(ticker, period="60d", interval="5m")
        if not df.empty and len(df) > 100:
            strategy_engine.train_model(ticker, df)
            training_data_buffer[ticker] = df # Keep for signal generation to avoid re-fetch if possible
        else:
            # print(f"Insufficient data for {ticker}")
            pass
            
    print("\n\nSystem Ready. Scanning Market...\n")
    print_header()
    
    # Snapshot Analysis
    # In a full live loop, this would run every 5 minutes.
    # Here we run once for immediately actionable info.
    
    active_signals = []
    
    for ticker in tickers:
        try:
            # 1. Get Data
            # If we cached data, update it? For now, fetch fresh small slice for speed?
            # Actually, we need 1H trend too.
            
            df_5m = data_handler.fetch_data(ticker, period="5d", interval="5m")
            df_1h = data_handler.fetch_data(ticker, period="3mo", interval="1h")
            
            if df_5m.empty or df_1h.empty:
                continue
                
            latest_price = df_5m['close'].iloc[-1]
            
            # 2. Analyze
            # strategy engine needs the DFs
            signal, atr = strategy_engine.generate_signal(ticker, df_5m, df_1h)
            
            # Get Context info for display
            df_1h_ind = strategy_engine.add_indicators(df_1h)
            trend = strategy_engine.analyze_1h_trend(df_1h_ind)
            
            # Get ML Confidence even if no signal, for curiosity? 
            # Strategy only returns signal if filtered.
            # Let's peek at raw confidence if we want, but strategy abstraction is better.
            
            features_now = strategy_engine.add_indicators(df_5m)[['RSI', 'Dist_VWAP', 'Z_Score_VWAP', 'volume']].iloc[[-1]]
            confidence = strategy_engine.get_ml_confidence(ticker, features_now)
            
            # Formatting Output
            if signal:
                sig_str = f"📢 {signal}"
                # Save for summary
                active_signals.append((ticker, signal, latest_price, confidence))
            else:
                sig_str = "WAIT"
            
            print(f"{ticker:<15} | {latest_price:<10.2f} | {trend:<12} | {sig_str:<8} | {confidence*100:<9.1f}% | {atr:<8.2f}")
            
        except Exception as e:
            # print(f"Error {ticker}: {e}")
            continue

    print("-" * 80)
    
    if active_signals:
        print("\n🔥 ACTIONABLE SIGNALS FOUND:")
        for t, s, p, c in active_signals:
            print(f"   >>> {s} {t} @ {p} (Conf: {c*100:.1f}%)")
    else:
        print("\n😴 No high-probability trades found right now. Patience.")
        
    print("\nNote: Market data is delayed by 15-30m or Real-time depending on yfinance.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
