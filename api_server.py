import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from modules.data_handler import DataHandler
from modules.strategy_engine import StrategyEngine
import pandas as pd
import asyncio
from datetime import datetime

from modules.paper_trader import PaperTrader
from pydantic import BaseModel

# Initialize Core System
data_handler = DataHandler()
strategy_engine = StrategyEngine()
paper_trader = PaperTrader()

class TradeRequest(BaseModel):
    ticker: str
    action: str # BUY / SELL
    qty: int
    price: float
    strategy: str = "manual"

# --- Global Cache ---
MARKET_CACHE = {
    "timestamp": None,
    "strategy": "composite",
    "signals": []
}

app = FastAPI(title="IronClad API")

# Allow CORS for React Frontend (runs on 5173 usually)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "online", "time": datetime.now()}

@app.get("/api/account")
def get_account():
    return paper_trader.get_account_summary()

@app.get("/api/portfolio")
def get_portfolio():
    return {"positions": paper_trader.get_holdings()}

@app.get("/api/predictions/{ticker}")
def get_predictions(ticker: str):
    """Returns AI predictions for the chart overlay."""
    return {"predictions": paper_trader.db.get_predictions(ticker)}

@app.get("/api/stats")
def get_ai_stats():
    """Returns AI Accuracy Statistics."""
    return paper_trader.db.get_accuracy_stats()

@app.post("/api/trade")
def execute_trade(trade: TradeRequest):
    result = paper_trader.execute_trade(
        trade.ticker, 
        trade.action, 
        trade.price, 
        trade.qty, 
        trade.strategy
    )
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/api/tickers")
def get_tickers():
    """Returns list of supported Nifty 50 tickers."""
    return {"tickers": data_handler.get_nifty50_tickers()}

@app.get("/api/data/{ticker}")
def get_market_data(ticker: str, period: str = "60d", interval: str = "5m"):
    """
    Returns Historical Data for Charting.
    Format tailored for Lightweight Charts (time: string/unix, open, high, low, close, volume).
    """
    df = data_handler.fetch_data(ticker, period=period, interval=interval)
    
    if df.empty:
        raise HTTPException(status_code=404, detail="No data found")
    
    # Lightweight Charts expects: { time: '2019-04-11', value: 80.01 } or { time: 1555555555, open: ..., ... }
    # interactive charts use Unit Timestamp usually.
    
    # Add indicators for overlay?
    # No, let frontend calculate or request separate indicator endpoint.
    # Actually, we can return pre-calculated indicators to ensure match with backend strategy.
    
    df = strategy_engine.add_indicators(df)
    
    # Process for JSON response
    # Reset index to get 'date' column if it's the index
    df = df.reset_index()
    
    # Detect Time Column
    # yfinance often works with 'Date' or 'Datetime' index.
    time_col = None
    for col in df.columns:
        if 'date' in col.lower() or 'time' in col.lower():
            time_col = col
            break
            
    if not time_col:
        # Fallback if index reset didn't work as expected or name is weird
        # But reset_index usually creates 'index' or 'Date'
        # Let's inspect
        pass

    results = []
    
    for _, row in df.iterrows():
        # Timestamp handling
        ts = row[time_col]
        # Convert to Unix Timestamp (seconds)
        unix_time = int(ts.timestamp()) + 19800 # Manual IST Offset adjustment if needed? 
        # yfinance returns UTC usually. Frontend chart handles UTC. 
        # Let's just send unix time.
        
        item = {
            "time": unix_time,
            "open": row['open'],
            "high": row['high'],
            "low": row['low'],
            "close": row['close'],
            "volume": row['volume'],
            # Indicators
            "sma_20": row.get('SMA_20'),
            "sma_50": row.get('SMA_50'),
            "vwap": row.get('VWAP'),
            "supertrend": row.get('Supertrend'),
            "supertrend_signal": row.get('Supertrend_Signal')
        }
        # Handle NaNs (Json doesn't like NaN)
        for k, v in item.items():
            if pd.isna(v):
                item[k] = None
        
        results.append(item)
        
    return {"ticker": ticker, "data": results}

@app.on_event("startup")
async def startup_event():
    """Start the background market scanner and validator on server startup."""
    asyncio.create_task(run_market_scanner())
    asyncio.create_task(run_validator_loop())

async def run_validator_loop():
    """Background task to validate predictions every 15 minutes."""
    from modules.validator import PredictionValidator
    validator = PredictionValidator()
    loop = asyncio.get_running_loop()
    while True:
        try:
            print(f"[{datetime.now()}] Running AI Validator...")
            # Run blocking validator in thread pool to avoid freezing the API
            await loop.run_in_executor(None, validator.validate)
        except Exception as e:
            print(f"Validator Error: {e}")
        
        await asyncio.sleep(900) # Check every 15 minutes

