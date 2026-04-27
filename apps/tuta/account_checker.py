import os
import sys
# Добавляем корень проекта в sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import time
import json
import random
import requests
import re
import argparse
import queue
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor
from filelock import FileLock
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from core.proxy_handler import ProxyManager
from core.mouse_engine import HumanCursor
from core import proxy_handler as proxy_fetcher
from core import browser_factory as playwright_config
from core.utils import human_delay, load_accounts

from apps.tuta.tuta_utils import resolve_config_path, check_tuta_errors, start_xvfb, login_to_tuta

# --- НАСТРОЙКИ ---
MAX_WORKERS = 15            # Количество одновременных браузеров
ACCOUNTS_FILE = "data/accounts.json"
LOCK_FILE = "data/accounts.lock"

ACCOUNT_QUEUE = queue.Queue()
PROXY_QUEUE = queue.Queue()

def save_result(account, status):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    email = account['email']
    
    with FileLock(LOCK_FILE):
        # 1. Загружаем все текущие аккаунты из файла
        all_accounts = load_accounts(ACCOUNTS_FILE)
        
        # 2. Ищем нужный аккаунт и обновляем его статус
        updated = False
        for acc in all_accounts:
            if acc['email'] == email:
                acc.update({
                    "isvalid": "VALID" if status == "VALID" else "INVALID",
                    "last_check": now
                })
                updated = True
                break
        
        # 3. Если аккаунта почему-то нет в списке, добавляем его (на всякий случай)
        if not updated:
            new_data = account.copy()
            new_data.update({
                "isvalid": "VALID" if status == "VALID" else "INVALID",
                "last_check": now
            })
            all_accounts.append(new_data)
            
        # 4. Перезаписываем файл целиком (безопасно под локом)
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            for acc in all_accounts:
                f.write(json.dumps(acc) + "\n")

def check_account_task(account, link, port, show_cursor, headless, saved_config=None):
    email = account['email']
    password = account['password']
    
    pm = ProxyManager(link, port)
    if not pm.start():
        return "RETRY"

    try:
        with sync_playwright() as pw:
            # Если конфиг не передан — пробуем загрузить его (для совместимости)
            if not saved_config:
                saved_config, _ = resolve_config_path(account.get("config_path"))

            if saved_config:
                browser_config = saved_config.get("browser_config", {})
                # Принудительно устанавливаем headless режим и порт прокси из текущей сессии
                browser_config["headless"] = headless
                if port:
                    browser_config["proxy"] = {"server": f"socks5://127.0.0.1:{port}"}
                
                context_args = saved_config.get("context_args", {})
                hardware_info = saved_config.get("hardware_info", {})
            else:
                browser_config = playwright_config.get_browser_config(headless=headless, port=port)
                # Если конфига нет, генерируем случайный контекст
                context_args, hardware_info = playwright_config.get_context_config()

            browser = pw.chromium.launch(**browser_config)
            context = browser.new_context(**context_args)
            
            stealth_script = playwright_config.get_stealth_script(hardware_info)
            context.add_init_script(stealth_script)
            
            page, cursor = playwright_config.init_page(context, show_cursor=show_cursor)
            
            page.goto("https://app.tuta.com/login", wait_until="domcontentloaded", timeout=60000)
            human_delay(2, 4)
            
            # Проверка первичного блока IP
            status, is_crit = check_tuta_errors(page)
            if status in ["IP_BLOCKED", "CONNECTION_LOST"]:
                return "RETRY"

            # Ввод данных
            print(f"[*] [{email}] Проверка...")
            try:
                login_to_tuta(page, cursor, email, password)
            except:
                return "RETRY"

            # Ожидание результата
            start_wait = time.time()
            while time.time() - start_wait < 30:
                status, is_crit = check_tuta_errors(page)
                if is_crit:
                    save_result(account, status)
                    print(f"[-] [{email}] Результат: {status}")
                    return "DONE"
                
                if status in ["IP_BLOCKED", "CONNECTION_LOST"]:
                    return "RETRY"

                # Успешный вход
                if page.locator("button[title='New email'], div.folder-item").first.is_visible():
                    save_result(account, "VALID")
                    print(f"[+] [{email}] Результат: VALID")
                    return "DONE"
                
                time.sleep(1)
            
            return "RETRY"
            
    except Exception as e:
        print(f"[-] [{email}] Ошибка: {e}")
        return "RETRY"
    finally:
        pm.stop()

