import requests
import json
from datetime import datetime

# Import config
import config

# Fetch markets
print("Fetching markets...")
url = "https://gamma-api.polymarket.com/markets"
all_markets = []
offset = 0

while len(all_markets) < 5000:  # Limite à 5000 pour le test
    params = {"closed": "false", "limit": 100, "offset": offset}
    resp = requests.get(url, params=params, timeout=30)
    batch = resp.json()
    if not batch:
        break
    all_markets.extend(batch)
    offset += len(batch)
    print(f"  Fetched {len(all_markets)}...")

print(f"\nTotal: {len(all_markets)} markets")

# Counters
stats = {
    "total": len(all_markets),
    "is_geopolitical": 0,
    "excluded": 0,
    "has_volume_10k": 0,
    "has_volume_5k": 0,
    "has_prices": 0,
    "price_in_range": 0,
    "has_tokens": 0,
    "has_timestamps": 0,
}

# Exemples pour debug
geo_examples = []
excluded_examples = []
no_price_examples = []
price_out_of_range_examples = []
no_volume_examples = []

current_ts = datetime.now().timestamp()

for m in all_markets:
    question = m.get("question", "")
    q_lower = question.lower()
    
    # Check geopolitical
    has_geo_kw = any(kw in q_lower for kw in config.GEO_KEYWORDS)
    has_exclude = any(excl in q_lower for excl in config.EXCLUDE_KEYWORDS)
    
    if has_exclude:
        stats["excluded"] += 1
        if len(excluded_examples) < 3:
            excluded_examples.append(question[:80])
        continue
    
    if has_geo_kw:
        stats["is_geopolitical"] += 1
        if len(geo_examples) < 5:
            geo_examples.append(question[:80])
    else:
        continue  # Skip non-geo
    
    # Check volume
    volume = float(m.get("volume", 0) or 0)
    if volume >= 5000:
        stats["has_volume_5k"] += 1
    if volume >= 10000:
        stats["has_volume_10k"] += 1
    else:
        if len(no_volume_examples) < 3:
            no_volume_examples.append(f"[Vol={volume:.0f}] {question[:60]}")
        continue
    
    # Check prices
    try:
        prices_raw = m.get("outcomePrices", "")
        if isinstance(prices_raw, str):
            prices = json.loads(prices_raw) if prices_raw else []
        else:
            prices = prices_raw or []
        
        outcomes = m.get("outcomes", [])
        price_yes = None
        
        for i, outcome in enumerate(outcomes):
            if outcome.lower() == "yes" and i < len(prices):
                price_yes = float(prices[i])
                break
        
        if price_yes is not None:
            stats["has_prices"] += 1
            
            if 0.20 <= price_yes <= 0.60:
                stats["price_in_range"] += 1
            else:
                if len(price_out_of_range_examples) < 3:
                    price_out_of_range_examples.append(f"[YES={price_yes:.1%}] {question[:60]}")
        else:
            if len(no_price_examples) < 3:
                no_price_examples.append(f"[outcomes={outcomes}, prices={prices_raw[:50] if prices_raw else 'N/A'}] {question[:50]}")
    except Exception as e:
        if len(no_price_examples) < 3:
            no_price_examples.append(f"[ERROR: {e}] {question[:50]}")
    
    # Check tokens
    clob_ids = m.get("clobTokenIds", [])
    if clob_ids and len(clob_ids) >= 2:
        stats["has_tokens"] += 1
    
    # Check timestamps
    start_date = m.get("startDate") or m.get("createdAt")
    end_date = m.get("endDate")
    if start_date and end_date:
        stats["has_timestamps"] += 1

# Report
print("\n" + "=" * 60)
print("FILTER FUNNEL")
print("=" * 60)
print(f"Total markets:           {stats['total']}")
print(f"  -> Excluded (sports/crypto/etc): {stats['excluded']}")
print(f"  -> Is geopolitical:     {stats['is_geopolitical']}")
print(f"    -> Volume >= 5k:      {stats['has_volume_5k']}")
print(f"    -> Volume >= 10k:     {stats['has_volume_10k']}")
print(f"    -> Has YES price:     {stats['has_prices']}")
print(f"    -> Price 20-60%:      {stats['price_in_range']}")
print(f"    -> Has CLOB tokens:   {stats['has_tokens']}")
print(f"    -> Has timestamps:    {stats['has_timestamps']}")

print("\n" + "=" * 60)
print("EXAMPLES: Geopolitical markets found")
print("=" * 60)
for ex in geo_examples:
    print(f"  OK: {ex}")

print("\n" + "=" * 60)
print("EXAMPLES: Excluded (matched exclusion keyword)")
print("=" * 60)
for ex in excluded_examples:
    print(f"  X: {ex}")

print("\n" + "=" * 60)
print("EXAMPLES: No/low volume")
print("=" * 60)
for ex in no_volume_examples:
    print(f"  $: {ex}")

print("\n" + "=" * 60)
print("EXAMPLES: Price out of range (not 20-60%)")
print("=" * 60)
for ex in price_out_of_range_examples:
    print(f"  %: {ex}")

print("\n" + "=" * 60)
print("EXAMPLES: Could not parse price")
print("=" * 60)
for ex in no_price_examples:
    print(f"  ?: {ex}")
