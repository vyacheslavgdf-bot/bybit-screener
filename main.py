import os
import logging
import time
import requests
import pandas as pd
from telegram.bot import Bot
import schedule

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получаем переменные окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Проверка наличия токена и ID
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    logger.error("❌ Обязательные переменные: TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID")
    exit(1)

# Инициализация бота (синхронная, v13.15)
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Список пар для сканирования
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

def fetch_price(symbol, exchange):
    """Получает последнюю цену с биржи (Bybit или Binance)"""
    try:
        if exchange == "bybit":
            url = "https://api.bybit.com/v5/market/kline"
            params = {"category": "linear", "symbol": symbol, "interval": "15", "limit": 1}
        else:  # binance
            url = "https://fapi.binance.com/fapi/v1/klines"
            params = {"symbol": symbol, "interval": "15m", "limit": 1}
        
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
        logger.error(f"Ошибка {symbol} на {exchange}: {e}")
        return None

def send_update():
    """Отправляет текущие цены в Telegram"""
    messages = []
    for symbol in SYMBOLS:
        for ex in ["bybit", "binance"]:
            price = fetch_price(symbol, ex)
            if price is not None:
                messages.append(f"{symbol} ({ex.upper()}): ${price:.2f}")
    
    if messages:
        text = "📊 Текущие цены:\n" + "\n".join(messages)
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
        logger.info("✅ Сообщение отправлено в Telegram")
    else:
        logger.warning("⚠️ Не удалось получить данные с бирж")

# Основной запуск
if __name__ == "__main__":
    send_update()  # Отправить сразу при старте
    schedule.every(15).minutes.do(send_update)  # Затем каждые 15 минут
    
    while True:
        schedule.run_pending()
        time.sleep(30)