def worker_thread(worker_id, show_cursor, headless):
    while not ACCOUNT_QUEUE.empty():
        account = ACCOUNT_QUEUE.get()
        email = account['email']
        
        # 1. Загружаем конфиг, чтобы вытащить оттуда родной прокси
        saved_config, _ = get_account_config(account)
        
        success = False
        attempts = 0

        # 2. Сначала пробуем родной прокси из конфига (если он есть)
        config_proxy = saved_config.get("proxy") if saved_config else None
        if config_proxy:
            print(f"[*] [{email}] Пробуем родной прокси из конфига...")
            port = 11000 + (worker_id * 100) + (attempts % 90)
            res = check_account_task(account, config_proxy, port, show_cursor, headless, saved_config=saved_config)
            if res == "DONE":
                success = True
            elif res == "RETRY":
                attempts += 1
                print(f"[*] [{email}] Родной прокси не сработал, переходим к общим.")

        # 3. Если родной прокси не помог (или его нет) — берем прокси из очереди
        if not success:
            while attempts < 10: # Максимум 10 прокси на один аккаунт
                try:
                    link = PROXY_QUEUE.get(timeout=20)
                except:
                    print(f"[*] [Worker {worker_id}] Ждем прокси...")
                    time.sleep(5)
                    continue

                port = 11000 + (worker_id * 100) + (attempts % 90)
                res = check_account_task(account, link, port, show_cursor, headless, saved_config=saved_config)
                
                PROXY_QUEUE.task_done()
                
                if res == "DONE":
                    success = True
                    break
                elif res == "RETRY":
                    attempts += 1
                    print(f"[*] [{email}] Прокси плохой, пробуем другой... (Попытка {attempts})")
                    continue
        
        if not success:
            print(f"[-] [{email}] Не удалось проверить (проблемы с прокси).")
            # Можно вернуть в очередь, если нужно: ACCOUNT_QUEUE.put(account)
            
        ACCOUNT_QUEUE.task_done()

def main():
    parser = argparse.ArgumentParser(description="Tuta Account Checker (Parallel)")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help="Number of workers")
    parser.add_argument("--accounts", default="data/accounts.json", help="Path to accounts JSON file")
    parser.add_argument("--show", action="store_true", help="Show cursor")
    parser.add_argument("--headless", action="store_true", default=False, help="Run browser in headless mode")
    parser.add_argument("--xvfb", action="store_true", help="Run browser in Xvfb (virtual display)")
    args = parser.parse_args()

    headless = args.headless
    if args.xvfb:
        headless = False # При Xvfb браузер должен быть в оконном режиме
        xvfb_process = start_xvfb(200, 250)

    global ACCOUNTS_FILE
    ACCOUNTS_FILE = args.accounts
    accounts = load_accounts(ACCOUNTS_FILE)
    if not accounts:
        print(f"[-] {args.accounts} не найден или пуст.")
        return
    
    print(f"[*] Загружено {len(accounts)} аккаунтов для проверки.")
    for acc in accounts:
        ACCOUNT_QUEUE.put(acc)

    # Первичная загрузка прокси
    print("[*] Загрузка прокси...")
    links = proxy_fetcher.update_proxies_python()
    for l in links: PROXY_QUEUE.put(l)

    # Запуск потоков
    threads = []
    for i in range(args.workers):
        t = threading.Thread(target=worker_thread, args=(i, args.show, headless))
        t.daemon = True
        t.start()
        threads.append(t)

    # Мониторинг прокси в основном потоке
    try:
        while any(t.is_alive() for t in threads):
            if PROXY_QUEUE.qsize() < args.workers * 2:
                new_links = proxy_fetcher.update_proxies_python()
                if new_links:
                    for l in new_links: PROXY_QUEUE.put(l)
            time.sleep(15)
    except KeyboardInterrupt:
        print("[!] Остановка...")

    print("[*] Проверка завершена.")
    
    if args.xvfb and 'xvfb_process' in locals() and xvfb_process:
        print("[*] Остановка Xvfb...")
        xvfb_process.kill()

if __name__ == "__main__":
    main()