async def run_market_scanner():
    """Background task to scan the market every 5 minutes."""
    while True:
        print(f"[{datetime.now()}] Starting Background Market Scan...")
        tickers = data_handler.get_nifty50_tickers()
        active_signals = []
        
        # We focus on the default 'composite' strategy for the dashboard cache
        strategy = "composite"
        
        for ticker in tickers:
            try:
                # Optimize fetch: We need enough for indicators.
                df_5m = data_handler.fetch_data(ticker, period="5d", interval="5m")
                if df_5m.empty: continue
                
                # Needed for Composite
                df_1h = data_handler.fetch_data(ticker, period="3mo", interval="1h")
                
                signal, atr = strategy_engine.generate_signal(ticker, df_5m, df_1h, strategy_type=strategy)
                
                if signal:
                    latest = df_5m.iloc[-1]
                    
                    # Confidence
                    features = strategy_engine.add_indicators(df_5m)[['RSI', 'Dist_VWAP', 'Z_Score_VWAP', 'volume']].iloc[[-1]]
                    conf = strategy_engine.get_ml_confidence(ticker, features)
                    
                    active_signals.append({
                        "ticker": ticker,
                        "signal": signal,
                        "price": latest['close'],
                        "atr": atr,
                        "confidence": conf,
                        "timestamp": datetime.now().isoformat()
                    })

                    # --- AUTO-TRADING ENGINE ---
                    # Logic: If Confidence > 70% AND No Position -> BUY
                    if conf > 0.7:
                        holdings = paper_trader.get_holdings()
                        already_owned = any(h['ticker'] == ticker for h in holdings)
                        
                        if not already_owned:
                            print(f"[{datetime.now()}] 🤖 AUTO-TRADE TRIGGERED: Buying {ticker} (Conf: {conf:.2f})")
                            paper_trader.execute_trade(
                                ticker=ticker,
                                action="BUY",
                                price=latest['close'],
                                qty=10, # Fixed size for now
                                strategy="auto_ai"
                            )
                    # ---------------------------
            except Exception as e:
                print(f"Error scanning {ticker}: {e}")
                continue
        
        # Update Cache
        MARKET_CACHE["signals"] = active_signals
        MARKET_CACHE["timestamp"] = datetime.now().isoformat()
        MARKET_CACHE["strategy"] = strategy
        
        print(f"[{datetime.now()}] Scan Complete. Found {len(active_signals)} signals. Sleeping for 5 min...")
        await asyncio.sleep(300) # 5 minutes

@app.get("/api/signals")
def get_active_signals(strategy: str = "composite"):
    """
    Returns cached signals for 'composite' strategy to be instant.
    """
    # If user asks for composite (default), return cache instantly
    if strategy == "composite":
        # If cache is empty (server just started), we might return empty or block once?
        # Returning empty allows UI to load. Background task will populate it shortly.
        return {"strategy": strategy, "signals": MARKET_CACHE["signals"], "last_updated": MARKET_CACHE["timestamp"]}
    
    # Fallback for other strategies (non-cached, still blocking but rarely used on main load)
    return scan_market_manual(strategy)

def scan_market_manual(strategy):
    # Old logic for on-demand scan
    tickers = data_handler.get_nifty50_tickers()
    active_signals = []
    
    for ticker in tickers:
        try:
            df_5m = data_handler.fetch_data(ticker, period="5d", interval="5m")
            if df_5m.empty: continue
            
            df_1h = pd.DataFrame() # Other strategies might not need 1H or we fetch it if needed
            if strategy == 'composite':
                 df_1h = data_handler.fetch_data(ticker, period="3mo", interval="1h")
            
            signal, atr = strategy_engine.generate_signal(ticker, df_5m, df_1h, strategy_type=strategy)
            
            if signal:
                latest = df_5m.iloc[-1]
                features = strategy_engine.add_indicators(df_5m)[['RSI', 'Dist_VWAP', 'Z_Score_VWAP', 'volume']].iloc[[-1]]
                conf = strategy_engine.get_ml_confidence(ticker, features)
                
                active_signals.append({
                    "ticker": ticker,
                    "signal": signal,
                    "price": latest['close'],
                    "atr": atr,
                    "confidence": conf,
                    "timestamp": datetime.now().isoformat()
                })
        except:
            continue
            
    return {"strategy": strategy, "signals": active_signals}
    
# --- FRONTEND SERVING (Full Stack) ---
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Mount Assets (JS, CSS)
# Check if dist exists (it might not locally if not built, but we just built it)
if os.path.exists("web_ui/dist/assets"):
    app.mount("/assets", StaticFiles(directory="web_ui/dist/assets"), name="assets")

@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    """
    Serve the React App for any path not matched by the API above.
    This enables React Router to handle client-side routing.
    """
    # If API path was missed above, it falls here. 
    # But we want to ensure we don't return index.html for api 404s if possible, 
    # but for simplicity in SPA, we often do.
    # Check if it looks like an API call
    if full_path.startswith("api/") or full_path.startswith("data/"):
        raise HTTPException(status_code=404, detail="Not Found")
        
    # Serve index.html
    if os.path.exists("web_ui/dist/index.html"):
        return FileResponse("web_ui/dist/index.html")
    else:
        return "React Frontend not found. Run 'npm run build' in web_ui folder."

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=True)
