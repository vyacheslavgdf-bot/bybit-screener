import os
import logging
import time
import requests
import numpy as np
import pandas as pd
from telegram import Bot
from telegram.error import TelegramError
import schedule

# === Настройка логирования ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# === Конфигурация ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    logger.error("❌ Не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID")
    exit(1)

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# === Фиксированный список популярных пар ===
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "AVAXUSDT", "MATICUSDT", "LINKUSDT", "UNIUSDT",
    "LTCUSDT", "BCHUSDT", "ATOMUSDT", "NEARUSDT", "APTUSDT"
]

LIMIT = 100

# === Вспомогательные функции ===
def fetch_klines(symbol, exchange):
    try:
        if exchange == "bybit":
            url = f"https://api.bybit.com/v5/market/kline"
            params = {"category": "linear", "symbol": symbol, "interval": "15", "limit": LIMIT}
        elif exchange == "binance":
            url = f"https://fapi.binance.com/fapi/v1/klines"
            params = {"symbol": symbol, "interval": "15m", "limit": LIMIT}
        else:
            return None

        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            logger.error(f"{exchange.upper()} {symbol}: HTTP {response.status_code}")
            return None

        data = response.json()
        if exchange == "bybit":
            if data.get("retCode") != 0:
                return None
            klines = data["result"]["list"]
            df = pd.DataFrame(klines, columns=["time", "open", "high", "low", "close", "volume", "turnover"])
        else:  # binance
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "qav", "trades", "taker_base", "taker_quote", "ignore"
            ])
        df["close"] = pd.to_numeric(df["close"])
        df["high"] = pd.to_numeric(df["high"])
        df["low"] = pd.to_numeric(df["low"])
        df["volume"] = pd.to_numeric(df["volume"])
        return df

    except Exception as e:
        logger.error(f"Ошибка получения
