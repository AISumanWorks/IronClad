import yfinance as yf

def test_fetch():
    ticker = "RELIANCE.NS"
    print(f"Testing fetch for {ticker}...")
    try:
        df = yf.download(ticker, period="60d", interval="5m", progress=False, auto_adjust=True)
        print("Data fetched:")
        print(df.head())
        print("Columns:", df.columns)
        if df.empty:
            print("DATAFRAME IS EMPTY")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_fetch()
