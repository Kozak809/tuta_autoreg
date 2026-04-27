import os
import json
import time
import random
import requests

# Базовые пути проекта
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
PROXY_PATH = os.path.join(DATA_DIR, "proxy_list.txt")

def human_delay(min_s=1, max_s=3):
    time.sleep(random.uniform(min_s, max_s))

def load_accounts(file_path):
    accounts = []
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content: return []
            try:
                # Пробуем распарсить как JSON массив
                data = json.loads(content)
                if isinstance(data, list): 
                    accounts = data
                else: 
                    accounts = [data]
            except json.JSONDecodeError:
                # Если не вышло, пробуем как JSON Lines
                f.seek(0)
                for line in f:
                    if line.strip():
                        try:
                            accounts.append(json.loads(line))
                        except:
                            pass
    return accounts

def get_proxy_info(port):
    """Получает информацию о геопозиции прокси через ip-api."""
    try:
        proxies = {'http': f'socks5h://127.0.0.1:{port}', 'https': f'socks5h://127.0.0.1:{port}'}
        # Используем fields чтобы минимизировать трафик
        resp = requests.get("http://ip-api.com/json/?fields=status,timezone,countryCode", proxies=proxies, timeout=10)
        data = resp.json()
        if data.get("status") == "success":
            cc = data.get("countryCode", "US")
            timezone = data.get("timezone", "UTC")
            # Генерируем локаль на основе кода страны
            locale = f"en-{cc}" if cc == "US" else f"{cc.lower()}-{cc}"
            return {"timezone": timezone, "locale": locale}
    except:
        pass
    return {"timezone": "UTC", "locale": "en-US"}

def check_proxy_connectivity(port, url="https://www.google.com", timeout=15):
    """Проверяет работоспособность прокси-туннеля через requests."""
    try:
        proxies = {'http': f'socks5h://127.0.0.1:{port}', 'https': f'socks5h://127.0.0.1:{port}'}
        resp = requests.get(url, proxies=proxies, timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False
