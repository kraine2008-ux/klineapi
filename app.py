# -*- coding: utf-8 -*-
'''
KLineAPI v3.0 - A股实时行情 API 服务平台
SEO 优化 + 界面美化 + 更专业版本
运行: python app.py [--port 5860]
'''
import argparse
import hashlib
import json
import os
import random
import re
import sqlite3
import struct
import threading
import time
import zlib
from datetime import datetime, timedelta
from functools import wraps
from zoneinfo import ZoneInfo

import bcrypt
import requests
from flask import (Flask, abort, flash, jsonify, redirect,
                   render_template, request, session, url_for)
from flask import Response

# ---------------------------------------------------------------- 基础配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'kline.db')
SECRET_FILE = os.path.join(BASE_DIR, '.secret')
INDEXNOW_FILE = os.path.join(BASE_DIR, 'indexnow_key.txt')
SITE_URL = os.environ.get('SITE_URL', 'https://klineapi.com')
TZ = ZoneInfo('Asia/Shanghai')
DEFAULT_PORT = 5860
TDX_BASE = os.environ.get('TDX_API_URL', 'http://127.0.0.1:8001')
TDX_TIMEOUT = 8


def tdx_get(endpoint, params=None):
    """调用 tdx_api 服务, 失败返回 None (上层自动降级)"""
    try:
        url = f'{TDX_BASE}/api/{endpoint}'
        resp = requests.get(url, params=params, timeout=TDX_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None
START_TIME = time.time()

TIERS = {
    'free': {'name': '免费版', 'price': 0, 'day': 100, 'min': 10, 'period': '永久'},
    'pro': {'name': '专业版', 'price': 49, 'day': 10000, 'min': 100, 'period': '月'},
    'enterprise': {'name': '企业版', 'price': 299, 'day': 100000, 'min': None, 'period': '月'},
}

INDEX_LIST = [
    ('sh000001', '上证指数'),
    ('sz399001', '深证成指'),
    ('sz399006', '创业板指'),
    ('sh000300', '沪深300'),
    ('sh000688', '科创50'),
]

# 内存限流计数器: (user_id, date) -> count / (user_id, minute) -> count
_day_counts = {}
_min_counts = {}
_lock = threading.Lock()
_qr_cache = {}


def now_str():
    return datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')


def today_str():
    return datetime.now(TZ).strftime('%Y-%m-%d')


def minute_str():
    return datetime.now(TZ).strftime('%Y-%m-%d %H:%M')
# ---------------------------------------------------------------- Flask 初始化
def _load_secret():
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, 'r', encoding='utf-8') as f:
            secret = f.read().strip()
            if secret:
                return secret
    secret = hashlib.sha256(os.urandom(64)).hexdigest()
    with open(SECRET_FILE, 'w', encoding='utf-8') as f:
        f.write(secret)
    return secret


app = Flask(__name__)
app.config['SECRET_KEY'] = _load_secret()
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['JSON_AS_ASCII'] = False
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024


@app.context_processor
def inject_globals():
    return {
        'site_url': SITE_URL,
        'tiers': TIERS,
        'now_str': now_str(),
        'current_user': _current_user_row(),
    }


