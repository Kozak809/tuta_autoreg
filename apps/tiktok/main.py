"""
Continuous multi-threaded account registrar for TikTok.

This script orchestrates the mass registration of TikTok accounts by managing a
pool of worker threads, maintaining a continuous supply of proxies, and running
the registration macro until a specified target number of accounts is reached.
"""
import os, time, sys, json, asyncio, psutil
# Добавляем корень проекта в sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import random
import queue
import threading
import builtins
import argparse
from concurrent.futures import ThreadPoolExecutor
from filelock import FileLock
from apps.tiktok import macro
from core import proxy_handler as proxy_fetcher
from apps.tuta.tuta_utils import start_xvfb

# --- НАСТРОЙКИ КОНВЕЙЕРА И ПАРСИНГ АРГУМЕНТОВ ---
ACCOUNTS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "accounts_tiktok.json"))
LOCK_FILE = os.path.join(os.path.dirname(__file__), "data/accounts_tiktok.lock")
xvfb_process = None

TARGET_ACCOUNTS = 1
MAX_WORKERS = 1
ONLY_SUCCESS_LOGS = False
SHOW_CURSOR = False
HEADLESS = False
USE_XVFB = True

# --- ФИЛЬТРАЦИЯ ЛОГОВ ---
def custom_print(*args, **kwargs):
    if not args:
        if not ONLY_SUCCESS_LOGS:
            builtins._original_print(*args, **kwargs)
        return
    msg = str(args[0])
    if ONLY_SUCCESS_LOGS:
        # Выводим только финальные сообщения об успехе
        if "[!!!]" in msg or "[+++]" in msg:
            builtins._original_print(*args, **kwargs)
    else:
        builtins._original_print(*args, **kwargs)

# Общая очередь для прокси
PROXY_QUEUE = queue.Queue()

