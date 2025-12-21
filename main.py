# main.py
import os
import time
import threading
import requests
from flask import Flask

app = Flask(__name__)

def fetch_tickers():
    url = "https://api.bybit.com/v5/market/tickers?category=linear"
    while True:
        try:
            response = requests.get(url)
            data = response.json()
            print("🔍 Сканируем пары...")
            # Здесь можно добавить логику анализа или отправки сигналов
        except Exception as e:
            print(f"Ошибка: {e}")
        time.sleep(60)

# Запускаем фоновый поток ПРИ ИМПОРТЕ модуля
fetcher_thread = None

def start_background_tasks():
    global fetcher_thread
    if fetcher_thread is None:
        fetcher_thread = threading.Thread(target=fetch_tickers, daemon=True)
        fetcher_thread.start()

# Регистрируем после первого запроса
@app.before_first_request
def initialize():
    start_background_tasks()

@app.route('/')
def health_check():
    # Если первый запрос — запустим фоновые задачи
    if fetcher_thread is None:
        start_background_tasks()
    return "OK", 200

# Для локального запуска
if __name__ == "__main__":
    start_background_tasks()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
