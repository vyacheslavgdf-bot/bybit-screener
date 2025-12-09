import os
import logging
import time
from telegram.bot import Bot
import schedule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    logger.error("❌ Задайте TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID в Render")
    exit(1)

bot = Bot(token=TOKEN)

def test_send():
    bot.send_message(chat_id=CHAT_ID, text="✅ Бот работает!")
    logger.info("Сообщение отправлено")

if __name__ == "__main__":
    test_send()
    schedule.every(30).minutes.do(test_send)
    while True:
        schedule.run_pending()
        time.sleep(60)