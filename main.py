def get_top_symbols(limit=20):
    try:
        url = "https://api.bybit.com/v5/market/tickers?category=linear"
        response = requests.get(url, timeout=10)
        
        # 👇 Отправляем первые 100 символов ответа в Telegram для отладки
        send_telegram(f"📡 Ответ Bybit API (первые 100 символов):\n{response.text[:100]}")
        
        if not response.text.strip():
            send_telegram("❌ Bybit API вернул пустой ответ.")
            return []
        
        if "<html" in response.text.lower():
            send_telegram("❌ Bybit API вернул HTML (возможно, капча или rate limit).")
            return []

        data = response.json()

        if data.get("retCode") != 0:
            send_telegram(f"❌ Ошибка Bybit API: {data.get('retMsg')}")
            return []

        symbols = []
        for item in data["result"]["list"]:
            if "USDT" in item["symbol"] and "USDC" not in item["symbol"]:
                try:
                    vol = float(item["turnover24h"])
                    symbols.append((item["symbol"], vol))
                except (ValueError, KeyError):
                    continue

        symbols.sort(key=lambda x: x[1], reverse=True)
        top_symbols = [s[0] for s in symbols[:limit]]
        send_telegram(f"✅ Найдено {len(top_symbols)} монет: {top_symbols[:3]}")
        return top_symbols

    except json.JSONDecodeError as e:
        send_telegram(f"❌ Ошибка JSON: {str(e)}\nОтвет: {response.text[:100]}")
        return []
    except Exception as e:
        send_telegram(f"❌ Исключение: {str(e)}")
        return []
