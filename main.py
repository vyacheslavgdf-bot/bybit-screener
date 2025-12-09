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
    logger.error("❌ Обязательно задайте TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID в Render")
    exit(1)

bot = Bot(token=TOKEN)

def send_test():
    try:
        bot.send_message(chat_id=CHAT_ID, text="✅ Бот успешно запущен на Render!")
        logger.info("Сообщение отправлено")
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")

if __name__ == "__main__":
    send_test()
    schedule.every(30).minutes.do(send_test)
    while True:
        schedule.run_pending()
        time.sleep(60)
