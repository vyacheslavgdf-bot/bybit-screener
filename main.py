import os
import logging
import time
import requests
import numpy as np
import pandas as pd
from telegram import Bot
from telegram.error import TelegramError
import schedule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    logger.error("❌ Не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID")
    exit(1)

bot = Bot(token=TELEGRAM_BOT_TOKEN)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
LIMIT = 50

def fetch_klines(symbol, exchange):
    try:
        if exchange == "bybit":
            url = "https://api.bybit.com/v5/market/kline"
            params = {"category": "linear", "symbol": symbol, "interval": "15", "limit": LIMIT}
        else:
            url = "https://fapi.binance.com/fapi/v1/klines"
            params = {"symbol": symbol, "interval": "15m", "limit": LIMIT}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return None
        data = response.json()
        if exchange == "bybit":
            if data.get("retCode") != 0:
                return None
            klines = data["result"]["list"]
            df = pd.DataFrame(klines, columns=["time","open","high","low","close","volume","turnover"])
        else:
            df = pd.DataFrame(data, columns=["open_time","open","high","low","close","volume",
                                            "close_time","qav","trades","taker_base","taker_quote","ignore"])
        df["close"] = pd.to_numeric(df["close"])
        df["high"] = pd.to_numeric(df["high"])
        df["low"] = pd.to_numeric(df["low"])
        df["volume"] = pd.to_numeric(df["volume"])
        return df
    except:
        return None

def scan():
    longs, shorts = [], []
    for symbol in SYMBOLS:
        for ex in ["bybit", "binance"]:
            df = fetch_klines(symbol, ex)
            if df is None or len(df) < 20:
                continue
            close = df["close"].values
            ma5 = pd.Series(close).rolling(5).mean().iloc[-1]
            ma10 = pd.Series(close).rolling(10).mean().iloc[-1]
            ma20 = pd.Series(close).rolling(20).mean().iloc[-1]
            price = df["close"].iloc[-2]
            if price > ma5 and price > ma10 and price > ma20:
                longs.append(f"✅ {symbol} ({ex})")
            elif price < ma5 and price < ma10 and price < ma20:
                shorts.append(f"🔻 {symbol} ({ex})")
    return longs, shorts

def send():
    try:
        logger.info("🔍 Сканирование...")
        longs, shorts = scan()
        msg = "✅ LONG:\n" + "\n".join(longs) if longs else ""
        msg += "\n🔻 SHORT:\n" + "\n".join(shorts) if shorts else ""
        if not longs and not shorts:
            msg = "🔍 Нет сигналов."
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        logger.info(f"✅ Отправлено: {len(longs)} LONG, {len(shorts)} SHORT")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    send()
    schedule.every(15).minutes.do(send)
    while True:
        schedule.run_pending()
        time.sleep(30)
