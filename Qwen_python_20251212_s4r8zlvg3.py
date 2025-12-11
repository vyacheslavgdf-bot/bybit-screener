import os
import time
import json
import schedule
import requests
import numpy as np
from datetime import datetime, timezone

# === НАСТРОЙКИ ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUR_TELEGRAM_ID = os.getenv("YOUR_TELEGRAM_ID")

if not TELEGRAM_BOT_TOKEN or not YOUR_TELEGRAM_ID:
    raise ValueError("Ошибка: не заданы TELEGRAM_BOT_TOKEN или YOUR_TELEGRAM_ID в переменных окружения!")

try:
    YOUR_TELEGRAM_ID = int(YOUR_TELEGRAM_ID)
except ValueError:
    raise ValueError("YOUR_TELEGRAM_ID должен быть числом!")

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def send_telegram(message):
    """Отправка сообщения в Telegram с обработкой ошибок"""
    try:
        payload = {
            "chat_id": YOUR_TELEGRAM_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(TELEGRAM_URL, json=payload, timeout=10)
        if not response.ok:
            print(f"Ошибка Telegram API: {response.status_code} - {response.text}")
        return response
    except Exception as e:
        print(f"Исключение при отправке в Telegram: {e}")
        return None

def get_top_symbols(limit=30):
    """Получить топ монет по обороту (только USDT пары)"""
    try:
        url = "https://api.bybit.com/v5/market/tickers?category=linear"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("retCode") != 0:
            send_telegram(f"❌ Ошибка Bybit API при получении списка монет: {data.get('retMsg')}")
            return []

        symbols = []
        for item in data["result"]["list"]:
            if "USDT" in item["symbol"] and not "USDC" in item["symbol"]:
                try:
                    vol = float(item["turnover24h"])
                    symbols.append((item["symbol"], vol))
                except (ValueError, KeyError):
                    continue

        symbols.sort(key=lambda x: x[1], reverse=True)
        top_symbols = [s[0] for s in symbols[:limit]]
        return top_symbols
    except Exception as e:
        send_telegram(f"❌ Исключение при получении списка монет: {str(e)}")
        return []

def get_klines(symbol, interval="60", limit=50):
    """Получить свечи"""
    try:
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={interval}&limit={limit}"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("retCode") != 0:
            print(f"Bybit ошибка для {symbol}: {data.get('retMsg')}")
            return []

        # Bybit возвращает: [start, open, high, low, close, ...]
        closes = []
        for candle in data["result"]["list"]:
            try:
                closes.append(float(candle[4]))
            except (IndexError, ValueError):
                continue
        return closes[::-1]  # Переворачиваем: от старых к новым
    except Exception as e:
        print(f"Исключение при получении свечей {symbol}: {e}")
        return []

def calculate_rsi(prices, period=14):
    """Простой RSI без talib"""
    if len(prices) < period + 1:
        return 50
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_ma(prices, period):
    if len(prices) < period:
        return None
    return np.mean(prices[-period:])

def is_valid_signal(symbol, closes):
    """Упрощённые условия для теста (замените на свои!)"""
    if len(closes) < 20:
        return False

    # Пример: просто проверим, что цена упала на 1% за последний час
    current = closes[-1]
    previous = closes[-2]
    change_pct = (current - previous) / previous

    # Добавим RSI
    rsi = calculate_rsi(closes)

    # ДЕБАГ: отправим данные по BTC всегда
    if symbol == "BTCUSDT":
        debug_msg = (
            f"🔍 DEBUG BTC:\n"
            f"Цена: {current:.6f}\n"
            f"Изменение: {change_pct*100:.2f}%\n"
            f"RSI: {rsi:.1f}"
        )
        send_telegram(debug_msg)

    # Условие для сигнала (временно простое!)
    if change_pct < -0.01 and rsi < 40:  # падение >1% и RSI < 40
        return True
    return False

def scan_market():
    """Основной цикл сканирования"""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    send_telegram(f"🕗 <b>Запуск сканирования</b>\nВремя: {now_utc}")

    symbols = get_top_symbols(limit=20)
    send_telegram(f"Анализирую {len(symbols)} монет...")

    signals_found = 0
    for symbol in symbols[:5]:  # Анализируем только первые 5 для debug
        closes = get_klines(symbol, interval="60", limit=30)
        if not closes:
            continue

        if is_valid_signal(symbol, closes):
            msg = f"⚡️ <b>СИГНАЛ</b>: {symbol}\nВход: {closes[-1]:.6f}"
            send_telegram(msg)
            signals_found += 1
            time.sleep(1)  # избегаем лимитов Telegram

    if signals_found == 0:
        send_telegram("⚠️ Нет сигналов по текущим условиям.")

def run():
    """Инициализация"""
    send_telegram("✅ <b>Debug-бот запущен!</b>\nСканирование каждые 5 минут.")
    scan_market()  # Первый запуск сразу
    schedule.every(5).minutes.do(scan_market)

    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("Остановка...")
    except Exception as e:
        error_msg = f"❌ КРИТИЧЕСКАЯ ОШИБКА:\n{str(e)}"
        print(error_msg)
        send_telegram(error_msg)