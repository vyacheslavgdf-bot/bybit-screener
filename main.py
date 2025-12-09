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
        logger.error(f"Ошибка получения данных {exchange} {symbol}: {e}")
        return None

def calculate_indicators(df):
    close = df["close"].values
    volume = df["volume"].values
    high = df["high"].values
    low = df["low"].values

    # MA
    ma5 = pd.Series(close).rolling(window=5).mean().iloc[-1]
    ma10 = pd.Series(close).rolling(window=10).mean().iloc[-1]
    ma20 = pd.Series(close).rolling(window=20).mean().iloc[-1]

    # RSI 10
    delta = np.diff(close)
    gain = (delta > 0) * delta
    loss = (delta < 0) * -delta
    avg_gain = np.mean(gain[-10:]) if len(gain) >= 10 else 0
    avg_loss = np.mean(loss[-10:]) if len(loss) >= 10 else 0
    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    rsi = 100 - (100 / (1 + rs)) if rs != 0 else 0

    # MACD
    ema12 = pd.Series(close).ewm(span=12, adjust=False).mean().iloc[-1]
    ema26 = pd.Series(close).ewm(span=26, adjust=False).mean().iloc[-1]
    macd_line = ema12 - ema26
    signal_line = pd.Series([ema12 - ema26] * 9).ewm(span=9, adjust=False).mean().iloc[-1] if len(close) >= 9 else 0
    if len(close) >= 35:
        macd_full = pd.Series(close).ewm(span=12, adjust=False).mean() - pd.Series(close).ewm(span=26, adjust=False).mean()
        signal_line = macd_full.ewm(span=9, adjust=False).mean().iloc[-1]
    else:
        signal_line = macd_line

    # Средний объём за последние 20 свечей
    avg_volume = np.mean(volume[-20:]) if len(volume) >= 20 else 0
    current_volume = volume[-1]

    # ATR (опционально — можно включить)
    # tr = np.maximum(high - low, np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))))
    # atr = pd.Series(tr).rolling(window=14).mean().iloc[-1]
    # avg_atr = np.mean(pd.Series(tr).rolling(window=14).mean()[-20:]) if len(tr) >= 20 else 0

    return ma5, ma10, ma20, rsi, macd_line, signal_line, avg_volume, current_volume

def scan_for_signals():
    long_signals = []
    short_signals = []

    for symbol in SYMBOLS:
        for exchange in ["bybit", "binance"]:
            df = fetch_klines(symbol, exchange)
            if df is None or len(df) < 50:
                continue

            ma5, ma10, ma20, rsi, macd_line, signal_line, avg_volume, current_volume = calculate_indicators(df)

            # Анализируем ПРЕДЫДУЩУЮ (закрытую) свечу
            if len(df) < 2:
                continue
            current_price = df["close"].iloc[-2]  # ← ЗАКРЫТИЕ ПРЕДЫДУЩЕЙ СВЕЧИ
            current_volume_prev = df["volume"].iloc[-2]  # объём предыдущей свечи

            # LONG: цена > MA5, MA10, MA20 + RSI < 70 + MACD > Signal + Объём > 1.5x среднего
            if (current_price > ma5 and current_price > ma10 and current_price > ma20 and
                rsi < 70 and macd_line > signal_line and
                current_volume_prev > avg_volume * 1.5):  # ← ФИЛЬТР ОБЪЁМА
                long_signals.append(f"✅ {symbol.upper()} ({exchange.title()}) [RSI={rsi:.2f}, Vol={current_volume_prev:.0f}]")

            # SHORT: цена < MA5, MA10, MA20 + RSI > 30 + MACD < Signal + Объём > 1.5x среднего
            elif (current_price < ma5 and current_price < ma10 and current_price < ma20 and
                  rsi > 30 and macd_line < signal_line and
                  current_volume_prev > avg_volume * 1.5):  # ← ФИЛЬТР ОБЪЁМА
                short_signals.append(f"🔻 {symbol.upper()} ({exchange.title()}) [RSI={rsi:.2f}, Vol={current_volume_prev:.0f}]")

    return long_signals, short_signals

def send_report():
    try:
        logger.info("🔍 Сканирование Bybit + Binance (MA 5/10/20 + RSI + MACD + Volume Filter)...")
        longs, shorts = scan_for_signals()

        message = "📊 Сигналы по стратегии:\n"
        message += "📈 LONG: цена > MA5, MA10, MA20 + RSI < 70 + MACD > Signal + Объём > 1.5x\n"
        message += "📉 SHORT: цена < MA5, MA10, MA20 + RSI > 30 + MACD < Signal + Объём > 1.5x\n\n"

        if longs:
            message += "✅ LONG:\n" + "\n".join(longs) + "\n\n"
        if shorts:
            message += "🔻 SHORT:\n" + "\n".join(shorts) + "\n\n"
        if not longs and not shorts:
            message += "🔍 Нет сигналов."

        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info(f"✅ Отправлено: {len(longs)} LONG, {len(shorts)} SHORT")

    except TelegramError as e:
        logger.error(f"❌ Ошибка Telegram: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

# === Основной цикл ===
if __name__ == "__main__":
    send_report()
    schedule.every(15).minutes.do(send_report)
    while True:
        schedule.run_pending()
        time.sleep(30)
