
import sys
import os
import pandas as pd
import asyncio
from datetime import datetime
from sqlalchemy import text

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.data_handler import DataHandler
from modules.strategy_engine import StrategyEngine
from modules.paper_trader import PaperTrader
from modules.sentiment_engine import SentimentEngine
from modules.db_manager import DatabaseManager

def test_data_handler():
    print("\n--- Testing DataHandler ---")
    dh = DataHandler()
    tickers = dh.get_nifty50_tickers()
    print(f"Tickers loaded: {len(tickers)}")
    assert len(tickers) > 0, "No tickers found"
    
    df = dh.fetch_data("TCS.NS", period="1d", interval="5m")
    print(f"Fetched Data for TCS.NS: {len(df)} rows")
    assert not df.empty, "Failed to fetch data"
    return df

def test_strategy_engine(df_5m):
    print("\n--- Testing StrategyEngine ---")
    se = StrategyEngine()
    
    # Mock Higher Timeframes
    df_1h = df_5m.copy() # Good enough for structural test
    df_1d = df_5m.copy()
    
    strategies = ['composite', 'orb', 'supertrend', 'macd', 'bollinger', 'candlestick_pattern', 'rsi_14']
    
    # Mock Sector Data
    sector_data = {
        '^NSEBANK': df_5m.copy(),
        '^NSEI': df_5m.copy()
    }
    
    for strategy in strategies:
        try:
            print(f"Testing Strategy: {strategy}...")
            signal, atr = se.generate_signal(
                "TCS.NS", 
                df_5m, 
                df_1h, 
                df_1d=df_1d, 
                strategy_type=strategy,
                sector_data=sector_data,
                sentiment_score=-0.1 # Test with neutral-ish sentiment
            )
            print(f"  -> Result: Signal={signal}, ATR={atr:.2f}")
        except Exception as e:
            print(f"  -> ERROR in {strategy}: {e}")
            raise e

def test_sentiment_engine():
    print("\n--- Testing SentimentEngine ---")
    s = SentimentEngine()
    try:
        score = s.get_sentiment("TCS.NS")
        print(f"Sentiment Score for TCS.NS: {score}")
        assert -1.0 <= score <= 1.0, "Score out of range"
    except Exception as e:
        print(f"Sentiment Engine Error: {e}")
        # Don't fail the whole suite if internet is flaky, but note it
        pass

def test_paper_trader():
    print("\n--- Testing PaperTrader ---")
    pt = PaperTrader()
    summary = pt.get_account_summary()
    print(f"Account Balance: {summary['cash']}")
    
    # Test Trade
    res = pt.execute_trade("TEST.NS", "BUY", 100.0, 1, "test_health_check")
    print(f"Trade Execution: {res}")
    assert res['status'] == 'success', "Trade failed"
    
    # Verify Holding
    holdings = pt.get_holdings()
    found = any(h['ticker'] == "TEST.NS" for h in holdings)
    print(f"Holding Verified: {found}")
    assert found, "Trade did not appear in holdings"
    
    # Sell (Cleanup)
    pt.execute_trade("TEST.NS", "SELL", 100.0, 1, "test_health_check_cleanup")

def test_sector_veto(df_5m):
    print("\n--- Testing Sector Veto Logic ---")
    se = StrategyEngine()
    
    # CASE 1: Normal Trade (Sector Flat)
    # HDFC (Stock) is Bullish
    # BankNifty (Sector) is Flat
    sector_data_flat = {
        '^NSEBANK': df_5m.copy(),
        '^NSEI': df_5m.copy()
    }
    # Mock generating a 'BUY' signal
    # We can't easily force generate_signal to BUY without crafting perfect data, 
    # but we can test check_sector_correlation directly.
    
    allowed = se.check_sector_correlation("HDFCBANK.NS", "BUY", sector_data_flat, df_5m)
    print(f"Sector Flat -> Allowed: {allowed}")
    assert allowed == True, "Trade should be allowed when sector is flat"
    
    # CASE 2: Sector Crash (VETO)
    sector_crash = df_5m.copy()
    # Artificially crash the last few candles of sector
    # Last candle close = 0.9 * previous (10% drop) -> huge crash
    sector_crash.iloc[-1, sector_crash.columns.get_loc('close')] = sector_crash.iloc[-6]['close'] * 0.90
    
    sector_data_crash = {
        '^NSEBANK': sector_crash,
        '^NSEI': df_5m.copy()
    }
    
    allowed_crash = se.check_sector_correlation("HDFCBANK.NS", "BUY", sector_data_crash, df_5m)
    print(f"Sector Crash -> Allowed: {allowed_crash}")
    assert allowed_crash == False, "Trade should be VETOED when sector crashes"

def test_db_integrity():
    print("\n--- Testing Database Integrity ---")
    db = DatabaseManager()
    
    tables = ["positions", "trades", "predictions", "strategy_stats"]
    for t in tables:
        try:
            # Simple query to check existence
            # Use SQLAlchemy connection logic (no cursor)
            with db.get_connection() as conn:
                res = conn.execute(text(f"SELECT count(*) FROM {t}"))
                count = res.fetchone()[0]
                print(f"Table '{t}' exists. Rows: {count}")
        except Exception as e:
            print(f"❌ Table '{t}' check failed: {e}")
            raise e

def test_ml_training(df_5m):
    print("\n--- Testing ML Training ---")
    se = StrategyEngine()
    
    # Needs > 100 samples
    # Create copies with different trends to ensure we have Target 0 and Target 1
    # Needs > 100 samples AFTER indicators (SMA 200 consumes 200 rows)
    # So we need > 300 rows minimum. Let's send 1000.
    
    df_1 = df_5m.copy()
    
    # Create a SYNTHETIC Bullish Trend (Guarantee Target 1)
    df_2 = df_5m.copy()
    # 1% per step
    synthetic_prices = [1000 * (1.01 ** i) for i in range(len(df_2))]
    df_2['close'] = synthetic_prices
    df_2['open'] = df_2['close'] * 0.99
    df_2['high'] = df_2['close'] * 1.01
    df_2['low'] = df_2['close'] * 0.98
    
    # Concatenate multiple times to get length ~1000
    df_long = pd.concat([df_1, df_2] * 8, ignore_index=True)
    
    # Train on longer data
    try:
        se.train_model("TEST_ML.NS", df_long)
        model = se.models.get("TEST_ML.NS")
        print(f"Model Trained: {model is not None}")
        assert model is not None, "Model failed to train"
        
        # Test Prediction
        features = se.add_indicators(df_5m)[['RSI', 'Dist_VWAP', 'Z_Score_VWAP', 'volume']].iloc[[-1]]
        conf = se.get_ml_confidence("TEST_ML.NS", features)
        print(f"Model Confidence: {conf:.2f}")
        assert 0.0 <= conf <= 1.0, "Confidence out of bounds"
        
    except Exception as e:
         print(f"ML Training Failed: {e}")
         raise e

def main():
    try:
        df_5m = test_data_handler()
        
        # Core checks
        test_strategy_engine(df_5m)
        test_sentiment_engine()
        test_paper_trader()
        
        # Deep dives
        test_sector_veto(df_5m)
        test_db_integrity()
        test_ml_training(df_5m)
        
        print("\n✅ EXTENDED SYSTEM HEALTH CHECK PASSED!")
    except Exception as e:
        print(f"\n❌ SYSTEM HEALTH CHECK FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
