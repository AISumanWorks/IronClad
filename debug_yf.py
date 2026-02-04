import yfinance as yf

ticker = "INFY.NS"
print(f"Testing yfinance download for {ticker} with period='1y' interval='1h'...")
try:
    df = yf.download(ticker, period="1y", interval="1h", progress=False, auto_adjust=True)
    print("Download result type:", type(df))
    print(df.head())
    if df.empty:
        print("DataFrame is empty.")
except Exception as e:
    print("Error:", e)
