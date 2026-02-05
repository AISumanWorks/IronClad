import requests
import json

url = "http://localhost:8000/api/data/RELIANCE.NS"
print(f"Fetching from {url}...")

try:
    res = requests.get(url)
    if res.status_code == 200:
        data = res.json()
        print("Success!")
        print(f"Ticker: {data['ticker']}")
        results = data['data']
        print(f"Count: {len(results)}")
        if results:
            print("First Item:")
            print(json.dumps(results[0], indent=2))
            print("Last Item:")
            print(json.dumps(results[-1], indent=2))
            
            # Check for nulls
            nulls = 0
            for item in results:
                if item['close'] is None:
                    nulls += 1
            print(f"Null Closes: {nulls}")
    else:
        print(f"Failed: {res.status_code}")
        print(res.text)

except Exception as e:
    print(f"Error: {e}")
