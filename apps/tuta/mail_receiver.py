"""
Automated email receiver and monitor for Tuta accounts.

This script logs into a specific Tuta account and continuously monitors the inbox
and spam folders for new messages. It extracts and displays the text of incoming
emails and can be configured to search for specific verification codes.
"""
import os
import sys
# Добавляем корень проекта в sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import time
import json
import random
import requests
import shutil
import re
import argparse
import subprocess
from playwright.sync_api import sync_playwright
from core.proxy_handler import ProxyManager
from core.mouse_engine import HumanCursor
from core import proxy_handler as proxy_fetcher
from core import browser_factory as playwright_config
from core.utils import human_delay, load_accounts, get_proxy_info, check_proxy_connectivity
from apps.tuta.macro import check_block
from apps.tuta.tuta_utils import resolve_config_path, check_tuta_errors, start_xvfb, login_to_tuta

# Удалено: human_delay перенесен в core.utils

def select_account(file_path, email_arg=None):
    accounts = load_accounts(file_path)
    if not accounts:
        print(f"[-] {file_path} не найден или пуст.")
        return None
    
    if email_arg:
        for acc in accounts:
            if acc['email'] == email_arg:
                return acc
        print(f"[-] Аккаунт {email_arg} не найден в {file_path}.")
        return None

    print("[*] Доступные аккаунты (последние 10):")
    start_idx = max(0, len(accounts) - 10)
    for i, acc in enumerate(accounts[start_idx:]):
        print(f"[{start_idx + i}] {acc['email']}")
    
    choice = input(f"\nВыберите номер аккаунта (по умолчанию {len(accounts)-1}): ")
    if not choice.strip():
        return accounts[-1]
    
    try:
        idx = int(choice)
        if 0 <= idx < len(accounts):
            return accounts[idx]
        else:
            print("[-] Неверный индекс, берем последний.")
            return accounts[-1]
    except:
        print("[-] Ошибка ввода, берем последний.")
        return accounts[-1]

# Удалено: check_proxy_connectivity перенесен в core.proxy_handler

