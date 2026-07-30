# KLineAPI Python Example
# pip install httpx
import httpx

API = "https://klineapi.com/v1"
client = httpx.Client()

# Market indices
r = client.get(f"{API}/market")
print("=== Market ===")
for idx in r.json().get("data", []):
    print(f"  {idx['name']}: {idx['price']} ({idx.get('changepercent', '?')}%)")

# Limit-up stocks
r = client.get(f"{API}/limit-up")
data = r.json()
print(f"\n=== Limit-up ({len(data)} stocks) ===")
for s in data[:5]:
    print(f"  {s['code']} {s['name']}: +{s.get('changepercent', '?')}%")

# Quote
r = client.get(f"{API}/quote", params={"code": "600519"})
m = r.json()
print(f"\n=== Moutai ({m.get('code')}) ===")
print(f"  Price: {m.get('price')}")
print(f"  Change: {m.get('changepercent')}%")
print(f"  Turnover: {m.get('turnover', 'N/A')}")
