import requests
import json

# Fetch juste 5 marchés
url = "https://gamma-api.polymarket.com/markets"
params = {"closed": "false", "limit": 5}
resp = requests.get(url, params=params, timeout=30)
markets = resp.json()

for m in markets:
    print("=" * 60)
    question = m.get("question", "N/A")[:60]
    print(f"Question: {question}")
    
    outcomes = m.get("outcomes")
    prices_raw = m.get("outcomePrices")
    
    print(f"outcomes type: {type(outcomes)}, value: {outcomes}")
    print(f"outcomePrices type: {type(prices_raw)}, value: {prices_raw}")
    
    # Parse prices
    if isinstance(prices_raw, str) and prices_raw:
        try:
            prices = json.loads(prices_raw)
            print(f"Parsed from JSON string: {prices}")
        except Exception as e:
            print(f"JSON parse error: {e}")
            prices = []
    elif isinstance(prices_raw, list):
        prices = prices_raw
        print(f"Already a list: {prices}")
    else:
        prices = []
        print(f"No prices found")
    
    # Find YES
    price_yes = None
    if outcomes and prices:
        for i, outcome in enumerate(outcomes):
            print(f"  Checking [{i}]: outcome='{outcome}', lower='{outcome.lower() if isinstance(outcome, str) else outcome}'")
            if isinstance(outcome, str) and outcome.lower() == "yes" and i < len(prices):
                try:
                    price_yes = float(prices[i])
                    print(f"  -> Found YES price: {price_yes}")
                except Exception as e:
                    print(f"  -> Error converting price: {e}")
                break
    
    print(f"Final price_yes: {price_yes}")
    print()
