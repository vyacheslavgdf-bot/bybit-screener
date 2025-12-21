# main.py
import os
import time
import schedule
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def send_telegram_message(bot_token, chat_id, text: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("✅ Сообщение отправлено")
        else:
            print(f"❌ Ошибка Telegram: {resp.json()}")
    except Exception as e:
        print(f"❌ Исключение при отправке: {e}")

def main():
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    YOUR_TELEGRAM_ID = os.getenv("YOUR_TELEGRAM_ID")

    if not TELEGRAM_BOT_TOKEN or not YOUR_TELEGRAM_ID:
        raise RuntimeError("❌ TELEGRAM_BOT_TOKEN или YOUR_TELEGRAM_ID не заданы!")

    print("🚀 Запуск Daily Signal Bot...")
    send_telegram_message(TELEGRAM_BOT_TOKEN, YOUR_TELEGRAM_ID, "✅ Daily Signal Bot запущен! Сканирование ежедневно в 00:05 UTC.")

    def get_bybit_symbols():
        url = "https://api.bybit.com/v5/market/tickers"
        params = {"category": "linear"}
        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if data["retCode"] == 0:
                symbols = [item["symbol"] for item in data["result"]["list"] if item["symbol"].endswith("USDT")]
                return symbols
            else:
                return ["BTCUSDT", "ETHUSDT"]
        except:
            return ["BTCUSDT", "ETHUSDT"]

    def get_daily_klines(symbol: str, limit: int = 5):
        url = "https://api.bybit.com/v5/market/kline"
        params = {"category": "linear", "symbol": symbol, "interval": "D", "limit": limit}
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

    def analyze_daily_signal(df: pd.DataFrame):
        if df is None or len(df) < 3:
            return None, None
        yesterday_close = df.iloc[-1]["close"]
        day_before_close = df.iloc[-2]["close"]
        if yesterday_close > day_before_close:
            return "LONG", yesterday_close
        elif yesterday_close < day_before_close:
            return "SHORT", yesterday_close
        else:
            return None, None

    def scan_daily_signals():
        symbols = get_bybit_symbols()
        print(f"📅 Сканируем {len(symbols)} пар на D1...")
        signals_found = False
        for symbol in symbols[:20]:
            df = get_daily_klines(symbol, limit=5)
            if df is None:
                continue
            signal, price = analyze_daily_signal(df)
            if signal:
                last_ts = df.iloc[-1]["timestamp"]
                now_utc = datetime.now(timezone.utc)
                if (now_utc.date() - last_ts.date()).days == 1:
                    msg = f"📊 Daily Signal ({last_ts.strftime('%Y-%m-%d')})\nПара: {symbol}\nНаправление: {signal}\nЦена закрытия: {price:.4f}"
                    send_telegram_message(TELEGRAM_BOT_TOKEN, YOUR_TELEGRAM_ID, msg)
                    signals_found = True
        if not signals_found:
            print("ℹ️ Нет новых сигналов сегодня.")

    schedule.every().day.at("00:05").do(scan_daily_signals)

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
