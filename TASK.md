# KLineAPI v3.0 重开发任务书

## 项目背景
这是一个 A股实时行情 API 服务网站（klineapi.com），现在要重新开发一个 **SEO 优化 + 界面美化 + 更专业** 的版本。当前服务器跑的是 Flask 旧版（5860端口），功能完整但界面简陋、无 SEO。

## 技术栈要求
- Python 3.11+ / Flask（保持简单，不要用 FastAPI）
- SQLite 数据库（单文件 kline.db，方便部署）
- 前端：原生 HTML/CSS/JS + 内嵌样式（不引入 npm 构建，保持零依赖部署简单）
- 全部文件编码 UTF-8，源码字符串统一用单引号

## 必须实现的功能（与现有版本一致）

### 1. 用户系统
- 注册（用户名/邮箱/密码≥6位，bcrypt 加密）
- 登录/登出（Flask session）
- 注册后自动生成 API Key（kline_ 开头 + md5 截断16位）

### 2. 套餐管理
- 三档：free（0元，100次/日，10次/分）、pro（49元/月，10000次/日，100次/分）、enterprise（299元/月，100000次/日，不限速）
- 订单表 + 支付页（支付宝二维码占位，qr_exists 判断）
- 管理员手动激活 /activate/<tier>

### 3. API Key 管理
- 控制台可查看已有 key、生成新 key
- 限流：内存计数器（每日+每分钟），超限返回 429

### 4. 数据接口（全部需要 API Key，?key= 或 X-API-Key 头）
- GET /v1/quote?code=600519 - 实时行情（腾讯源，含五档盘口）
- GET /v1/batch?codes=a,b,c - 批量行情
- GET /v1/top?limit=50 - 全市场涨幅排行（新浪源）
- GET /v1/index - 主要指数（上证/深成/创业板/沪深300/科创50）
- GET /v1/limit_up - 涨停池（新浪源，按板块规则过滤 ST/主板9.5%/创业板科创板19.5%/北交所29.5%）
- GET /v1/orderbook?code= - 五档盘口（复用 quote 数据）
- GET /v1/intraday?code= - 分时K线（腾讯分时接口）
- GET /v1/auction?code= - 集合竞价（9:15-9:25 + 14:57）
- GET /v1/market - 大盘指数（同 /v1/index 别名）
- GET /v1/board - 全市场排行（同 /v1/top 别名）
- GET /v1/status - 服务状态（用户数等）

### 5. 网页页面
- / - 首页（专业 landing page）
- /pricing - 套餐页
- /docs - API 文档页
- /register - 注册页
- /login - 登录页
- /dashboard - 控制台（API Key 管理 + 用量统计 + 最近调用日志）
- /subscribe/<tier> - 下单支付页

## SEO 要求（重点！）
所有页面模板必须包含：
1. `<title>` 每个页面独立且含关键词
2. meta description / keywords
3. Open Graph 标签（og:title, og:description, og:type, og:url, og:image）
4. Twitter Card 标签（twitter:card, twitter:title, twitter:description）
5. JSON-LD 结构化数据（Organization + WebSite + Product/API 类型）
6. canonical 链接
7. robots.txt + sitemap.xml（含全部页面 URL）+ indexnow_key.txt
8. 百度验证 meta（可选）
9. 语义化 HTML5 标签（header/nav/main/section/footer），h1-h3 层级清晰

## 界面美化要求（重点！）
- **专业深色科技风**（类似 Stripe/交易所风格），参考：深蓝黑背景 #0a0e17 系 + 金色/青色点缀
- 首页要有一眼专业的 hero 区：大标题 + 副标题 + CTA 按钮 + 终端代码示例窗口（展示 curl 调用）
- 数据指标区（毫秒级响应/99.9%可用率/覆盖全市场等）
- 三档套餐卡片（免费/专业/企业，专业版高亮）
- API 接口列表区（带图标）
- 文档页排版专业（代码块高亮、参数表格）
- 响应式设计（移动端适配）
- 字体用系统字体栈：-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif
- 禁用 emoji 当图标，用 SVG 或 CSS

## 部署要求
- 单文件 app.py（或 app/ 包结构）+ templates/ + static/
- requirements.txt：flask, bcrypt, requests
- 运行命令：python app.py（默认 5860 端口，支持 --port 参数）
- 数据库自动初始化（首次运行建表）
- 时间显示用 Asia/Shanghai

## 验收标准
1. python app.py 能直接启动，浏览器访问首页正常
2. 注册→登录→控制台看到 API Key→调用 /v1/quote?code=600519&key=xxx 返回真实行情
3. 每个页面源码包含 SEO meta 标签
4. robots.txt / sitemap.xml 可访问
5. 界面看起来专业、现代、无乱码

请开始开发。完成后运行 python app.py 并 curl 验证关键接口。
