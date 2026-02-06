import yfinance as yf
import pandas as pd
import datetime
import time
from modules.system_logger import logger

class DataHandler:
    """
    Handles data fetching and processing for the IronClad Trading System.
    Designed to be modular: yfinance can be replaced with a broker API.
    """
    
    def __init__(self):
        # Top 15 Nifty 50 stocks by weight for this implementation
        self.tickers = [
            "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
            "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
            "LTIM.NS", "AXISBANK.NS", "LT.NS", "BAJFINANCE.NS", "MARUTI.NS",
            "^NSEI", "^NSEBANK"
        ]
        
    def get_nifty50_tickers(self):
        """Returns the list of Nifty 50 tickers."""
        return self.tickers

    def fetch_data(self, ticker: str, period: str = "1mo", interval: str = "5m"):
        """
        Fetches historical data using yf.Ticker.history() which is more reliable for single requests.
        """
        for attempt in range(3):
            try:
                # print(f"Fetching {interval} data for {ticker} (Attempt {attempt+1})...")
                # Use Ticker object
                dat = yf.Ticker(ticker)
                
                # Check if we got a valid object
                if dat is None:
                    continue

                df = dat.history(period=period, interval=interval, auto_adjust=True)
                
                if df is None or df.empty:
                    # Try without auto_adjust if empty (some tickers issues)
                    df = dat.history(period=period, interval=interval, auto_adjust=False)
                    
                if df is None or df.empty:
                    # print(f"Warning: No data fetched for {ticker}")
                    time.sleep(1)
                    continue

                # Clean columns
                df.columns = [c.lower() for c in df.columns]
                
                # Ensure index is datetime and localized?
                # yfinance returns timezone-aware index usually.
                
                return df
                
            except TypeError as te:
                if "'NoneType' object is not subscriptable" in str(te):
                    # Common yfinance error when data is missing upstream
                    # print(f"Warning: Data missing for {ticker} (yfinance internal error)")
                    time.sleep(1)
                    continue
                logger.log(f"Error fetching data for {ticker}: {te}", "ERROR")
                time.sleep(1)
            except Exception as e:
                logger.log(f"Error fetching data for {ticker}: {e}", "ERROR")
                time.sleep(1)
        
        return pd.DataFrame()

    def get_latest_price(self, ticker: str):
        """
        Gets the real-time/latest close price.
        Useful for position sizing calculations.
        """
        df = self.fetch_data(ticker, period="1d", interval="1m")
        if not df.empty:
            return df['close'].iloc[-1]
        return None
