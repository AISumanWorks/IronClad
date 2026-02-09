import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from modules.data_handler import DataHandler
from modules.strategy_engine import StrategyEngine
from modules.system_logger import logger # Import Logger
import pandas as pd
import asyncio
from datetime import datetime

from modules.paper_trader import PaperTrader
from pydantic import BaseModel

# Initialize Core System
data_handler = DataHandler()
strategy_engine = StrategyEngine()
paper_trader = PaperTrader()

# Initialize Sentiment Engine
from modules.sentiment_engine import SentimentEngine, run_sentiment_scanner
sentiment_engine = SentimentEngine()

# Initialize Notification Manager
from modules.notification_manager import NotificationManager
notification_manager = NotificationManager()

class TradeRequest(BaseModel):
    ticker: str
    action: str # BUY / SELL
    qty: int
    price: float
    strategy: str = "manual"

# --- Global Cache ---
MARKET_CACHE = {
    "timestamp": None,
    "signals": {} # Keyed by strategy: "composite": [], "rsi_14": [] ...
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
    holdings = paper_trader.get_holdings() # List of dicts
    
    # Enrich with Live Data
    for p in holdings:
        try:
            # Fetch very brief data for latest price
            # We use 5m because 1m might be unstable or empty depending on yfinance
            df = data_handler.fetch_data(p['ticker'], period="1d", interval="5m")
            
            if not df.empty:
                current_price = float(df['close'].iloc[-1])
                p['current_price'] = current_price
                
                # Calculate P&L
                invested = p['avg_price'] * p['qty']
                current_value = current_price * p['qty']
                p['pnl'] = current_value - invested
                p['pnl_percent'] = (p['pnl'] / invested) * 100
            else:
                p['current_price'] = p['avg_price']
                p['pnl'] = 0.0
                p['pnl_percent'] = 0.0
        except:
             p['current_price'] = p['avg_price']
             p['pnl'] = 0.0
             p['pnl_percent'] = 0.0
             
    return {"positions": holdings}

@app.get("/api/history")
def get_trade_history():
    """Returns past executed trades."""
    return {"trades": paper_trader.get_history()}

@app.get("/api/predictions/{ticker}")
def get_predictions(ticker: str):
    """Returns AI predictions for the chart overlay."""
    return {"predictions": paper_trader.db.get_predictions(ticker)}

@app.get("/api/stats")
def get_ai_stats():
    """Returns AI Accuracy Statistics."""
    return paper_trader.db.get_accuracy_stats()

@app.get("/api/brain")
def get_brain_stats():
    """Returns Strategy Performance Stats (The Brain)."""
    df = paper_trader.db.get_strategy_stats()
    if df.empty:
        return {"strategies": []}
    return {"strategies": df.to_dict(orient='records')}

@app.get("/api/logs")
def get_system_logs():
    """Returns the latest 'thoughts' from the AI."""
    return {"logs": logger.get_logs()}

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

async def run_intraday_exit_loop():
    """Checks time every minute and closes positions at 3:15 PM."""
    loop = asyncio.get_running_loop()
    while True:
        now = datetime.now()
        # IST is UTC+5:30. Ensure system time is correct or handle offset.
        # Assuming system time is local IST (as per user context).
        if now.hour == 15 and now.minute >= 15: # 15:15 (3:15 PM)
             logger.log("⏰ INTRADAY EXIT: Market Closing. Squaring off all positions.", "VETO")
             holdings = paper_trader.get_holdings()
             for h in holdings:
                 try:
                     # Fetch price
                     df = data_handler.fetch_data(h['ticker'], period="1d", interval="5m")
                     price = float(df['close'].iloc[-1]) if not df.empty else h['avg_price']
                     
                     logger.log(f"📉 Squaring off {h['ticker']} at {price}", "TRADE")
                     paper_trader.execute_trade(h['ticker'], "SELL", price, h['qty'], "intraday_exit")
                 except Exception as e:
                     logger.log(f"Error squaring off {h['ticker']}: {e}", "ERROR")
             
             # Prevent re-firing immediately (sleep until 4 PM)
             await asyncio.sleep(3600) 
        
        await asyncio.sleep(60)

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
    loop = asyncio.get_running_loop()
    while True:
        try:
            print(f"[{datetime.now()}] Starting Background Market Scan (Threaded)...")
            
            # Run heavy scanning logic in a separate thread
            new_signals = await loop.run_in_executor(None, scan_market_sync)
            
            # Update Cache (Safe on main thread)
            MARKET_CACHE["signals"] = new_signals
            MARKET_CACHE["timestamp"] = datetime.now().isoformat()
            
            total = sum(len(v) for v in new_signals.values())
            print(f"[{datetime.now()}] Scan Complete. Found {total} signals. Sleeping for 5 min...")
            
        except Exception as e:
            print(f"Scanner Logic Error: {e}")

        await asyncio.sleep(300) 

@app.on_event("startup")
async def startup_event():
    """Start the background market scanner and validator on server startup."""
    asyncio.create_task(run_market_scanner())
    asyncio.create_task(run_validator_loop()) 
    asyncio.create_task(run_intraday_exit_loop()) # Intraday Logic
    
    # Start Sentiment Scanner:
    asyncio.create_task(run_sentiment_scanner(sentiment_engine, data_handler.get_nifty50_tickers()))

@app.get("/api/signals")
def get_active_signals(strategy: str = "composite"):
    """
    Returns cached signals for requested strategy.
    """
    # Check cache first
    cached_signals = MARKET_CACHE["signals"].get(strategy)
    
    if cached_signals is not None:
        return {
            "strategy": strategy, 
            "signals": cached_signals, 
            "last_updated": MARKET_CACHE["timestamp"]
        }
    
    # Fallback for strategies not in scanner (shouldn't happen with new logic, but safe to keep)
    return scan_market_manual(strategy)

def scan_market_manual(strategy):
    # Old logic for on-demand scan
    tickers = data_handler.get_nifty50_tickers()
    active_signals = []
    
    for ticker in tickers:
        try:
            df_5m = data_handler.fetch_data(ticker, period="5d", interval="5m")
            if df_5m.empty: continue
            
            df_1h = pd.DataFrame() 
            df_1d = pd.DataFrame()
            
            if strategy == 'composite':
                 df_1h = data_handler.fetch_data(ticker, period="3mo", interval="1h")
                 df_1d = data_handler.fetch_data(ticker, period="1y", interval="1d")
            
            signal, atr = strategy_engine.generate_signal(ticker, df_5m, df_1h, df_1d=df_1d, strategy_type=strategy)
            
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

def scan_market_sync():
    """Synchronous function containing the heavy market scanning logic."""
    STRATEGIES = ['composite', 'orb', 'supertrend', 'macd', 'bollinger', 'candlestick_pattern', 'rsi_14', 'rsi_9_aggressive', 'rsi_21_conservative']
    
    tickers = data_handler.get_nifty50_tickers()
    
    # --- FETCH SECTOR INDICES (Context for Phase 4) ---
    sector_data = {}
    try:
         bank_nifty = data_handler.fetch_data('^NSEBANK', period="5d", interval="5m")
         if not bank_nifty.empty: sector_data['^NSEBANK'] = bank_nifty
         
         nifty_50 = data_handler.fetch_data('^NSEI', period="5d", interval="5m")
         if not nifty_50.empty: sector_data['^NSEI'] = nifty_50
    except Exception as e:
         logger.log(f"Error fetching sector indices: {e}", "ERROR")
    
    new_signals = {s: [] for s in STRATEGIES}
    
    for ticker in tickers:
        try:
            logger.log(f"Scanning {ticker}...", "SCAN") # Log Scanning
            
            df_5m = data_handler.fetch_data(ticker, period="5d", interval="5m")
            if df_5m.empty: continue
            
            # --- STALE DATA CHECK (Market Closed Guard) ---
            # If data is older than 20 mins, market is likely closed. 
            # Don't generate fake signals on old candles.
            last_candle_time = df_5m.index[-1]
            if last_candle_time.tzinfo is None:
                # Localize if naive (assume local time/IST)
                last_candle_time = last_candle_time.replace(tzinfo=datetime.now().astimezone().tzinfo)
            
            # Compare with current time (aware)
            now = datetime.now().astimezone()
            
            if (now - last_candle_time).total_seconds() > 1200: # 20 minutes
                # logger.log(f"Skipping {ticker}: Data stale (Last: {last_candle_time.strftime('%H:%M')})", "DEBUG")
                continue
            
            if strategy_engine.models.get(ticker) is None:
                strategy_engine.train_model(ticker, df_5m)

            df_1h = data_handler.fetch_data(ticker, period="3mo", interval="1h")
            df_1d = data_handler.fetch_data(ticker, period="1y", interval="1d")
            
            sentiment_score = 0
            try: 
                if 'sentiment_engine' in globals():
                    sentiment_score = sentiment_engine.get_sentiment(ticker)
            except: pass
            
            for strategy in STRATEGIES:
                try:
                    signal, atr = strategy_engine.generate_signal(
                        ticker, df_5m, df_1h, df_1d=df_1d, strategy_type=strategy,
                        sector_data=sector_data, sentiment_score=sentiment_score
                    )
                    
                    if signal:
                        latest = df_5m.iloc[-1]
                        features = strategy_engine.add_indicators(df_5m)[['RSI', 'Dist_VWAP', 'Z_Score_VWAP', 'volume']].iloc[[-1]]
                        conf = strategy_engine.get_ml_confidence(ticker, features)
                        
                        sig_obj = {
                            "ticker": ticker, "signal": signal, "price": latest['close'],
                            "atr": atr, "confidence": conf, "sentiment": sentiment_score,
                            "timestamp": datetime.now().isoformat(), "strategy": strategy
                        }
                        new_signals[strategy].append(sig_obj)

                        # --- TELEGRAM ALERT ---
                        # Only alert for Composite strategy (High Quality) or High Confidence
                        if strategy == 'composite' and conf > 0.6:
                             # Run in try/except to not crash scanner
                             try:
                                 notification_manager.send_signal_alert(sig_obj)
                             except Exception as e:
                                 logger.log(f"Alert Error: {e}", "ERROR")

                        # --- AUTO-TRADING ENGINE ---
                        if strategy == 'composite' and conf > 0.60:
                            holdings = paper_trader.get_holdings()
                            already_owned = any(h['ticker'] == ticker for h in holdings)
                            
                            if not already_owned:
                                qty = 10
                                if conf < 0.70: qty = 5
                                elif conf > 0.90: qty = 20
                                elif conf > 0.80: qty = 15
                                logger.log(f"🤖 AUTO-TRADE TRIGGERED: Buying {ticker} (Conf: {conf:.2f}, Qty: {qty})", "TRADE")
                                paper_trader.execute_trade(ticker, "BUY", latest['close'], qty, "auto_ai")
                            
                            elif already_owned and signal == "SELL":
                                current_qty = next(h['qty'] for h in holdings if h['ticker'] == ticker)
                                logger.log(f"🤖 AUTO-TRADE TRIGGERED: Selling {ticker} (Signal: SELL, Qty: {current_qty})", "TRADE")
                                paper_trader.execute_trade(ticker, "SELL", latest['close'], current_qty, "auto_ai")
                except: continue
        except: continue
            
    return new_signals

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=True)
