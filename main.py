def send_telegram(message):
    """Отправка сообщения в Telegram с отладкой"""
    try:
        payload = {
            "chat_id": YOUR_TELEGRAM_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        print(f"📤 Попытка отправить: {message}", flush=True)
        response = requests.post(TELEGRAM_URL, json=payload, timeout=10)
        if response.ok:
            print(f"✅ Успешно отправлено", flush=True)
        else:
            print(f"❌ Ошибка Telegram API: {response.status_code} - {response.text}", flush=True)
        return response
    except Exception as e:
        print(f"❌ Исключение при отправке: {e}", flush=True)
        return None
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

    except json.JSONDecodeError as e:
        send_telegram(f"❌ Ошибка JSON при разборе ответа Bybit: {str(e)}")
        return []
    except Exception as e:
        send_telegram(f"❌ Исключение при получении списка монет: {str(e)}")
        return []
