# KLineAPI Python SDK

Simple Python client for [KLineAPI](https://klineapi.com).

## Install

```bash
pip install httpx
```

Or copy [klineapi_client.py](klineapi_client.py) into your project.

## Usage

```python
from klineapi_client import KLineAPI

api = KLineAPI("your_api_key_here")

# Market indices
market = api.market()
for idx in market["data"]:
    print(f"{idx['name']}: {idx['price']} ({idx['changepercent']}%)")

# Limit-up stocks
limit_up = api.limit_up()
for s in limit_up[:5]:
    print(f"{s['code']} {s['name']}: +{s['changepercent']}%")

# Real-time quote
moutai = api.quote("600519")
print(f"Moutai: {moutai['price']}")
```

## Methods

| Method | Description |
|--------|-------------|
| `quote(code)` | Real-time stock quote |
| `limit_up()` | Today limit-up stocks |
| `market()` | Market indices |
| `board(sort)` | Full market ranking |
| `sector()` | Sector ranking |

Get your free API key at [klineapi.com/register](https://klineapi.com/register)
