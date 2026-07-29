# 📈 KLineAPI - A股实时行情 API

> **上线即用 · 毫秒级响应 · 零维护**  
> A股实时行情数据接口，免费注册获取 API Key，即开即用

🌐 **[https://klineapi.com](https://klineapi.com)** · 📖 [API 文档](https://klineapi.com/docs) · 🚀 [免费注册](https://klineapi.com/register)

---

## 简介

KLineAPI 提供 A 股实时行情 RESTful API 服务，覆盖实时报价、五档盘口、分时 K 线、集合竞价、涨停监控、市场排行等核心场景。所有数据来自腾讯行情 + 新浪财经 + Baostock 多源聚合，毫秒级响应。

适合量化交易、自动化策略、行情监控、Web/移动端展示等场景。

---

## API 接口

所有接口需要 API Key，可通过 `?key=` 查询参数或 `X-API-Key` HTTP Header 传递。

### 实时行情

```
GET https://klineapi.com/v1/quote?code=<股票代码>&key=<API Key>
```

**参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | string | 是 | 股票代码，如 `600519`、`000001`、`600519.SH` |
| `key` | string | 是 | API Key |

**示例**

```bash
curl "https://klineapi.com/v1/quote?code=600519&key=你的APIKey"
```

**响应**

```json
{
  "name": "贵州茅台",
  "price": 1888.88,
  "change_pct": 2.35
}
```

### 五档盘口

```
GET https://klineapi.com/v1/orderbook?code=<股票代码>&key=<API Key>
```

**示例**

```bash
curl "https://klineapi.com/v1/orderbook?code=600519&key=你的APIKey"
```

**响应**

```json
{
  "code": "600519",
  "name": "贵州茅台",
  "price": 1888.88,
  "bids": [
    {"price": 1888.00, "volume": 120},
    {"price": 1887.00, "volume": 85},
    ...
  ],
  "asks": [
    {"price": 1889.00, "volume": 60},
    {"price": 1890.00, "volume": 45},
    ...
  ]
}
```

### 分时K线

```
GET https://klineapi.com/v1/intraday?code=<股票代码>&key=<API Key>
```

获取当日 1 分钟分时 K 线数据。

```bash
curl "https://klineapi.com/v1/intraday?code=600519&key=你的APIKey"
```

### 集合竞价

```
GET https://klineapi.com/v1/auction?code=<股票代码>&key=<API Key>
```

获取开盘（9:15-9:25）和收盘（14:57-15:00）集合竞价数据。

```bash
curl "https://klineapi.com/v1/auction?code=600519&key=你的APIKey"
```

### 涨停池

```
GET https://klineapi.com/v1/limit-up?key=<API Key>
```

获取当前所有涨停股票列表，包含封单量、换手率、成交额等信息。

```bash
curl "https://klineapi.com/v1/limit-up?key=你的APIKey"
```

**响应**

```json
{
  "count": 35,
  "stocks": [
    {"code": "002952", "name": "亚世光电", "changepercent": 10.03, "封单": 2.5},
    {"code": "603863", "name": "松炀资源", "changepercent": 10.01, "封单": 1.8}
  ]
}
```

### 全市场排行

```
GET https://klineapi.com/v1/board?key=<API Key>
```

获取全市场涨幅排行（前 1000 只），按涨幅降序排列。

```bash
curl "https://klineapi.com/v1/board?key=你的APIKey"
```

### 大盘指数

```
GET https://klineapi.com/v1/market?key=<API Key>
```

获取主要指数实时数据：

| 指数 | 代码 |
|------|------|
| 上证指数 | 000001 |
| 深证成指 | 399001 |
| 创业板指 | 399006 |
| 沪深300 | 000300 |
| 科创50 | 000688 |

```bash
curl "https://klineapi.com/v1/market?key=你的APIKey"
```

### 注册获取 API Key

```
GET https://klineapi.com/v1/register
```

无需参数，直接返回一个免费 API Key。

```bash
curl "https://klineapi.com/v1/register"
```

**响应**

```json
{
  "api_key": "kline_a1b2c3d4e5f6...",
  "tier": "free"
}
```

---

## 快速开始

### 1. 获取 API Key

```bash
curl https://klineapi.com/v1/register
```

或访问 [klineapi.com/register](https://klineapi.com/register) 注册账号。

### 2. 调用 API

```bash
# 查询茅台实时行情
curl "https://klineapi.com/v1/quote?code=600519&key=你的APIKey"

# 获取涨停池
curl "https://klineapi.com/v1/limit-up?key=你的APIKey"

# 查看大盘指数
curl "https://klineapi.com/v1/market?key=你的APIKey"
```

### Python

```python
import httpx

API_KEY = "你的APIKey"

# 实时行情
resp = httpx.get("https://klineapi.com/v1/quote", params={
    "code": "600519", "key": API_KEY
})
print(resp.json())

# 涨停池
resp = httpx.get("https://klineapi.com/v1/limit-up", params={"key": API_KEY})
print(resp.json())
```

### JavaScript

```javascript
const API_KEY = '你的APIKey';

// 实时行情
fetch(`https://klineapi.com/v1/quote?code=600519&key=${API_KEY}`)
  .then(r => r.json())
  .then(console.log);
```

---

## 定价

| 套餐 | 免费版 | 专业版 | 企业版 |
|------|--------|--------|--------|
| **价格** | **¥0** | **¥49/月** | **¥299/月** |
| 每日调用 | 100次 | 10,000次 | 100,000次 |
| 速率限制 | 10次/分 | 50次/分 | 200次/分 |
| 实时行情 | ✅ | ✅ | ✅ |
| 涨停池 | ✅ | ✅ | ✅ |
| 五档盘口 | ❌ | ✅ | ✅ |
| 集合竞价 | ❌ | ✅ | ✅ |
| 分时K线 | ❌ | ✅ | ✅ |
| 全市场排行 | ❌ | ✅ | ✅ |
| 大盘指数 | ❌ | ✅ | ✅ |
| 专属支持 | ❌ | ❌ | ✅ |

[立即升级 →](https://klineapi.com/dashboard)

---

## 技术栈

- **框架**: FastAPI (Python)
- **数据源**: 腾讯行情 + 新浪财经 + Baostock
- **部署**: Nginx + SSL + systemd

---

## 关于

KLineAPI 致力于为开发者提供简单、稳定、低延迟的 A 股实时行情数据服务。

- 🌐 官网: [https://klineapi.com](https://klineapi.com)
- 📖 文档: [https://klineapi.com/docs](https://klineapi.com/docs)
- 🚀 注册: [https://klineapi.com/register](https://klineapi.com/register)
- 🐛 Issues: [GitHub Issues](https://github.com/kraine2008-ux/klineapi/issues)

**如果这个项目对你有帮助，请点 ⭐ Star 支持！**
