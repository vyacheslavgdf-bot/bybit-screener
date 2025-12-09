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

def get_binance_symbols():
    try:
        url = "https://api.binance.com/api/v3/exchangeInfo"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            logger.error(f"Binance exchangeInfo: HTTP {response.status_code}")
            return []
        data = response.json()
        symbols = []
        for item in data['symbols']:
            if item['status'] == 'TRADING' and item['quoteAsset'] == 'USDT':
                symbols.append(item['symbol'])
        return symbols
    except Exception as e:
        logger.error(f"Ошибка получения списка Binance: {e}")
        return []

def get_klines_binance(symbol, interval='1h', limit=100):
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {'symbol': symbol, 'interval': interval, 'limit': limit}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            logger.error(f"Binance klines {symbol}: HTTP {response.status_code}")
            return [], []
        data = response.json()
        closes, volumes = [], []
        for kline in data:
            closes.append(float(kline[4]))      # close
            volumes.append(float(kline[5]))     # volume
        return closes, volumes
    except Exception as e:
        logger.error(f"Ошибка получения свечей Binance {symbol}: {e}")
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
    closes, volumes = get_klines_binance(symbol, '1h', 100)
    if len(closes) < 30:
        return False
    # Рост за 6 часов = 6 свечей на 1h
    if len(closes) < 7:
        return False
    price_change_6h = (closes[-1] - closes[-7]) / closes[-7] * 100
    if price_change_6h < 25:
        return False
    # Объём за 24ч = 24 свечи
    if len(volumes) < 25:
        return False
    avg_vol_24h = sum(volumes[-24:]) / 24
    if avg_vol_24h == 0:
        return False
    vol_change_pct = (volumes[-1] - avg_vol_24h) / avg_vol_24h * 100
    if vol_change_pct < 300:
        return False
    # RSI
    rsi = calculate_rsi(closes, 14)
    if not rsi or not (50 <= rsi <= 70):
        return False
    # MA
    ma5 = calculate_ma(closes, 5)
    ma10 = calculate_ma(closes, 10)
    if not ma5 or not ma10 or ma5 <= ma10:
        return False
    price = closes[-1]
    if not (ma10 * 0.99 <= price <= ma10 * 1.01):
        return False
    message = (
        f"🟢 ПОТЕНЦИАЛЬНЫЙ LONG-СИГНАЛ (Binance)!\n\n"
        f"Монета: {symbol}\n"
        f"Рост за 6ч: +{price_change_6h:.1f}%\n"
        f"Объём: +{vol_change_pct:.0f}%\n"
        f"RSI(14): {rsi:.1f}\n"
        f"Цена у MA10, MA5 > MA10\n\n"
        f"👉 Проверь график на 15m в Binance!"
    )
    send_telegram_message(message)
    return True

def analyze_short_signal(symbol):
    closes, volumes = get_klines_binance(symbol, '1h', 50)
    if len(closes) < 25:
        return False
    if len(closes) < 7:
        return False
    price_change_6h = (closes[-1] - closes[-7]) / closes[-7] * 100
    if price_change_6h < 25:
        return False
    if len(volumes) < 25:
        return False
    avg_vol_24h = sum(volumes[-24:]) / 24
    if avg_vol_24h == 0:
        return False
    vol_change_pct = (volumes[-1] - avg_vol_24h) / avg_vol_24h * 100
    if vol_change_pct < 300:
        return False
    rsi = calculate_rsi(closes, 14)
    if not rsi or rsi < 70:
        return False
    ma5 = calculate_ma(closes, 5)
    ma10 = calculate_ma(closes, 10)
    if not ma5 or not ma10 or ma5 > ma10:
        return False
    message = (
        f"🚨 ПОТЕНЦИАЛЬНЫЙ SHORT-СИГНАЛ (Binance)!\n\n"
        f"Монета: {symbol}\n"
        f"Рост за 6ч: +{price_change_6h:.1f}%\n"
        f"Объём: +{vol_change_pct:.0f}%\n"
        f"RSI(14): {rsi:.1f}\n"
        f"MA: MA5 < MA10 (разворот)\n\n"
        f"👉 Проверь график на 15m в Binance!"
    )
    send_telegram_message(message)
    return True

def main():
    logger.info("🔍 Сканирование Binance (LONG + SHORT)...")
    symbols = get_binance_symbols()
    # Ограничиваем до топ-100 монет по объёму (опционально можно отсортировать)
    symbols = [s for s in symbols if 'USDT' in s][:100]
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
            logger.error(f"Критическая ошибка: {e}")
        time.sleep(900)  # 15 минут
