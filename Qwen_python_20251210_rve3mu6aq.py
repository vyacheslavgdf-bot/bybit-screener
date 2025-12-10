import os
import time
import schedule
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUR_TELEGRAM_ID = os.getenv("YOUR_TELEGRAM_ID")

if not TELEGRAM_BOT_TOKEN or not YOUR_TELEGRAM_ID:
    raise RuntimeError("❌ Не заданы TELEGRAM_BOT_TOKEN или YOUR_TELEGRAM_ID в Render!")

def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": YOUR_TELEGRAM_ID, "text": text}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("✅ Сообщение отправлено")
        else:
            print(f"❌ Ошибка Telegram: {resp.json()}")
    except Exception as e:
        print(f"❌ Исключение: {e}")

def get_bybit_symbols():
    url = "https://api.bybit.com/v5/market/tickers"
    params = {"category": "linear"}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data["retCode"] == 0:
            symbols = [item["symbol"] for item in data["result"]["list"] if item["symbol"].endswith("USDT")]
            return sorted(symbols)
        else:
            return ["BTCUSDT", "ETHUSDT"]
    except:
        return ["BTCUSDT", "ETHUSDT"]

def get_klines(symbol: str, interval: str, limit: int = 100):
    url = "https://api.bybit.com/v5/market/kline"
    params = {"category": "linear", "symbol": symbol, "interval": interval, "limit": limit}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data["retCode"] == 0:
            df = pd.DataFrame(
                data["result"]["list"],
                columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"]
            )
            df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
            df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit='ms')
            df = df.sort_values("timestamp").reset_index(drop=True)
            return df
        else:
            return None
    except:
        return None

def calculate_indicators(df: pd.DataFrame):
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
    df["bb_middle"] = df["close"].rolling(20).mean()
    bb_std = df["close"].rolling(20).std()
    df["bb_upper"] = df["bb_middle"] + (bb_atd * 2)
    df["bb_lower"] = df["bb_middle"] - (bb_std * 2)
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]
    return df

def is_trading_hours(timestamp: pd.Timestamp) -> bool:
    return 7 <= timestamp.hour <= 22

def analyze_timeframe(df: pd.DataFrame, direction: str = "LONG"):
    if df is None or len(df) < 25:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    if not is_trading_hours(last["timestamp"]):
        return False
    if last["bb_width"] < 0.005:
        return False
    if direction == "LONG":
        return (last["ma5"] > last["ma10"] > last["ma20"] and
                50 < last["rsi"] < 70 and
                last["macd"] > last["macd_signal"] and prev["macd"] <= prev["macd_signal"] and
                last["volume"] > df["volume"].rolling(20).mean().iloc[-1] * 1.5 and
                last["close"] > last["open"])
    elif direction == "SHORT":
        return (last["ma5"] < last["ma10"] < last["ma20"] and
                30 < last["rsi"] < 50 and
                last["macd"] < last["macd_signal"] and prev["macd"] >= prev["macd_signal"] and
                last["volume"] > df["volume"].rolling(20).mean().iloc[-1] * 1.5 and
                last["close"] < last["open"])
    return False

def scan_signals():
    symbols = get_bybit_symbols()
    print(f"🔍 Сканируем {len(symbols)} пар...")
    for symbol in symbols[:50]:
        df_h1 = get_klines(symbol, "60", 100)
        if df_h1 is None:
            continue
        df_h1 = calculate_indicators(df_h1)
        long_candidate = analyze_timeframe(df_h1, "LONG")
        short_candidate = analyze_timeframe(df_h1, "SHORT")
        if not (long_candidate or short_candidate):
            continue
        df_m15 = get_klines(symbol, "15", 100)
        if df_m15 is None:
            continue
        df_m15 = calculate_indicators(df_m15)
        confirmed_long = long_candidate and analyze_timeframe(df_m15, "LONG")
        confirmed_short = short_candidate and analyze_timeframe(df_m15, "SHORT")
        if confirmed_long:
            msg = f"🟢 LONG\nПара: {symbol}\nЦена: {df_m15.iloc[-1]['close']:.4f}"
            send_telegram_message(msg)
        if confirmed_short:
            msg = f"🔴 SHORT\nПара: {symbol}\nЦена: {df_m15.iloc[-1]['close']:.4f}"
            send_telegram_message(msg)
    print("✅ Сканирование завершено.")

if __name__ == "__main__":
    send_telegram_message("✅ Бот запущен! Сканирование каждые 5 минут.")
    schedule.every(5).minutes.do(scan_signals)
    scan_signals()
    while True:
        schedule.run_pending()
        time.sleep(30)