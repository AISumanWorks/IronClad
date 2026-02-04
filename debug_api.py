import requests
import json
import time

try:
    print("Requesting data...")
    start = time.time()
    response = requests.get("http://localhost:8000/data/RELIANCE.NS")
    end = time.time()
    print(f"Response received in {end-start:.2f}s")
    
    if response.status_code == 200:
        data = response.json()
        print("Keys:", data.keys())
        if "data" in data and len(data["data"]) > 0:
            print("Item count:", len(data["data"]))
            first_item = data["data"][0]
            print("First item:", json.dumps(first_item, indent=2))
        else:
            print("Data list is empty")
    else:
        print("Error:", response.status_code, response.text)

except Exception as e:
    print("Exception:", e)
