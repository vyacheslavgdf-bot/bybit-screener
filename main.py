import os
import json
import requests
import numpy as np
from flask import Flask
from datetime import datetime, timezone

# === НАСТРОЙКИ ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUR_TELEGRAM_ID = os.getenv("YOUR_TELEGRAM_ID")

if not TELEGRAM_BOT_TOKEN or not YOUR_TELEGRAM_ID:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN или YOUR_TELEGRAM_ID не заданы")

try:
    YOUR_TELEGRAM_ID = int(YOUR_TELEGRAM_ID)
except ValueError:
    raise ValueError("YOUR_TELEGRAM_ID должен быть числом")

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def send_telegram(message):
    try:
        payload = {"chat_id": YOUR_TELEGRAM_ID, "text": message, "parse_mode": "HTML"}
        response = requests.post(TELEGRAM_URL, json=payload, timeout=10)
        if not response.ok:
            print(f"❌ Telegram API error: {response.text}")
        return response
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return None

def get_top_symbols(limit=20):
    try:
        url = "https://api.bybit.com/v5/market/tickers?category=linear"
        response = requests.get(url, timeout=10)
        send_telegram(f"📡 Ответ Bybit API (первые 100 символов):\n{response.text[:100]}")
        
        if not response.text.strip():
            send_telegram("❌ Bybit API вернул пустой ответ.")
            return []
        if "<html" in response.text.lower():
            send_telegram("❌ Bybit API вернул HTML (возможно, капча или rate limit).")
            return []

        data = response.json()
        if data.get("retCode") != 0:
            send_telegram(f"❌ Ошибка Bybit API: {data.get('retMsg')}")
            return []

        symbols = []
        for item in data["result"]["list"]:
            if "USDT" in item["symbol"] and "USDC" not in item["symbol"]:
                try:
                    vol = float(item["turnover24h"])
                    symbols.append((item["symbol"], vol))
                except (ValueError, KeyError):
                    continue

        symbols.sort(key=lambda x: x[1], reverse=True)
        top_symbols = [s[0] for s in symbols[:limit]]
        send_telegram(f"✅ Найдено {len(top_symbols)} монет: {top_symbols[:3]}")
        return top_symbols

    except json.JSONDecodeError as e:
        send_telegram(f"❌ Ошибка JSON: {str(e)}\nОтвет: {response.text[:100]}")
        return []
    except Exception as e:
        send_telegram(f"❌ Исключение: {str(e)}")
        return []

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_klines(symbol, interval="60", limit=30):
    try:
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={interval}&limit={limit}"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("retCode") != 0:
            return []
        closes = [float(c[4]) for c in data["result"]["list"]]
        return closes[::-1]
    except Exception as e:
        print(f"❌ Ошибка получения свечей для {symbol}: {e}")
        return []

def scan_market():
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    send_telegram(f"🕗 <b>Запуск сканирования</b>\nВремя: {now_utc}")
    
    symbols = get_top_symbols(limit=10)
    send_telegram(f"Анализирую {len(symbols)} монет...")
    
    for symbol in symbols[:3]:
        closes = get_klines(symbol)
        if closes and len(closes) > 15:
            rsi = calculate_rsi(closes)
            current_price = closes[-1]
            send_telegram(f"🔍 {symbol}\nЦена: {current_price:.6f}\nRSI: {rsi:.1f}")
            # Небольшая задержка для соблюдения лимитов API
            import time
            time.sleep(0.5)

    send_telegram("✅ Сканирование завершено.")

# === Flask App ===
app = Flask(__name__)

@app.route('/')
def trigger():
    scan_market()
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
