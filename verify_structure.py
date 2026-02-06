from modules.paper_trader import PaperTrader
import json

try:
    pt = PaperTrader()
    summary = pt.get_account_summary()
    print("\n--- Account Summary Keys ---")
    print(list(summary.keys()))
    
    if "cash" in summary:
        print("✅ SUCCESS: 'cash' key found (Matches Frontend)")
    else:
        print("❌ FAILURE: 'cash' key MISSING")

    portfolio = pt.get_holdings()
    print("\n--- Portfolio Data ---")
    print(portfolio)

except Exception as e:
    print(f"Error: {e}")
