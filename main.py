def get_top_symbols(limit=30):
    """Получить топ монет по обороту (только USDT пары)"""
    try:
        url = "https://api.bybit.com/v5/market/tickers?category=linear"
        response = requests.get(url, timeout=10)

        # Проверяем, что ответ не пустой и не HTML
        if not response.text.strip():
            send_telegram("❌ Bybit API вернул пустой ответ. Повторная попытка через 5 мин.")
            return []
        
        if "<html" in response.text.lower():
            send_telegram("❌ Bybit API вернул HTML (возможно, капча или rate limit).")
            return []

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

    except json.JSONDecodeError as e:
        send_telegram(f"❌ Ошибка JSON при разборе ответа Bybit: {str(e)}")
        return []
    except Exception as e:
        send_telegram(f"❌ Исключение при получении списка монет: {str(e)}")
        return []
