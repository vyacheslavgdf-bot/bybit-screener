import os
import logging
import time
import requests
import pandas as pd
from telegram import Bot
import schedule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    logger.error("❌ TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID обязательны")
    exit(1)

bot = Bot(token=TOKEN)
SYMBOLS = ["BTCUSDT", "ETHUSDT"]

def get_price(symbol, ex):
    try:
        url = "https://api.bybit.com/v5/market/kline" if ex == "bybit" else "https://fapi.binance.com/fapi/v1/klines"
        p = {"category":"linear","symbol":symbol,"interval":"15","limit":30} if ex == "bybit" else {"symbol":symbol,"interval":"15m","limit":30}
        r = requests.get(url, params=p, timeout=10)
        if r.status_code != 200:
            return None
        d = r.json()
        if ex == "bybit":
            if d.get("retCode") != 0: return None
            return float(d["result"]["list"][0][4])
        else:
            return float(d[0][4])
    except:
        return None

def send_signals():
    msg = []
    for s in SYMBOLS:
        for ex in ["bybit", "binance"]:
            price = get_price(s, ex)
            if price:
                msg.append(f"{s} ({ex}): {price}")
    if msg:
        text = "Цены:\n" + "\n".join(msg)
        bot.send_message(chat_id=CHAT_ID, text=text)
        logger.info("✅ Отправлены цены")
    else:
        logger.warning("⚠️ Нет данных")

if __name__ == "__main__":
    send_signals()
    schedule.every(15).minutes.do(send_signals)
    while True:
        schedule.run_pending()
        time.sleep(30)