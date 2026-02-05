from modules.data_handler import DataHandler
import pandas as pd

dh = DataHandler()
ticker = "RELIANCE.NS"

print(f"Fetching data for {ticker}...")
try:
    df = dh.fetch_data(ticker, period="5d", interval="5m")
    print(f"Data fetched: {len(df)} rows")
    if not df.empty:
        print(df.head())
        print(df.tail())
    else:
        print("DataFrame is empty!")
except Exception as e:
    print(f"Error fetching data: {e}")