def save_account_safe(email, password, config_path="N/A", note=""):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "email": email,
        "password": password,
        "config_path": config_path,
        "timestamp": now,
        "last_check": now,
        "isvalid": "INVALID" if note else "VALID"
    }
    if note:
        data["note"] = note

    save_dir = os.path.dirname(ACCOUNTS_FILE)
    os.makedirs(save_dir, exist_ok=True)
    
    with FileLock(LOCK_FILE):
        with open(ACCOUNTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")

def get_success_count():
    if not os.path.exists(ACCOUNTS_FILE): return 0
    count = 0
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip(): count += 1
    except: pass
    return count

def worker_task(worker_id, initial_count, show_cursor, headless):
    """
    Постоянный воркер: берет прокси из очереди и сразу запускает макрос.
    """
    attempts = 0
    print(f"[*] [Worker {worker_id}] Запущен и готов к работе.")
    
    while True:
        # 1. Проверяем общую цель
        current_count = get_success_count()
        if current_count - initial_count >= TARGET_ACCOUNTS:
            print(f"[*] [Worker {worker_id}] Цель достигнута. Завершаю работу.")
            break
            
        # 2. Берем прокси из очереди (ждем, если пусто)
        try:
            link = PROXY_QUEUE.get(timeout=10)
        except queue.Empty:
            continue

        # 3. Рассчитываем порт (свой диапазон для каждого воркера)
        # Использование портов 20000+ для TikTok во избежание конфликтов с Tuta
        port = 20000 + (worker_id * 1000) + (attempts % 900)
        
        print(f"[*] [Worker {worker_id}] Взял прокси. Попытка #{attempts+1} на порту {port}...")
        try:
            # Запускаем макрос
            success = macro.run(link, port, save_account_safe, show_cursor=show_cursor, debug_mode=False, headless=headless)
            if success == "NO_ACCOUNTS":
                print(f"[-] [Worker {worker_id}] Нет доступных аккаунтов. Завершаю работу.")
                PROXY_QUEUE.task_done()
                break
            if not success:
                # Увеличиваем attempts, чтобы сменить порт для следующего прокси
                attempts += 1
                PROXY_QUEUE.task_done()
                time.sleep(random.uniform(1, 3))
                continue
        except Exception as e:
            print(f"[-] [Worker {worker_id}] Критическая ошибка: {e}")
        
        attempts += 1
        PROXY_QUEUE.task_done()
        
        # Небольшая пауза перед следующим прокси, чтобы система "продышалась"
        time.sleep(random.uniform(1, 3))

async def main():
    global TARGET_ACCOUNTS, MAX_WORKERS, ONLY_SUCCESS_LOGS, SHOW_CURSOR, HEADLESS, USE_XVFB
    parser = argparse.ArgumentParser(description="Continuous multi-threaded account registrar for TikTok.")
    parser.add_argument("target", type=int, nargs="?", default=TARGET_ACCOUNTS, help=f"Target number of accounts to create (default: {TARGET_ACCOUNTS})")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help=f"Number of concurrent browsers (default: {MAX_WORKERS})")
    parser.add_argument("--nologs", action="store_true", help="Show only success logs")
    parser.add_argument("--show", action="store_true", help="Show browser and cursor")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--noxvfb", action="store_true", help="Disable Xvfb (virtual display)")
    args = parser.parse_args()
    TARGET_ACCOUNTS = args.target
    MAX_WORKERS = args.workers
    ONLY_SUCCESS_LOGS = args.nologs
    SHOW_CURSOR = args.show
    HEADLESS = args.headless
    USE_XVFB = not args.noxvfb

    if USE_XVFB:
        HEADLESS = False

    if not hasattr(builtins, "_original_print"):
        builtins._original_print = builtins.print
        builtins.print = custom_print

    os.makedirs("temp", exist_ok=True)
    os.makedirs("logs/sessions", exist_ok=True)
    os.makedirs("data/configs_tiktok", exist_ok=True)

    global xvfb_process
    xvfb_process = None
    if USE_XVFB:
        import subprocess
        xvfb_process = start_xvfb(100, 120)  # Xvfb port 100 for TikTok

    initial_count = get_success_count()
    print(f"[#] КОНВЕЙЕР TIKTOK (НЕПРЕРЫВНЫЙ) ЗАПУЩЕН.")
    print(f"[#] Цель: {TARGET_ACCOUNTS}. Потоков: {MAX_WORKERS}. Headless: {HEADLESS}")

    # Запускаем воркеров в ThreadPoolExecutor
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    for i in range(MAX_WORKERS):
        executor.submit(worker_task, i, initial_count, SHOW_CURSOR, HEADLESS)

    try:
        while True:
            current_count = get_success_count()
            if current_count - initial_count >= TARGET_ACCOUNTS:
                print(f"[*] Цель достигнута. Принудительно завершаем работу всех потоков...")
                break

            # Если очередь прокси пустеет — подливаем новые
            if PROXY_QUEUE.qsize() < MAX_WORKERS * 2:
                print("[*] Очередь прокси пуста, запрашиваю новые...")
                links = proxy_fetcher.update_proxies_python()
                if links:
                    for l in links:
                        PROXY_QUEUE.put(l)
                    print(f"[+] Добавлено {len(links)} прокси в очередь.")
                else:
                    print("[-] Прокси не получены, ждем 20 сек...")
            
            await asyncio.sleep(20)
    except KeyboardInterrupt:
        print("[!] Остановка пользователем...")
    finally:
        executor.shutdown(wait=False)
        final_count = get_success_count()
        print(f"[+++] ВСЕГО СОЗДАНО: {final_count - initial_count}. Остановка дочерних процессов (браузеров)...")
        try:
            parent = psutil.Process(os.getpid())
            children = parent.children(recursive=True)
            for child in children:
                try: child.kill()
                except Exception: pass
            psutil.wait_procs(children, timeout=3)
        except Exception:
            pass
            
        if 'xvfb_process' in globals() and xvfb_process:
            try: xvfb_process.kill()
            except: pass
            
        print("[+++] Скрипт полностью остановлен.")
        os._exit(0)

if __name__ == "__main__":
    asyncio.run(main())