# ---------------------------------------------------------------- 数据库
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free',
            plan_expire TEXT,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            api_key TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tier TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            qr_token TEXT NOT NULL,
            created_at TEXT NOT NULL,
            paid_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS call_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            api_key TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            code TEXT,
            status INTEGER NOT NULL,
            ip TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_call_logs_user ON call_logs(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
        ''')
def _bootstrap_admin():
    user = os.environ.get('KLINE_ADMIN_USER') or 'admin'
    pw = os.environ.get('KLINE_ADMIN_PASS') or 'admin123'
    hashed = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    with get_db() as conn:
        row = conn.execute('SELECT id FROM users WHERE username = ?', (user,)).fetchone()
        if row:
            conn.execute('UPDATE users SET is_admin = 1, password = ? WHERE id = ?', (hashed, row['id']))
            uid = row['id']
        else:
            cur = conn.execute(
                'INSERT INTO users (username, email, password, plan, is_admin, created_at) VALUES (?, ?, ?, ?, 1, ?)',
                (user, user + '@klineapi.com', hashed, 'enterprise', now_str()))
            uid = cur.lastrowid
        # 确保 admin 有 API key
        existing_key = conn.execute('SELECT id FROM api_keys WHERE user_id = ?', (uid,)).fetchone()
        if not existing_key:
            key = gen_api_key()
            conn.execute('INSERT INTO api_keys (user_id, api_key, created_at) VALUES (?, ?, ?)',
                        [uid, key, now_str()])
            conn.commit()


def get_indexnow_key():
    if os.path.exists(INDEXNOW_FILE):
        with open(INDEXNOW_FILE, 'r', encoding='utf-8') as f:
            key = f.read().strip()
            if key:
                return key
    key = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
    with open(INDEXNOW_FILE, 'w', encoding='utf-8') as f:
        f.write(key)
    return key


def _current_user_row():
    uid = session.get('user_id')
    if not uid:
        return None
    with get_db() as conn:
        return conn.execute('SELECT * FROM users WHERE id = ?', (uid,)).fetchone()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            flash('请先登录', 'error')
            return redirect(url_for('login', next=request.path))
        return fn(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------- 工具函数
def gen_api_key():
    return 'kline_' + hashlib.md5(os.urandom(32)).hexdigest()[:16]


def tencent_symbol(code):
    code = (code or '').strip().lower()
    if re.match(r'^(sh|sz|bj)\d{6}$', code):
        return code
    if re.match(r'^\d{6}$', code):
        if code[0] == '6':
            return 'sh' + code
        if code[0] in ('0', '1', '3'):
            return 'sz' + code
        if code[0] in ('4', '8', '9'):
            return 'bj' + code
        if code[0] == '5':
            return 'sh' + code
    return 'sh' + code


def _num(fields, idx):
    try:
        val = fields[idx].strip()
        return float(val) if val else None
    except (IndexError, ValueError):
        return None


def _bid_ask(fields):
    bid, ask = [], []
    for i in range(5):
        bid.append({'price': _num(fields, 9 + i * 2), 'volume': _num(fields, 10 + i * 2)})
        ask.append({'price': _num(fields, 19 + i * 2), 'volume': _num(fields, 20 + i * 2)})
    return bid, ask
def fetch_tencent_quote(code):
    # 优先 tdx_api (本地历史库+3秒缓存)
    tdx = tdx_get('quote', {'code': code})
    if tdx and tdx.get('price'):
        bid = [{'price': tdx['bid_ask'][f'bid{i}']['price'], 'volume': tdx['bid_ask'][f'bid{i}']['vol']} for i in range(1, 6)]
        ask = [{'price': tdx['bid_ask'][f'ask{i}']['price'], 'volume': tdx['bid_ask'][f'ask{i}']['vol']} for i in range(1, 6)]
        return {
            'symbol': ('sh' if tdx.get('market') == 1 else 'sz') + code,
            'code': code, 'name': tdx.get('name', ''),
            'price': tdx['price'], 'pre_close': tdx['last_close'],
            'open': tdx['open'], 'volume': tdx.get('volume'),
            'high': tdx['high'], 'low': tdx['low'],
            'change_pct': tdx.get('change_pct'), 'amount': tdx.get('amount'),
            'time': tdx.get('servertime'),
            'bid': bid, 'ask': ask, 'source': 'klineapi-engine',
        }
    # 降级: 备用源
    symbol = tencent_symbol(code)
    url = 'https://qt.gtimg.cn/q=' + symbol
    resp = requests.get(url, timeout=8)
    resp.raise_for_status()
    text = resp.content.decode('gbk', errors='ignore')
    m = re.search(r'="([^"]+)"', text)
    if not m:
        return None
    f = m.group(1).split('~')
    if len(f) < 50 or not f[1]:
        return None
    bid, ask = _bid_ask(f)
    return {
        'symbol': symbol,
        'code': f[2],
        'name': f[1],
        'price': _num(f, 3),
        'pre_close': _num(f, 4),
        'open': _num(f, 5),
        'volume': _num(f, 6),
        'outer_volume': _num(f, 7),
        'inner_volume': _num(f, 8),
        'high': _num(f, 33),
        'low': _num(f, 34),
        'change': _num(f, 31),
        'change_pct': _num(f, 32),
        'amount': _num(f, 37),
        'turnover_rate': _num(f, 38),
        'pe': _num(f, 39),
        'pb': _num(f, 46),
        'amplitude': _num(f, 43),
        'float_market_cap': _num(f, 44),
        'total_market_cap': _num(f, 45),
        'limit_up': _num(f, 47),
        'limit_down': _num(f, 48),
        'volume_ratio': _num(f, 49),
        'avg_price': _num(f, 51),
        'time': f[30] if len(f) > 30 else None,
        'bid': bid,
        'ask': ask,
        'source': 'klineapi-engine',
    }


def fetch_tencent_batch(codes):
    result = []
    for code in codes:
        try:
            q = fetch_tencent_quote(code)
            if q:
                result.append({'code': q['code'], 'data': q})
            else:
                result.append({'code': code, 'error': '未找到该代码的行情'})
        except Exception as e:
            result.append({'code': code, 'error': '行情获取失败: ' + str(e)})
    return result


def _sina_market_page(page, num):
    url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
    params = {'page': page, 'num': num, 'sort': 'changepercent', 'asc': 0, 'node': 'hs_a', 'symbol': '', '_s_r_a': 'init'}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    text = re.sub(r'([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', resp.text)
    data = json.loads(text)
    return data if isinstance(data, list) else []


def fetch_sina_market(limit=50):
    limit = min(max(int(limit), 1), 100)
    return _sina_market_page(1, limit)


def fetch_sina_index():
    # 优先 tdx_api (指数接口已修复)
    tdx_indices = [
        ('000001', '上证指数'), ('399001', '深证成指'), ('399006', '创业板指'),
        ('000300', '沪深300'), ('000688', '科创50'), ('000016', '上证50'),
    ]
    results = []
    for icode, iname in tdx_indices:
        tdx = tdx_get('index', {'code': icode})
        if tdx and tdx.get('price'):
            results.append({
                'symbol': icode, 'name': tdx.get('name', iname),
                'price': tdx['price'], 'change_pct': tdx.get('change_pct', 0),
                'volume': tdx.get('vol'), 'amount': tdx.get('amount'),
            })
    if len(results) >= 4:
        return results
    # 降级: 备用源
    codes = ','.join('s_' + c for c, _ in INDEX_LIST)
    resp = requests.get('https://hq.sinajs.cn/list=' + codes,
                        headers={'Referer': 'https://finance.sina.com.cn'}, timeout=8)
    resp.raise_for_status()
    text = resp.content.decode('gbk', errors='ignore')
    result = []
    for line in text.strip().splitlines():
        m = re.search(r'hq_str_s_([a-z]+\d+)="(.*)"', line)
        if not m:
            continue
        parts = m.group(2).split(',')
        if len(parts) < 6:
            continue
        result.append({
            'symbol': m.group(1),
            'name': parts[0],
            'price': float(parts[1] or 0),
            'change': float(parts[2] or 0),
            'change_pct': float(parts[3] or 0),
            'volume': float(parts[4] or 0),
            'amount': float(parts[5] or 0),
        })
    return result
def fetch_tencent_intraday(code):
    # 优先 tdx_api (pytdx 分时)
    tdx = tdx_get('min', {'code': code})
    if tdx and tdx.get('items'):
        return {
            'symbol': tencent_symbol(code),
            'date': today_str(),
            'points': [{'time': it.get('time', ''), 'price': it['price'], 'volume': it['vol']} for it in tdx['items']],
            'source': 'klineapi-engine',
        }
    # 降级: 备用源
    symbol = tencent_symbol(code)
    resp = requests.get('https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=' + symbol, timeout=8)
    resp.raise_for_status()
    j = resp.json()
    node = j.get('data', {}).get(symbol, {})
    rows = node.get('data', {}).get('data', [])
    points = []
    for row in rows:
        parts = str(row).split(' ')
        item = {'time': parts[0] if parts else None}
        if len(parts) > 1:
            item['price'] = float(parts[1])
        if len(parts) > 2:
            item['volume'] = int(float(parts[2]))
        if len(parts) > 3:
            item['amount'] = float(parts[3])
        points.append(item)
    return {
        'symbol': symbol,
        'date': node.get('data', {}).get('date'),
        'points': points,
        'source': 'klineapi-engine',
    }


def board_threshold(code):
    if code.startswith('30') or code.startswith('688'):
        return 19.5
    if code[0] in ('4', '8', '9'):
        return 29.5
    return 9.5


def fetch_limit_up():
    items = []
    seen = set()
    for page in range(1, 11):
        try:
            data = _sina_market_page(page, 100)
        except Exception:
            break
        if not data:
            break
        qualified = False
        for s in data:
            code = str(s.get('code') or '')
            name = str(s.get('name') or '')
            pct = float(s.get('changepercent') or 0)
            if 'ST' in name.upper() or not re.match(r'^\d{6}$', code):
                continue
            threshold = board_threshold(code)
            if pct >= threshold and code not in seen:
                seen.add(code)
                items.append({
                    'symbol': s.get('symbol'),
                    'code': code,
                    'name': name,
                    'price': s.get('trade'),
                    'change_pct': pct,
                    'change': s.get('pricechange'),
                    'open': s.get('open'),
                    'high': s.get('high'),
                    'low': s.get('low'),
                    'volume': s.get('volume'),
                    'amount': s.get('amount'),
                    'turnover_rate': s.get('turnoverratio'),
                    'board': '创业板/科创板' if code.startswith('30') or code.startswith('688') else ('北交所' if code[0] in ('4', '8', '9') else '主板'),
                })
                qualified = True
        if not qualified:
            break
    return items
def auction_info(code):
    now = datetime.now(TZ)
    weekday = now.weekday()
    hm = now.strftime('%H:%M')
    status = 'closed'
    label = '非交易时段'
    if weekday < 5:
        if '09:15' <= hm < '09:20':
            status, label = 'auction_open', '集合竞价阶段（9:15-9:20 可撤单）'
        elif '09:20' <= hm <= '09:25':
            status, label = 'auction_locked', '集合竞价阶段（9:20-9:25 不可撤单）'
        elif '09:25' <= hm < '09:30':
            status, label = 'auction_done', '集合竞价结束，等待开盘'
        elif '09:30' <= hm < '11:30':
            status, label = 'trading', '上午连续竞价'
        elif '11:30' <= hm < '13:00':
            status, label = 'lunch', '午间休市'
        elif '13:00' <= hm < '14:57':
            status, label = 'trading', '下午连续竞价'
        elif '14:57' <= hm < '15:00':
            status, label = 'closing_auction', '收盘集合竞价（14:57-15:00）'
        elif hm >= '15:00':
            status, label = 'closed', '已收盘'
    quote = fetch_tencent_quote(code)
    if quote is None:
        raise ValueError('未找到该代码的行情')
    matched = quote['price'] if status in ('auction_open', 'auction_locked', 'closing_auction') else None
    return {
        'code': quote['code'],
        'symbol': quote['symbol'],
        'name': quote['name'],
        'status': status,
        'label': label,
        'matched_price': matched,
        'pre_close': quote['pre_close'],
        'open': quote['open'],
        'price': quote['price'],
        'volume': quote['volume'],
        'amount': quote['amount'],
        'time': quote['time'],
        'server_time': now_str(),
        'source': 'klineapi-engine',
    }


# ---------------------------------------------------------------- 限流
def _prune_counters():
    stale_day = (datetime.now(TZ) - timedelta(days=2)).strftime('%Y-%m-%d')
    stale_min = (datetime.now(TZ) - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M')
    for k in [k for k in _day_counts if k[1] < stale_day]:
        _day_counts.pop(k, None)
    for k in [k for k in _min_counts if k[1] < stale_min]:
        _min_counts.pop(k, None)


def check_rate_limit(user_id, plan):
    with _lock:
        _prune_counters()
        limits = TIERS[plan]
        dk = (user_id, today_str())
        mk = (user_id, minute_str())
        d = _day_counts.get(dk, 0)
        m = _min_counts.get(mk, 0)
        if d >= limits['day']:
            return False, 'daily'
        if limits['min'] is not None and m >= limits['min']:
            return False, 'minute'
        _day_counts[dk] = d + 1
        _min_counts[mk] = m + 1
        return True, None


def log_call(user_id, api_key, endpoint, code, status, ip=None):
    try:
        with get_db() as conn:
            conn.execute(
                'INSERT INTO call_logs (user_id, api_key, endpoint, code, status, ip, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (user_id, api_key, endpoint, code or '', status, ip or request.remote_addr, now_str()))
    except Exception:
        pass


def api_error(message, http_code):
    return {'code': http_code, 'message': message, 'timestamp': now_str()}


def api_success(data):
    return {'code': 0, 'message': 'ok', 'data': data, 'timestamp': now_str()}
def _authenticate():
    key = (request.args.get('key') or '').strip() or (request.headers.get('X-API-Key') or '').strip()
    if not key:
        return None, None, api_error('缺少 API Key，请通过 ?key= 参数或 X-API-Key 请求头传递', 401)
    with get_db() as conn:
        row = conn.execute('''
            SELECT k.api_key, k.user_id, u.username, u.plan, u.plan_expire
            FROM api_keys k JOIN users u ON u.id = k.user_id
            WHERE k.api_key = ?
        ''', (key,)).fetchone()
    if not row:
        return None, None, api_error('无效的 API Key', 401)
    plan = row['plan']
    if row['plan_expire'] and row['plan_expire'] < now_str():
        with get_db() as conn:
            conn.execute('UPDATE users SET plan = ?, plan_expire = ? WHERE id = ?', ('free', None, row['user_id']))
        plan = 'free'
    ok, reason = check_rate_limit(row['user_id'], plan)
    if not ok:
        if reason == 'daily':
            return None, None, api_error('今日调用次数已达上限（' + str(TIERS[plan]['day']) + ' 次/日），请升级套餐或明日再试', 429)
        return None, None, api_error('调用过于频繁，超过每分钟限额（' + str(TIERS[plan]['min']) + ' 次/分）', 429)
    return row, key, None


def api_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user, key, err = _authenticate()
        if err:
            return jsonify(err), err['code']
        kwargs['api_user'] = user
        kwargs['api_key'] = key
        try:
            result = fn(*args, **kwargs)
        except requests.RequestException:
            app.logger.exception('upstream request failed: %s', request.path)
            result = api_error('上游行情源暂时不可用，请稍后重试', 502)
        except Exception:
            app.logger.exception('internal error: %s', request.path)
            result = api_error('服务器内部错误', 500)
        status = result['code'] if result.get('code') != 0 else 200
        log_call(user['user_id'], key, request.path, request.args.get('code'), status)
        return jsonify(result), status
    return wrapper


# ---------------------------------------------------------------- 数据接口
@app.route('/v1/quote')
@api_required
def v1_quote(api_user, api_key):
    code = (request.args.get('code') or '').strip()
    if not code:
        return api_error('缺少参数 code（如 code=600519）', 400)
    q = fetch_tencent_quote(code)
    if q is None:
        return api_error('未找到代码 ' + code + ' 的行情数据', 404)
    return api_success(q)
@app.route('/v1/batch')
@api_required
def v1_batch(api_user, api_key):
    codes = (request.args.get('codes') or '').strip()
    if not codes:
        return api_error('缺少参数 codes（逗号分隔，如 codes=600519,000001）', 400)
    code_list = [c.strip() for c in codes.split(',') if c.strip()]
    if not code_list:
        return api_error('codes 参数格式不正确', 400)
    return api_success(fetch_tencent_batch(code_list))


@app.route('/v1/top')
@api_required
def v1_top(api_user, api_key):
    limit = (request.args.get('limit') or '50').strip()
    try:
        limit = int(limit)
    except ValueError:
        return api_error('limit 参数必须为数字', 400)
    data = fetch_sina_market(limit)
    return api_success({'limit': len(data), 'list': data})


@app.route('/v1/index')
@api_required
def v1_index(api_user, api_key):
    return api_success({'list': fetch_sina_index()})


@app.route('/v1/market')
@api_required
def v1_market(api_user, api_key):
    return api_success({'list': fetch_sina_index()})


@app.route('/v1/limit_up')
@api_required
def v1_limit_up(api_user, api_key):
    items = fetch_limit_up()
    return api_success({'count': len(items), 'list': items})


@app.route('/v1/orderbook')
@api_required
def v1_orderbook(api_user, api_key):
    code = (request.args.get('code') or '').strip()
    if not code:
        return api_error('缺少参数 code（如 code=600519）', 400)
    q = fetch_tencent_quote(code)
    if q is None:
        return api_error('未找到代码 ' + code + ' 的行情数据', 404)
    return api_success({
        'code': q['code'], 'symbol': q['symbol'], 'name': q['name'],
        'price': q['price'], 'time': q['time'],
        'bid': q['bid'], 'ask': q['ask'],
        'source': 'klineapi-engine',
    })
@app.route('/v1/intraday')
@api_required
def v1_intraday(api_user, api_key):
    code = (request.args.get('code') or '').strip()
    if not code:
        return api_error('缺少参数 code（如 code=600519）', 400)
    return api_success(fetch_tencent_intraday(code))


@app.route('/v1/auction')
@api_required
def v1_auction(api_user, api_key):
    code = (request.args.get('code') or '').strip()
    if not code:
        return api_error('缺少参数 code（如 code=600519）', 400)
    return api_success(auction_info(code))


@app.route('/v1/board')
@api_required
def v1_board(api_user, api_key):
    limit = (request.args.get('limit') or '50').strip()
    try:
        limit = int(limit)
    except ValueError:
        return api_error('limit 参数必须为数字', 400)
    data = fetch_sina_market(limit)
    return api_success({'limit': len(data), 'list': data})


@app.route('/v1/status')
@api_required
def v1_status(api_user, api_key):
    with get_db() as conn:
        user_count = conn.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']
        key_count = conn.execute('SELECT COUNT(*) AS c FROM api_keys').fetchone()['c']
        today_count = conn.execute(
            'SELECT COUNT(*) AS c FROM call_logs WHERE created_at LIKE ?', (today_str() + '%',)).fetchone()['c']
        order_count = conn.execute('SELECT COUNT(*) AS c FROM orders WHERE status = ?', ('pending',)).fetchone()['c']
    return api_success({
        'service': 'klineapi-v3',
        'status': 'ok',
        'uptime_seconds': int(time.time() - START_TIME),
        'server_time': now_str(),
        'timezone': 'Asia/Shanghai',
        'user_count': user_count,
        'api_key_count': key_count,
        'today_calls': today_count,
        'pending_orders': order_count,
        'rate_limits': TIERS,
    })


# ---------------------------------------------------------------- tdx_api 扩展端点
@app.route('/v1/kline')
@api_required
def v1_kline(api_user, api_key):
    """K线历史 (tdx_api 本地历史库, 30年数据)"""
    code = (request.args.get('code') or '').strip()
    if not code:
        return api_error('缺少参数 code（如 code=600519）', 400)
    period = (request.args.get('period') or 'day').strip().lower()
    # 字符串周期 → tdx_api 数字周期 (9=日K 5=周K 6=月K 0=5分 1=15分 2=30分 3=60分 8=1分 10=季K 11=年K)
    PERIOD_MAP = {'min1': 8, '1min': 8, '1m': 8, '5min': 0, '5m': 0, '15min': 1, '15m': 1,
                  '30min': 2, '30m': 2, '60min': 3, '1hour': 3, '60m': 3, 'hour': 3,
                  'day': 9, 'daily': 9, 'd': 9, 'week': 5, 'weekly': 5, 'w': 5,
                  'month': 6, 'monthly': 6, 'm': 6, 'quarter': 10, 'year': 11}
    period_num = PERIOD_MAP.get(period)
    if period_num is None:
        return api_error(f'period 参数无效: {period}（支持 day/week/month/5min/15min/30min/60min/min1）', 400)
    count = (request.args.get('count') or '100').strip()
    start = (request.args.get('start') or '').strip()
    end = (request.args.get('end') or '').strip()
    try:
        count = min(max(int(count), 1), 800)
    except ValueError:
        return api_error('count 参数必须为数字', 400)
    params = {'code': code, 'period': period_num, 'count': count}
    if start:
        params['start'] = start
    if end:
        params['end'] = end
    data = tdx_get('kline', params)
    if data is None:
        return api_error('tdx_api 不可用或该代码无K线数据', 502)
    return api_success(data)


@app.route('/v1/search')
@api_required
def v1_search(api_user, api_key):
    """股票搜索 (tdx_api 证券列表缓存)"""
    keyword = (request.args.get('keyword') or '').strip()
    if not keyword:
        return api_error('缺少参数 keyword', 400)
    limit = (request.args.get('limit') or '20').strip()
    try:
        limit = min(max(int(limit), 1), 50)
    except ValueError:
        return api_error('limit 参数必须为数字', 400)
    data = tdx_get('search', {'keyword': keyword})
    if data is None:
        return api_error('tdx_api 不可用', 502)
    return api_success({'keyword': keyword, 'count': data.get('total', 0),
                        'list': data.get('items', [])[:limit]})


@app.route('/v1/finance')
@api_required
def v1_finance(api_user, api_key):
    """财务指标 (tdx_api F10 财务数据)"""
    code = (request.args.get('code') or '').strip()
    if not code:
        return api_error('缺少参数 code（如 code=600519）', 400)
    ftype = (request.args.get('type') or 'financial').strip()
    data = tdx_get('finance', {'code': code, 'type': ftype})
    if data is None:
        return api_error('tdx_api 不可用或该代码无财务数据', 502)
    return api_success(data)


@app.route('/v1/north')
@api_required
def v1_north(api_user, api_key):
    """北向资金 (自有行情引擎)"""
    data = tdx_get('ak/north')
    if data is None:
        return api_error('北向资金数据不可用', 502)
    return api_success(data)


@app.route('/v1/lhb')
@api_required
def v1_lhb(api_user, api_key):
    """龙虎榜 (自有行情引擎)"""
    date = (request.args.get('date') or '').strip()
    params = {'date': date} if date else None
    data = tdx_get('ak/lhb', params)
    if data is None:
        return api_error('龙虎榜数据不可用', 502)
    return api_success(data)


@app.route('/v1/board_list')
@api_required
def v1_board_list(api_user, api_key):
    """板块行情 (tdx_api)"""
    btype = (request.args.get('type') or 'industry').strip()
    data = tdx_get('ak/sector_industry' if btype == 'industry' else 'ak/sector_concept')
    if data is None:
        return api_error('板块数据不可用', 502)
    return api_success(data)


# ---------------------------------------------------------------- 用户系统
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password') or ''
        if not re.match(r'^[\w\u4e00-\u9fa5]{3,32}$', username):
            flash('用户名需为 3-32 位字母、数字、下划线或中文', 'error')
        elif not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            flash('邮箱格式不正确', 'error')
        elif len(password) < 6:
            flash('密码长度至少 6 位', 'error')
        else:
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            try:
                with get_db() as conn:
                    cur = conn.execute(
                        'INSERT INTO users (username, email, password, plan, created_at) VALUES (?, ?, ?, ?, ?)',
                        (username, email, hashed, 'free', now_str()))
                    user_id = cur.lastrowid
                    key = gen_api_key()
                    conn.execute('INSERT INTO api_keys (user_id, api_key, created_at) VALUES (?, ?, ?)',
                                 (user_id, key, now_str()))
                session['user_id'] = user_id
                flash('注册成功，已自动生成 API Key', 'success')
                return redirect(url_for('dashboard'))
            except sqlite3.IntegrityError:
                flash('用户名或邮箱已被注册', 'error')
    return render_template('register.html', page_title='注册')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        with get_db() as conn:
            user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, username)).fetchone()
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            session['user_id'] = user['id']
            flash('登录成功', 'success')
            next_url = request.args.get('next')
            return redirect(next_url if next_url and next_url.startswith('/') else url_for('dashboard'))
        flash('用户名或密码错误', 'error')
    return render_template('login.html', page_title='登录')


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('已退出登录', 'success')
    return redirect(url_for('index'))
# ---------------------------------------------------------------- 控制台
@app.route('/dashboard')
@login_required
def dashboard():
    user = _current_user_row()
    with get_db() as conn:
        keys = conn.execute('SELECT * FROM api_keys WHERE user_id = ? ORDER BY id DESC', (user['id'],)).fetchall()
        today_count = conn.execute(
            'SELECT COUNT(*) AS c FROM call_logs WHERE user_id = ? AND created_at LIKE ?',
            (user['id'], today_str() + '%')).fetchone()['c']
        total_count = conn.execute('SELECT COUNT(*) AS c FROM call_logs WHERE user_id = ?', (user['id'],)).fetchone()['c']
        recent_logs = conn.execute(
            'SELECT * FROM call_logs WHERE user_id = ? ORDER BY id DESC LIMIT 20', (user['id'],)).fetchall()
    plan = user['plan']
    day_used = _day_counts.get((user['id'], today_str()), 0)
    min_used = _min_counts.get((user['id'], minute_str()), 0)
    return render_template('dashboard.html', page_title='控制台', user=user, keys=keys,
                           today_count=today_count, total_count=total_count, recent_logs=recent_logs,
                           day_used=day_used, min_used=min_used, plan=plan)


@app.route('/dashboard/generate_key', methods=['POST'])
@login_required
def generate_key():
    user = _current_user_row()
    key = gen_api_key()
    with get_db() as conn:
        conn.execute('INSERT INTO api_keys (user_id, api_key, created_at) VALUES (?, ?, ?)',
                     (user['id'], key, now_str()))
    flash('已生成新的 API Key', 'success')
    return redirect(url_for('dashboard'))


# ---------------------------------------------------------------- 套餐与订单
@app.route('/pricing')
def pricing():
    return render_template('pricing.html', page_title='套餐价格')


@app.route('/subscribe/<tier>')
@login_required
def subscribe(tier):
    if tier not in TIERS:
        abort(404)
    user = _current_user_row()
    token = hashlib.md5((str(user['id']) + tier + now_str()).encode('utf-8')).hexdigest()
    with get_db() as conn:
        pending = conn.execute(
            'SELECT * FROM orders WHERE user_id = ? AND tier = ? AND status = ?',
            (user['id'], tier, 'pending')).fetchone()
        if not pending:
            cur = conn.execute(
                'INSERT INTO orders (user_id, tier, amount, status, qr_token, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                (user['id'], tier, TIERS[tier]['price'], 'pending', token, now_str()))
            pending = conn.execute('SELECT * FROM orders WHERE id = ?', (cur.lastrowid,)).fetchone()
    render_qr_svg(pending['qr_token'])
    return render_template('subscribe.html', page_title='套餐订阅', tier=tier, order=pending)
@app.route('/qr/<token>')
@login_required
def qr_image(token):
    user = _current_user_row()
    with get_db() as conn:
        order = conn.execute('SELECT * FROM orders WHERE qr_token = ?', (token,)).fetchone()
    if not order or order['user_id'] != user['id']:
        abort(404)
    svg = render_qr_svg(token)
    return Response(svg, mimetype='image/svg+xml')


def qr_exists(token):
    return ('qr_' + token) in _qr_cache


def render_qr_svg(token):
    cache_key = 'qr_' + token
    if cache_key in _qr_cache:
        return _qr_cache[cache_key]
    size = 25
    random.seed(int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16))
    matrix = [[random.random() < 0.45 for _ in range(size)] for _ in range(size)]

    def draw_finder(r0, c0):
        for dr in range(7):
            for dc in range(7):
                edge = dr in (0, 6) or dc in (0, 6)
                core = 2 <= dr <= 4 and 2 <= dc <= 4
                matrix[r0 + dr][c0 + dc] = edge or core

    draw_finder(0, 0)
    draw_finder(0, size - 7)
    draw_finder(size - 7, 0)
    cell = 6
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" viewBox="0 0 {} {}" shape-rendering="crispEdges">'
             .format(size * cell, size * cell, size * cell, size * cell)]
    parts.append('<rect width="100%" height="100%" fill="#ffffff"/>')
    for r in range(size):
        for c in range(size):
            if matrix[r][c]:
                parts.append('<rect x="{}" y="{}" width="{}" height="{}" fill="#0a0e17"/>'
                             .format(c * cell, r * cell, cell, cell))
    parts.append('</svg>')
    svg = ''.join(parts)
    _qr_cache[cache_key] = svg
    return svg


@app.route('/activate/<tier>', methods=['POST'])
@login_required
def activate(tier):
    if tier not in TIERS:
        abort(404)
    user = _current_user_row()
    target_id = user['id']
    if user['is_admin']:
        try:
            target_id = int(request.form.get('uid') or user['id'])
        except ValueError:
            target_id = user['id']
    with get_db() as conn:
        order = conn.execute(
            'SELECT * FROM orders WHERE user_id = ? AND tier = ? AND status = ?',
            (target_id, tier, 'pending')).fetchone()
        if not order:
            flash('没有找到该套餐的待激活订单', 'error')
            return redirect(url_for('subscribe', tier=tier))
        expire = None
        if tier in ('pro', 'enterprise'):
            expire = (datetime.now(TZ) + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('UPDATE orders SET status = ?, paid_at = ? WHERE id = ?', ('paid', now_str(), order['id']))
        conn.execute('UPDATE users SET plan = ?, plan_expire = ? WHERE id = ?', (tier, expire, target_id))
    flash(TIERS[tier]['name'] + ' 已激活，限流配额已生效', 'success')
    return redirect(url_for('dashboard'))
# ---------------------------------------------------------------- 网页页面
@app.route('/')
def index():
    return render_template('index.html', page_title='首页')


@app.route('/docs')
def docs():
    return render_template('docs.html', page_title='API 文档')


@app.route('/openclaw')
def openclaw():
    return render_template('openclaw.html', page_title='OpenClaw 接入')


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html', page_title='页面不存在'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html', page_title='服务器错误'), 500


# ---------------------------------------------------------------- SEO 文件
@app.route('/robots.txt')
def robots_txt():
    text = 'User-agent: *\nAllow: /\n\nSitemap: ' + SITE_URL + '/sitemap.xml\n'
    return Response(text, mimetype='text/plain')


@app.route('/sitemap.xml')
def sitemap_xml():
    pages = ['/', '/pricing', '/docs', '/openclaw', '/register', '/login', '/dashboard',
             '/subscribe/free', '/subscribe/pro', '/subscribe/enterprise']
    items = []
    for p in pages:
        priority = '1.0' if p == '/' else '0.9'
        items.append('<url><loc>{0}{1}</loc><changefreq>daily</changefreq><priority>{2}</priority></url>'
                     .format(SITE_URL, p, priority))
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + \
          '\n'.join(items) + '\n</urlset>'
    return Response(xml, mimetype='application/xml')


@app.route('/indexnow_key.txt')
def indexnow_txt():
    return Response(get_indexnow_key(), mimetype='text/plain')


@app.route('/favicon.ico')
def favicon():
    try:
        with open(os.path.join(BASE_DIR, 'static', 'favicon.svg'), 'rb') as f:
            return Response(f.read(), mimetype='image/svg+xml')
    except OSError:
        abort(404)
# ---------------------------------------------------------------- OG 图片生成
def _write_png(path, width, height, pixel_fn):
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            r, g, b = pixel_fn(x, y)
            row += bytes((r, g, b))
        rows.append(bytes(row))
    raw = b''.join(rows)

    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        c += struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
        return c

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(png)


def ensure_og_image():
    path = os.path.join(BASE_DIR, 'static', 'og-cover.png')
    if os.path.exists(path):
        return

    def pixel(x, y):
        t = y / 630.0
        r = int(10 + 8 * t)
        g = int(14 + 12 * t)
        b = int(23 + 25 * t)
        if 470 <= y < 500 and 140 <= x < 1060:
            return 246, 196, 83
        if 510 <= y < 528 and 140 <= x < 1060:
            return 53, 208, 242
        return r, g, b

    _write_png(path, 1200, 630, pixel)


# ---------------------------------------------------------------- 启动
def main():
    parser = argparse.ArgumentParser(description='KLineAPI v3.0 行情 API 服务')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='监听端口，默认 ' + str(DEFAULT_PORT))
    parser.add_argument('--host', default='0.0.0.0', help='监听地址，默认 0.0.0.0')
    parser.add_argument('--debug', action='store_true', help='开启调试模式')
    args = parser.parse_args()
    print('KLineAPI v3.0 启动成功: http://' + args.host + ':' + str(args.port))
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


# 模块级初始化 (waitress/生产环境也需要)
init_db()
_bootstrap_admin()


if __name__ == '__main__':
    main()
