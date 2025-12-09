import requests
import time
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
YOUR_TELEGRAM_ID = os.getenv('YOUR_TELEGRAM_ID')

if not TELEGRAM_BOT_TOKEN or not YOUR_TELEGRAM_ID:
    logger.error("Не заданы TELEGRAM_BOT_TOKEN или YOUR_TELEGRAM_ID")
    exit(1)

# Улучшенные заголовки для обхода защиты Bybit (включая HTTP 403)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.bybit.com/',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Origin': 'https://www.bybit.com',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'Connection': 'keep-alive'
}

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': YOUR_TELEGRAM_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code != 200:
            logger.error(f"Telegram API ошибка: {response.status_code} – {response.text}")
    except Exception as e:
        logger.error(f"Ошибка отправки в Telegram: {e}")

def get_bybit_symbols():
    try:
        url = "https://api.bybit.com/v5/market/instruments-info"
        params = {'category': 'linear'}
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            logger.error(f"Bybit instruments: HTTP {response.status_code}")
            return []
        data = response.json()
        if data.get('retCode') != 0:
            logger.error(f"Bybit ошибка: {data.get('retMsg')}")
            return []
        return [
            item['symbol'] for item in data['result']['list']
            if item['status'] == 'Trading' and item['symbol'].endswith('USDT')
        ]
    except Exception as e:
        logger.error(f"Ошибка получения списка инструментов: {e}")
        return []

def get_klines_bybit(symbol, interval='60', limit=100):
    try:
        url = "https://api.bybit.com/v5/market/kline"
        params = {'category': 'linear', 'symbol': symbol, 'interval': interval, 'limit': limit}
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            logger.error(f"Bybit kline {symbol}: HTTP {response.status_code}")
            return [], []
        data = response.json()
        if data.get('retCode') != 0:
            logger.error(f"Bybit kline ошибка для {symbol}: {data.get('retMsg')}")
            return [], []
        closes, volumes = [], []
        for kline in data['result']['list']:
            closes.append(float(kline[4]))
            volumes.append(float(kline[5]))
        closes.reverse()
        volumes.reverse()
        return closes, volumes
    except Exception as e:
        logger.error(f"Ошибка получения свечей {symbol}: {e}")
        return [], []

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(diff if diff > 0 else 0)
        losses.append(abs(diff) if diff < 0 else 0)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_ma(prices, window):
    if len(prices) < window:
        return None
    return sum(prices[-window:]) / window

def analyze_long_signal(symbol):
    closes, volumes = get_klines_bybit(symbol, '60', 100)
    if len(closes) < 30:
        return False
    price_change_6h = (closes[-1] - closes[-7]) / closes[-7] * 100
    if price_change_6h < 25:
        return False
    avg_vol_24h = sum(volumes[-24:]) / 24
    if avg_vol_24h == 0:
        return False
    vol_change_pct = (volumes[-1] - avg_vol_24h) / avg_vol_24h * 100
    if vol_change_pct < 300:
        return False
    rsi = calculate_rsi(closes, 14)
    if not rsi or not (50 <= rsi <= 70):
        return False
    ma5 = calculate_ma(closes, 5)
    ma10 = calculate_ma(closes, 10)
    if not ma5 or not ma10 or ma5 <= ma10:
        return False
    price = closes[-1]
    if not (ma10 * 0.99 <= price <= ma10 * 1.01):
        return False
    message = (
        f"🟢 ПОТЕНЦИАЛЬНЫЙ LONG-СИГНАЛ (Bybit)!\n\n"
        f"Монета: {symbol}\n"
        f"Рост за 6ч: +{price_change_6h:.1f}%\n"
        f"Объём: +{vol_change_pct:.0f}%\n"
        f"RSI(14): {rsi:.1f}\n"
        f"Цена у MA10, MA5 > MA10\n\n"
        f"👉 Проверь график на 15m в Bybit!"
    )
    send_telegram_message(message)
    return True

def analyze_short_signal(symbol):
    closes, volumes = get_klines_bybit(symbol, '60', 50)
    if len(closes) < 25:
        return False
    price_change_6h = (closes[-1] - closes[-7]) / closes[-7] * 100
    if price_change_6h < 25:
        return False
    avg_volume_24h = sum(volumes[-24:]) / 24
    if avg_volume_24h == 0:
        return False
    volume_change_pct = (volumes[-1] - avg_volume_24h) / avg_volume_24h * 100
    if volume_change_pct < 300:
        return False
    rsi = calculate_rsi(closes, 14)
    if not rsi or rsi < 70:
        return False
    ma5 = calculate_ma(closes, 5)
    ma10 = calculate_ma(closes, 10)
    if not ma5 or not ma10 or ma5 > ma10:
        return False
    message = (
        f"🚨 ПОТЕНЦИАЛЬНЫЙ SHORT-СИГНАЛ (Bybit)!\n\n"
        f"Монета: {symbol}\n"
        f"Рост за 6ч: +{price_change_6h:.1f}%\n"
        f"Объём: +{volume_change_pct:.0f}%\n"
        f"RSI(14): {rsi:.1f}\n"
        f"MA: MA5 < MA10 (разворот)\n\n"
        f"👉 Проверь график на 15m в Bybit!"
    )
    send_telegram_message(message)
    return True

def main():
    logger.info("🔍 Сканирование Bybit (LONG + SHORT)...")
    symbols = get_bybit_symbols()[:100]
    if not symbols:
        logger.warning("Не удалось получить список монет — пропуск цикла")
        return
    long_count = 0
    short_count = 0
    for symbol in symbols:
        try:
            if analyze_long_signal(symbol):
                long_count += 1
            if analyze_short_signal(symbol):
                short_count += 1
        except Exception as e:
            logger.error(f"Ошибка анализа {symbol}: {e}")
            continue
    logger.info(f"✅ Найдено: {long_count} LONG, {short_count} SHORT")

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            logger.error(f"Критическая ошибка в основном цикле: {e}")
        time.sleep(900)
