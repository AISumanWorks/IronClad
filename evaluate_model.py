import pandas as pd
import numpy as np
from modules.data_handler import DataHandler
from modules.strategy_engine import StrategyEngine
from sklearn.metrics import classification_report, accuracy_score, precision_score
import warnings

warnings.filterwarnings("ignore")

def evaluate():
    print("="*60)
    print("IRONCLAD AI EVALUATION REPORT")
    print("="*60)
    
    data_handler = DataHandler()
    strategy_engine = StrategyEngine()
    
    # Test on a few major tickers to save time, or all? 
    # Let's do top 5 for speed in demonstration, or user can change it.
    tickers = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]
    
    overall_y_true = []
    overall_y_pred = []
    
    print(f"Benchmarking AI on {len(tickers)} major assets (60 days data)...")
    
    for ticker in tickers:
        try:
            # Fetch Data
            df = data_handler.fetch_data(ticker, period="60d", interval="5m")
            if df.empty or len(df) < 200:
                print(f"Skipping {ticker}: Insufficient Data")
                continue
                
            # Prepare Data
            # We want to use the strategy engine's logic to ensure consistency
            # But the strategy engine usually trains on everything passed to 'train_model'
            # We need to manually split here to measure "Out of Sample" performance
            
            data, features = strategy_engine.prepare_ml_data(df.copy())
            
            # 70/30 Split
            split = int(len(data) * 0.7)
            train_df = df.iloc[:split] # Pass original DF structure to train_model if possible?
            # strategy_engine.train_model expects a raw dataframe, calls prepare_ml_data internally
            # So we pass the sliced raw DF
            
            # Train on first 70%
            strategy_engine.train_model(ticker, df.iloc[:split])
            
            # Test on last 30%
            test_data_slice = data.iloc[split:]
            if len(test_data_slice) == 0: continue
            
            X_test = test_data_slice[features]
            y_test = test_data_slice['Target']
            
            # Predict
            model = strategy_engine.models.get(ticker)
            if model:
                # Use Probability Threshold matching Production (0.75)
                probs = model.predict_proba(X_test)[:, 1]
                preds = (probs > 0.75).astype(int)
                
                acc = accuracy_score(y_test, preds)
                precision = precision_score(y_test, preds, zero_division=0)
                print(f"{ticker:<15} | Acc: {acc:.2%} | Precision @ 0.75: {precision:.2f}")
                
                overall_y_true.extend(y_test)
                overall_y_pred.extend(preds)
            else:
                 print(f"{ticker:<15} | Failed to train")

        except Exception as e:
            print(f"Error {ticker}: {e}")

    print("-" * 60)
    if overall_y_true:
        print("AGGREGATE REPORT (All Tickers)")
        print(classification_report(overall_y_true, overall_y_pred))
        print(f"Overall Precision (Buy): {precision_score(overall_y_true, overall_y_pred):.2f}")
    else:
        print("No evaluation data generated.")
    print("="*60)

if __name__ == "__main__":
    evaluate()
