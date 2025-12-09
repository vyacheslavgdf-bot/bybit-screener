import os
import logging
import time
import requests
import pandas as pd
from telegram.ext import Updater
import schedule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    logger.error("❌ TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID обязательны")
    exit(1)

updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
bot = updater.bot

SYMBOLS = ["BTCUSDT", "ETHUSDT"]

def get_price(symbol, exchange):
    try:
        if exchange == "bybit":
            url = "https://api.bybit.com/v5/market/kline"
            params = {"category": "linear", "symbol": symbol, "interval": "15", "limit": 30}
        else:
            url = "https://fapi.binance.com/fapi/v1/klines"
            params = {"symbol": symbol, "interval": "15m", "limit": 30}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return None
        data = response.json()
        if exchange == "bybit":
            if data.get("retCode") != 0:
                return None
            return float(data["result"]["list"][0][4])
        else:
            return float(data[0][4])
    except Exception as e:
        logger.error(f"Ошибка {symbol} {exchange}: {e}")
        return None

def send_signals():
    messages = []
    for symbol in SYMBOLS:
        for ex in ["bybit", "binance"]:
            price = get_price(symbol, ex)
            if price is not None:
                messages.append(f"{symbol} ({ex}): {price:.2f}")
    if messages:
        text = "📊 Цены:\n" + "\n".join(messages)
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
        logger.info("✅ Успешно отправлено")
    else:
        logger.warning("⚠️ Нет данных для отправки")

if __name__ == "__main__":
    send_signals()
    schedule.every(15).minutes.do(send_signals)
    while True:
        schedule.run_pending()
        time.sleep(30)
