# KLineAPI Usage Examples

## Quick Start

### Register for free API key
curl https://klineapi.com/v1/register

### Real-time quote (Kweichow Moutai)
curl "https://klineapi.com/v1/quote?code=600519"

### Today limit-up stocks
curl "https://klineapi.com/v1/limit-up"

### Market indices
curl "https://klineapi.com/v1/market"

### Query with format param
curl "https://klineapi.com/v1/quote?code=600519&format=json"

### All market stocks sorted by change percent
curl "https://klineapi.com/v1/board?sort=changepercent"

### Single stock detail
curl "https://klineapi.com/v1/stock_detail?code=600519"
