# KLineAPI - A股实时行情 API

> 零配置 · 毫秒级响应 · 一站式A股数据接口

[![GitHub Stars](https://img.shields.io/github/stars/kraine2008-ux/klineapi?style=social)](https://github.com/kraine2008-ux/klineapi)
[![GitHub Stars](https://img.shields.io/github/stars/kraine2008-ux/klineapi?style=social)](https://github.com/kraine2008-ux/klineapi)
[![Website](https://img.shields.io/badge/%E5%AE%98%E7%BD%91-klineapi.com-blue)](https://klineapi.com)
[![API Docs](https://img.shields.io/badge/API%E6%96%87%E6%A1%A3-%E5%9C%A8%E7%BA%BF-green)](https://klineapi.com/docs)
[![Register](https://img.shields.io/badge/%E5%85%8D%E8%B4%B9%E6%B3%A8%E5%86%8C-%E7%AB%8B%E5%8D%B3%E8%8E%B7%E5%8F%96APIKey-orange)](https://klineapi.com/register)
![Python](https://img.shields.io/badge/Python-3.10+-yellow)
![FastAPI](https://img.shields.io/badge/FastAPI-%E2%9A%A1-teal)

**KLineAPI** 提供 A 股实时行情 RESTful API，覆盖实时报价、五档盘口、分时K线、集合竞价、涨停板监控、全市场排行等核心功能。注册即用，毫秒级响应。

- Website: https://klineapi.com
- API Docs: https://klineapi.com/docs
- Free Register: https://klineapi.com/register
- CLI Tool: https://github.com/kraine2008-ux/klineapi-cli

---

## Quick Start

### 1. Get API Key

```bash
# One-liner register
curl https://klineapi.com/v1/register

# Or register at: https://klineapi.com/register
```

### 2. Call API

```bash
# Real-time quote
curl "https://klineapi.com/v1/quote?code=600519&key=YOUR_API_KEY"

# Today's limit-up stocks
curl "https://klineapi.com/v1/limit-up?key=YOUR_API_KEY"

# Market indices
curl "https://klineapi.com/v1/market?key=YOUR_API_KEY"
```

### Python

```python
import httpx
r = httpx.get("https://klineapi.com/v1/quote",
    params={"code": "600519", "key": "YOUR_API_KEY"})
print(r.json())
# {'code': '600519', 'name': '贵州茅台', 'price': 1888.00, ...}
```

### CLI (pip install)

```bash
pip install klineapi-cli
klineapi quote 600519
klineapi limit-up
klineapi market
```

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /v1/quote` | Real-time quote (price, change, volume) |
| `GET /v1/orderbook` | Level-2 order book (bid/ask 5) |
| `GET /v1/intraday` | 1-min intraday K-line data |
| `GET /v1/auction` | Call auction (open/close) |
| `GET /v1/limit-up` | Limit-up stocks monitor |
| `GET /v1/board` | Full market ranking by % change |
| `GET /v1/market` | Major indices (SH/SZ/ChiNext) |
| `GET /v1/register` | Get an API key instantly |

---

## Features

- **Zero config** - No software installation, just curl
- **Millisecond response** - Real-time aggregated data
- **Full coverage** - Shanghai, Shenzhen, Beijing, STAR, ChiNext
- **Smart limit-up pool** - Auto-filter by board type, exclude ST stocks
- **Call auction** - Open (9:15-9:25) and close (14:57-15:00) data

---

## Pricing

| Plan | Free | Pro | Enterprise |
|------|------|-----|------------|
| **Price** | **$0** | **$7/month** | **$42/month** |
| Daily calls | 100 | 10,000 | 100,000 |
| Rate limit | 10/sec | 50/sec | 200/sec |
| All endpoints | Yes | Yes | Yes |
| Priority support | - | - | Yes |

[Upgrade Plan](https://klineapi.com/payment/plans)

---

## Why KLineAPI?

| Feature | KLineAPI | Paid Terminals | Self-built |
|---------|----------|---------------|------------|
| Setup time | 1 minute | Days | Days/weeks |
| Latency | Millisecond | Millisecond | Seconds |
| Cost | Free tier | $$$ | Server + dev |
| Reliability | High | High | Low |
| Code needed | 1 curl | - | 100s of lines |

---

## Contributing

- Report bugs: [New Issue](https://github.com/kraine2008-ux/klineapi/issues/new)
- Feature requests: [New Issue](https://github.com/kraine2008-ux/klineapi/issues/new)
- PRs welcome!

---

**If you find this useful, please give it a Star!** :star:
