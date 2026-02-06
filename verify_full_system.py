import requests
import time
import json
import sys

BASE_URL = "http://localhost:8000"
API_PREFIX = "/api"

def print_pass(msg):
    print(f"✅ PASS: {msg}")

def print_fail(msg):
    print(f"❌ FAIL: {msg}")

def test_endpoint(method, endpoint, payload=None, expected_code=200):
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=payload)
        
        if response.status_code == expected_code:
            print_pass(f"{method} {endpoint} returned {response.status_code}")
            return response.json()
        else:
            print_fail(f"{method} {endpoint} returned {response.status_code}. Expected {expected_code}")
            print(response.text)
            return None
    except Exception as e:
        print_fail(f"Could not connect to {url}: {e}")
        return None

def run_tests():
    print("🚀 Starting Full System Verification...\n")

    # 1. Health Check
    print("--- 1. Testing Core API ---")
    data = test_endpoint("GET", f"{API_PREFIX}/health")
    if not data: return

    # 2. Tickers
    print("\n--- 2. Testing Data Handler ---")
    data = test_endpoint("GET", f"{API_PREFIX}/tickers")
    if data and len(data.get("tickers", [])) > 0:
        print_pass(f"Fetched {len(data['tickers'])} tickers")
        ticker = data['tickers'][0]
    else:
        print_fail("No tickers returned")
        return

    # 3. Market Data
    print(f"\n--- 3. Testing Market Data ({ticker}) ---")
    data = test_endpoint("GET", f"{API_PREFIX}/data/{ticker}")
    if data and len(data.get("data", [])) > 0:
        print_pass("Historical data fetched successfully")
    else:
        print_fail("Market data empty")

    # 4. Account & Portfolio
    print("\n--- 4. Testing Account & Portfolio ---")
    acc = test_endpoint("GET", f"{API_PREFIX}/account")
    if acc:
        print(f"   Current Balance: {acc.get('balance')}")
    
    # 5. Simulate Trade
    print("\n--- 5. Testing Trading Engine ---")
    trade_payload = {
        "ticker": ticker,
        "action": "BUY",
        "qty": 1,
        "price": 100.0,
        "strategy": "test_script"
    }
    trade_res = test_endpoint("POST", f"{API_PREFIX}/trade", trade_payload)
    
    if trade_res and trade_res.get("status") == "success":
        print_pass("Trade executed successfully")
        
        # Verify in Portfolio
        port = test_endpoint("GET", f"{API_PREFIX}/portfolio")
        found = False
        for pos in port.get("positions", []):
            if pos['ticker'] == ticker:
                found = True
                print_pass(f"Ticker {ticker} found in portfolio with qty {pos['qty']}")
                break
        if not found:
            print_fail("Trade executed but not found in portfolio!")
    else:
        print_fail("Trade execution failed")

    # 6. Signals
    print("\n--- 6. Testing Signal Scanner ---")
    signals = test_endpoint("GET", f"{API_PREFIX}/signals")
    if signals:
        print_pass("Signals endpoint accessible")
    
    # 7. Frontend Static Files (Root)
    print("\n--- 7. Testing Static File Serving ---")
    try:
        res = requests.get(BASE_URL)
        if res.status_code == 200:
            if "<!doctype html>" in res.text.lower():
                print_pass("Root URL serves index.html")
            else:
                print_fail("Root URL returned 200 but content doesn't look like HTML")
        else:
            print_fail(f"Root URL returned {res.status_code}")
    except:
        print_fail("Could not access Root URL")

    print("\n✅ Verification Complete.")

if __name__ == "__main__":
    run_tests()
