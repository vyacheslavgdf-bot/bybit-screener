# main.py
import os
import time
import schedule
import requests
import pandas as pd
import numpy as np
from telegram import Bot

# === 1. Загрузка токена и ID из переменных окружения ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUR_TELEGRAM_ID = os.getenv("YOUR_TELEGRAM_ID")

if not TELEGRAM_BOT_TOKEN or not YOUR_TELEGRAM_ID:
    raise RuntimeError("❌ ОШИБКА: Не заданы TELEGRAM_BOT_TOKEN или YOUR_TELEGRAM_ID в Render!")

# === 2. Инициализация бота ===
bot = Bot(token=TELEGRAM_BOT_TOKEN)

def send_telegram_message(text: str):
    """Универсальная функция отправки сообщения в Telegram."""
    try:
        bot.send_message(chat_id=int(YOUR_TELEGRAM_ID), text=text)
        print(f"✅ Отправлено: {text[:50]}...")
    except Exception as e:
        print(f"❌ Ошибка Telegram: {e}")

def get_bybit_klines(symbol: str, interval: str = "15", limit: int = 100):
    """Получает последние свечи с Bybit (публичный API)."""
    url = "https://api.bybit.com/v5/market/kline"
    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if data.get("retCode") != 0:
            print(f"⚠️ Bybit API ошибка для {symbol}: {data.get('retMsg')}")
            return None
        df = pd.DataFrame(
            data["result"]["list"],
            columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"]
        )
        df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit='ms')
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df
    except Exception as e:
        print(f"❌ Ошибка загрузки данных Bybit для {symbol}: {e}")
        return None

def calculate_indicators(df: pd.DataFrame):
    """Рассчитывает MA, RSI, MACD."""
    df["ma5"] = df["close"].rolling(5).mean()
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()

    # RSI
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    # MACD
    exp12 = df["close"].ewm(span=12).mean()
    exp26 = df["close"].ewm(span=26).mean()
    df["macd"] = exp12 - exp26
    df["macd_signal"] = df["macd"].ewm(span=9).mean()
    return df

def scan_signals():
    """Основная логика сканирования."""
    symbols = ["BTCUSDT", "ETHUSDT"]  # можно расширить
    for symbol in symbols:
        df = get_bybit_klines(symbol, interval="15", limit=100)
        if df is None or len(df) < 25:
            continue

        df = calculate_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]

        # Проверка: закрыта ли последняя свеча (ждём полного закрытия таймфрейма)
        candle_age_ms = time.time() * 1000 - last["timestamp"].timestamp() * 1000
        if candle_age_ms < 15 * 60 * 1000:  # если прошло <15 минут — свеча ещё формируется
            continue

        # Условия LONG
        ma_ok = last["ma5"] > last["ma10"] > last["ma20"]
        rsi_ok = 50 < last["rsi"] < 70
        macd_cross = last["macd"] > last["macd_signal"] and prev["macd"] <= prev["macd_signal"]
        volume_ok = last["volume"] > df["volume"].rolling(20).mean().iloc[-1] * 1.5
        bullish_candle = last["close"] > last["open"]

        if ma_ok and rsi_ok and macd_cross and volume_ok and bullish_candle:
            msg = (
                f"🟢 LONG СИГНАЛ\n"
                f"Пара: {symbol}\n"
                f"Цена: {last['close']:.2f}\n"
                f"Объём: ↑ {last['volume']:.1f}\n"
                f"RSI: {last['rsi']:.1f}\n"
                f"MA: 5({last['ma5']:.2f}) > 10({last['ma10']:.2f}) > 20({last['ma20']:.2f})"
            )
            send_telegram_message(msg)

    print("🔍 Сканирование завершено.")

# === 3. ЗАПУСК ===
if __name__ == "__main__":
    print("🚀 Запуск бота...")
    send_telegram_message("✅ Бот запущен! Сканирование каждые 2 минуты.")

    # Сканировать каждые 2 минуты
    schedule.every(2).minutes.do(scan_signals)

    # Запуск немедленно при старте (опционально)
    scan_signals()

    while True:
        schedule.run_pending()
        time.sleep(10)