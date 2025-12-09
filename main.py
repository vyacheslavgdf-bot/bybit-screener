import requests
import time
import logging
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
YOUR_TELEGRAM_ID = os.getenv('YOUR_TELEGRAM_ID')

if not TELEGRAM_BOT_TOKEN or not YOUR_TELEGRAM_ID:
    logger.error("Не заданы TELEGRAM_BOT_TOKEN или YOUR_TELEGRAM_ID")
    exit(1)

# Заголовки для обхода защиты Bybit
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Referer': 'https://www.bybit.com/'
}

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': YOUR_TELEGRAM_ID, 'text': text, 'parse_mode': 'HTML'}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        logger.error(f"Ошибка Telegram: {e}")

def get_bybit_symbols():
    try:
        url = "https://api.bybit.com/v5/market/instruments-info"
        params = {'category': 'linear'}
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = response.json()
        return [item['symbol'] for item in data['result']['list'] 
                if item['status'] == 'Trading' and item['symbol'].endswith('USDT')]
    except Exception as e:
        logger.error(f"Ошибка Bybit (инструменты): {e} | Ответ: {response.text[:200]}")
        return []

def get_klines_bybit(symbol, interval='60', limit=100):
    try:
        url = "https://api.bybit.com/v5/market/kline"
        params = {'category': 'linear', 'symbol': symbol, 'interval': interval, 'limit': limit}
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = response.json()
        if data['retCode'] != 0:
            return [], []
        closes, volumes = [], []
        for kline in data['result']['list']:
            closes.append(float(kline[4]))
            volumes.append(float(kline[5]))
        closes.reverse()
        volumes.reverse()
        return closes, volumes
    except Exception as e:
        logger.error(f"Ошибка Bybit (свечи {symbol}): {e} | Ответ: {response.text[:200]}")
        return [], []

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    def calculate_macd(prices, fast=12, slow=26, signal=9):
    ema_fast = []
    ema_slow = []
    for i in range(len(prices)):  # ← Убедись, что тут есть `len(prices)` и `:`
        if i + 1 >= fast:
            ema_fast.append(sum(prices[i - fast + 1:i + 1]) / fast)
