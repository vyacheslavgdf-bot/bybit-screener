# main.py
import os
import time
import schedule
import requests
import pandas as pd
import numpy as np

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUR_TELEGRAM_ID = os.getenv("YOUR_TELEGRAM_ID")

if not TELEGRAM_BOT_TOKEN or not YOUR_TELEGRAM_ID:
    raise RuntimeError("❌ Не заданы TELEGRAM_BOT_TOKEN или YOUR_TELEGRAM_ID в Render!")

def send_telegram_message(text: str):
    """Отправка сообщения напрямую через Telegram Bot API."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": YOUR_TELEGRAM_ID, "text": text}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("✅ Сообщение отправлено")
        else:
            print(f"❌ Ошибка Telegram: {resp.json()}")
    except Exception as e:
        print(f"❌ Исключение при отправке: {e}")

# === Bybit + сигналы (без изменений) ===
def get_bybit_klines(symbol: str, interval: str = "15", limit: int = 100):
    url = "https://api.bybit.com/v5/market/kline"
    params = {"category": "linear", "symbol": symbol, "interval": interval, "limit": limit}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data["retCode"] != 0:
            return None
        df = pd.DataFrame(data["result"]["list"], columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
        df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit='ms')
        return df.sort_values("timestamp").reset_index(drop=True)
    except:
        return None

def calculate_indicators(df):
    df["ma5"] = df["close"].rolling(5).mean()
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))
    exp12 = df["close"].ewm(span=12).mean()
    exp26 = df["close"].ewm(span=26).mean()
    df["macd"] = exp12 - exp26
    df["macd_signal"] = df["macd"].ewm(span=9).mean()
    return df

def scan_signals():
    for symbol in ["BTCUSDT", "ETHUSDT"]:
        df = get_bybit_klines(symbol, "15", 100)
        if df is None or len(df) < 25:
            continue
        df = calculate_indicators(df)
        last, prev = df.iloc[-1], df.iloc[-2]
        if time.time() * 1000 - last["timestamp"].timestamp() * 1000 < 15 * 60 * 1000:
            continue
        if (last["ma5"] > last["ma10"] > last["ma20"] and
            50 < last["rsi"] < 70 and
            last["macd"] > last["macd_signal"] and prev["macd"] <= prev["macd_signal"] and
            last["volume"] > df["volume"].rolling(20).mean().iloc[-1] * 1.5 and
            last["close"] > last["open"]):
            msg = f"🟢 LONG\nПара: {symbol}\nЦена: {last['close']:.2f}"
            send_telegram_message(msg)
    print("🔍 Сканирование завершено.")

# === Запуск ===
if __name__ == "__main__":
    print("🚀 Запуск (чистый requests, без telegram-библиотеки)")
    send_telegram_message("✅ Бот активен! Сканирование каждые 2 мин.")
    schedule.every(2).minutes.do(scan_signals)
    scan_signals()
    while True:
        schedule.run_pending()
        time.sleep(10)