def run_receiver(account, show_cursor=True, headless=False, one_code=False):
    email = account['email']
    password = account['password']
    
    # Попытка загрузить конфиг
    config_path = account.get("config_path")
    saved_config = None
    if config_path:
        # Проверяем несколько вариантов пути, чтобы конфиг находился независимо от директории запуска
        possible_paths = [
            config_path, # если запускаем из apps/tuta
            os.path.join(os.path.dirname(__file__), config_path), # относительно скрипта
            os.path.join("apps", "tuta", config_path) # если запускаем из корня проекта
        ]
        
        for cp in possible_paths:
            if os.path.exists(cp):
                try:
                    with open(cp, "r", encoding="utf-8") as f:
                        saved_config = json.load(f)
                    print(f"[*] Загружен профиль из {cp}")
                    break
                except Exception as e:
                    print(f"[-] Ошибка чтения конфига: {e}")

    success = False
    
    # 1. Попробуем сначала прокси из конфига
    links_to_try = []
    if saved_config and saved_config.get("proxy"):
        links_to_try.append(saved_config["proxy"])
        print(f"[*] Добавлен прокси из конфига: {saved_config['proxy'][:30]}...")

    if not links_to_try:
        # 2. Подготовим остальные прокси как запасной вариант
        print("[*] Обновление запасных прокси...")
        proxy_fetcher.update_proxies_python()
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "proxy_list.txt"),
            os.path.abspath(os.path.join(os.getcwd(), "data", "proxy_list.txt")),
            "data/proxy_list.txt"
        ]
        proxy_path = None
        for p in possible_paths:
            if os.path.exists(p):
                proxy_path = p
                break
                
        if proxy_path:
            with open(proxy_path, "r", encoding="utf-8") as f:
                fallback_links = [l.strip() for l in f if l.lower().startswith(("vless://", "trojan://", "ss://", "vmess://"))]
                random.shuffle(fallback_links)
                links_to_try.extend(fallback_links[:10])
                
    if not links_to_try:
        print("[-] Прокси не найдены ни в конфиге, ни в списке.")
        return

    for link in links_to_try:
        port = 8000 + random.randint(0, 1000)
        pm = ProxyManager(link, port)
        if not pm.start():
            continue
            
        print(f"[*] Проверка прокси {link[:30]}...")
        if not check_proxy_connectivity(port):
            print("[-] Прокси не прошел проверку связи. Пробуем следующий...")
            pm.stop()
            continue

        proxy_info = get_proxy_info(port)
        print(f"[*] Локаль: {proxy_info['locale']}, Таймзона: {proxy_info['timezone']}")

        try:
            with sync_playwright() as pw:
                if saved_config:
                    browser_config = saved_config.get("browser_config", {})
                    browser_config["headless"] = headless
                    # Обновляем порт прокси на текущий сгенерированный
                    if "proxy" in browser_config:
                        browser_config["proxy"] = {"server": f"socks5://127.0.0.1:{port}"}
                    
                    if "args" not in browser_config:
                        browser_config["args"] = []
                    context_args = saved_config.get("context_args", {})
                    hardware_info = saved_config.get("hardware_info", {})
                else:
                    browser_config = playwright_config.get_browser_config(headless=headless, port=port)
                    proxy_info = get_proxy_info(port)
                    context_args, hardware_info = playwright_config.get_context_config(proxy_info)

                browser = pw.chromium.launch(**browser_config)
                context = browser.new_context(**context_args)
                
                stealth_script = playwright_config.get_stealth_script(hardware_info)
                context.add_init_script(stealth_script)
                
                page, cursor = playwright_config.init_page(context, show_cursor=show_cursor)
                
                print(f"[*] Переход на страницу входа Tuta...")
                page.goto("https://app.tuta.com/login", wait_until="domcontentloaded", timeout=90000)
                human_delay(2, 4)
                
                if check_block(page):
                    pm.stop()
                    continue

                # Логин
                print("[*] Ввод данных...")
                login_to_tuta(page, cursor, email, password)
                
                print(f"[*] [{email}] Ожидание загрузки почты...")
                
                # Ждем загрузки интерфейса или сообщения об ошибке
                start_wait = time.time()
                success_login = False
                while time.time() - start_wait < 60:
                    check_page_status(page) # Мгновенная проверка на критические ошибки
                    
                    # Ищем признаки успеха
                    success_selectors = [
                        "button[title='New email']", 
                        "button[title='Новое письмо']", 
                        "div.folder-item:has-text('Inbox')",
                        "div.folder-item:has-text('Входящие')"
                    ]
                    for sel in success_selectors:
                        try:
                            if page.locator(sel).first.is_visible():
                                success_login = True
                                break
                        except: pass
                    
                    if success_login: break
                    time.sleep(1) # Короткая пауза между проверками
                
                if not success_login:
                    print("[-] Не дождались загрузки интерфейса почты.")
                    pm.stop()
                    continue

                print(f"[+] [{email}] Успешный вход!")
                
                # Мониторинг новых сообщений
                print("[*] Ожидание новых сообщений (Ctrl+C для выхода)...")
                
                # Функции для работы с письмами (фильтруем виртуальные элементы)
                def get_mail_items():
                    try:
                        # Ищем только видимые строки (li.list-row), у которых есть реальное содержимое
                        all_rows = page.locator("li.list-row").all()
                        valid_rows = []
                        for row in all_rows:
                            if row.is_visible():
                                # Проверяем, что aria-label не пустой и содержит данные (не просто "Unread")
                                div = row.locator("div[tabindex='0']").first
                                label = div.get_attribute("aria-label")
                                if label and len(label.strip()) > 15: # У реального письма длинный label
                                    valid_rows.append(row)
                        return valid_rows
                    except:
                        return []

                def get_msg_info(row):
                    try:
                        label = row.locator("div[tabindex='0']").first.get_attribute("aria-label")
                        return label.strip() if label else "Пусто"
                    except:
                        return "Ошибка"

                def get_msg_body(row):
                    try:
                        # Кликаем по интерактивному элементу внутри строки
                        interactive_div = row.locator("div[tabindex='0']").first
                        cursor.click(interactive_div)
                        human_delay(2.0, 3.0)
                        
                        # Пытаемся найти тело письма (с учетом Shadow DOM)
                        body_selectors = [
                            "#mail-body",
                            "#shadow-mail-body",
                            ".mail-viewer",
                            "div[role='article']",
                            "div.mail-body",
                            "div.mail-content"
                        ]
                        
                        for sel in body_selectors:
                            try:
                                el = page.locator(sel).first
                                # Ждем немного, пока элемент станет видимым и не пустым
                                if el.is_visible():
                                    text = el.inner_text().strip()
                                    if text and len(text) > 5: # Игнорируем слишком короткие заглушки
                                        return text
                            except: pass
                            
                        # Если не нашли обычным способом, пробуем вытащить текст через evaluate (может быть в shadow root)
                        try:
                            text = page.evaluate("""() => {
                                const body = document.querySelector('#mail-body');
                                if (body && body.shadowRoot) {
                                    return body.shadowRoot.textContent;
                                }
                                const shadowBody = document.querySelector('#shadow-mail-body');
                                if (shadowBody) return shadowBody.textContent;
                                return null;
                            }""")
                            if text and len(text.strip()) > 5:
                                return text.strip()
                        except: pass

                        return "Текст не найден или еще не загрузился."
                    except Exception as e:
                        return f"Ошибка при получении текста: {e}"

                items = get_mail_items()
                last_count = len(items)
                print(f"[*] Мониторинг запущен. Реальных писем обнаружено: {last_count}")
                if last_count > 0:
                    print(f"[*] Текст последнего письма: {get_msg_body(items[0])}")
                
                success = True
                while True:
                    if page.is_closed():
                        print("[*] Окно браузера закрыто пользователем. Завершаю мониторинг...")
                        break

                    time.sleep(4)
                    
                    # Постоянная проверка на ошибки во время мониторинга
                    try:
                        if not page.is_closed():
                            status, is_crit = check_tuta_errors(page)
                            if is_crit:
                                print(f"[-] КРИТИЧЕСКАЯ ОШИБКА: {status}. Завершение мониторинга.")
                                break
                            if status == "CONNECTION_LOST":
                                raise Exception("CONNECTION_LOST")
                    except: break
                    
                    # Проверка на вылет из аккаунта (сессия истекла)
                    try:
                        if page.is_closed(): break
                        if page.url.endswith("/login") or page.locator("button").filter(has_text=re.compile("Log in|Войти", re.IGNORECASE)).is_visible():
                            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [!] Сессия истекла (появилась кнопка входа). Выполняю повторный вход...")
                            login_to_tuta(page, cursor, email, password)
                            print(f"[*] Повторный вход отправлен. Ожидание загрузки...")
                            human_delay(5.0, 7.0)
                            continue
                    except Exception as e:
                        pass
                    
                    items = get_mail_items()
                    current_count = len(items)
                    
                    if current_count > last_count:
                        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] [!!!] ПОЛУЧЕНО НОВОЕ ПИСЬМО! Всего теперь: {current_count}")
                        print("-" * 50)
                        for i, item in enumerate(items):
                            info = get_msg_info(item)
                            print(f"[{i+1}] {info}")
                            # Для нового (первого) письма выводим текст
                            if i == 0:
                                body = get_msg_body(item)
                                print(f"    ТЕКСТ: {body}")
                                if one_code:
                                    found = re.findall(r'(?<!\d)\d{6}(?!\d)', body)
                                    if found:
                                        print(f"CODE_FOUND:{found[0]}", flush=True)
                                        return found[0]
                        print("-" * 50)
                        last_count = current_count
                    elif current_count < last_count:
                        # Если количество уменьшилось (удаление), просто обновляем счетчик
                        last_count = current_count
                    
                    # Переключаемся между Inbox и Spam по таймеру
                    now = time.time()
                    if not hasattr(run_receiver, "_last_switch"):
                        run_receiver._last_switch = now
                        run_receiver._next_delay = random.uniform(15, 30)
                        run_receiver._current_folder = "Inbox"

                    if now - run_receiver._last_switch > run_receiver._next_delay:
                        try:
                            # Чередуем Inbox и Spam
                            run_receiver._current_folder = "Spam" if run_receiver._current_folder == "Inbox" else "Inbox"
                            # Устанавливаем задержку для следующего переключения
                            if run_receiver._current_folder == "Inbox":
                                run_receiver._next_delay = random.uniform(15, 30)
                            else:
                                run_receiver._next_delay = random.uniform(15, 25)
                            
                            run_receiver._last_switch = now
                            
                            folder_btn = page.locator(f"[data-testid='btn:folder:{run_receiver._current_folder}']").first
                            if folder_btn.is_visible():
                                cursor.click(folder_btn)
                                human_delay(1.5, 2.5)
                        except: pass
                    
        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Ошибка в процессе (прокси {link[:20]}...): {e}")
        finally:
            pm.stop()
            if success: break
    
    if not success:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [-] Не удалось найти работающий прокси или выполнить вход.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tuta Email Receiver with Anti-Bot Protection.")
    parser.add_argument("--email", help="Email to login")
    parser.add_argument("--accounts", default="data/accounts.json", help="Path to accounts JSON file")
    parser.add_argument("--noshow", action="store_true", help="Don't show browser cursor")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--xvfb", action="store_true", help="Run browser in Xvfb (virtual display)")
    parser.add_argument("--one-code", action="store_true", help="Find one code and exit")
    
    args = parser.parse_args()

    headless = args.headless
    xvfb_process = None
    if args.xvfb:
        headless = False
        xvfb_process = start_xvfb(251, 300)

    if not os.path.exists("temp"): os.makedirs("temp")
    
    selected = select_account(args.accounts, args.email)
    if selected:
        try:
            run_receiver(selected, show_cursor=not args.noshow, headless=headless, one_code=args.one_code)
        finally:
            if xvfb_process:
                print("[*] Остановка Xvfb...")
                xvfb_process.kill()
