"""
Automated email sender for Tuta accounts.

This script utilizes Playwright and stealth techniques to log into Tuta accounts
and send emails. It supports using proxies, human-like typing delays, and can
process multiple accounts in sequence based on command-line arguments.
"""
import argparse
import sys
import time
import os
# Добавляем корень проекта в sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import random
import re
import requests
import subprocess
import json
import numpy as np
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from core.proxy_handler import ProxyManager
from core.mouse_engine import HumanCursor
from core import browser_factory as playwright_config
from core.utils import human_delay, load_accounts, get_proxy_info, check_proxy_connectivity
from apps.tuta.tuta_utils import check_block, login_to_tuta

# Удалено: PROXY_COMMAND, update_proxies и human_delay перенесены/заменены на core модули

# Удалено: check_block, get_proxy_info и load_accounts перенесены в core модули

def send_tuta_email(username, password, to_address, subject, body, proxy_port=None, show_cursor=False, count=1):
    with sync_playwright() as pw:
        browser_config = playwright_config.get_browser_config(headless=not show_cursor, port=proxy_port)
        browser = pw.chromium.launch(**browser_config)
        
        proxy_info = get_proxy_info(proxy_port) if proxy_port else {"timezone": "UTC", "locale": "en-US"}
        context_args, hardware_info = playwright_config.get_context_config(proxy_info)
        
        context = browser.new_context(**context_args)
        
        stealth_script = playwright_config.get_stealth_script(hardware_info)
        context.add_init_script(stealth_script)
        
        page, cursor = playwright_config.init_page(context, show_cursor=show_cursor)
        
        success_count = 0
        try:
            print(f"[*] [{username}] Вход в Tuta...")
            page.goto("https://app.tuta.com/login", wait_until="domcontentloaded", timeout=90000)
            human_delay(3, 5)
            
            if check_block(page): return 0

            # Ввод данных и логин
            login_to_tuta(page, cursor, username, password)
            
            print(f"[*] [{username}] Ожидание загрузки почты...")
            
            # Ждем появления кнопки "Новое письмо"
            new_mail_btn_selector = "button[title='New email'], button[title='Новое письмо'], button.primary"
            page.wait_for_selector(new_mail_btn_selector, timeout=60000)
            print(f"[+] [{username}] Успешный вход.")
            
            for i in range(count):
                print(f"[*] [{username}] Отправка письма {i+1}/{count}...")
                
                # Кликаем "Новое письмо"
                new_btn = page.locator(new_mail_btn_selector).first
                cursor.click(new_btn)
                human_delay(2, 3)
                
                # Кому
                to_field = page.locator("input[aria-label='To'], input[aria-label='Кому']")
                cursor.click(to_field)
                to_field.press_sequentially(to_address, delay=random.randint(40, 80))
                page.keyboard.press("Enter")
                human_delay(0.5, 1.0)
                
                # Тема
                subj_field = page.locator("input[aria-label='Subject'], input[aria-label='Тема']")
                cursor.click(subj_field)
                subj_field.press_sequentially(subject, delay=random.randint(40, 80))
                human_delay(0.5, 1.0)
                
                # Тело письма
                body_field = page.locator("div[role='textbox']")
                cursor.click(body_field)
                
                # Очистка стандартного текста (Ctrl+A, Delete)
                page.keyboard.press("Control+A")
                page.keyboard.press("Delete")
                human_delay(0.5, 1.0)
                
                body_field.press_sequentially(body, delay=random.randint(20, 50))
                human_delay(1, 2)
                
                # Отправить
                send_btn = page.locator("button[title='Send'], button[title='Отправить']").first
                cursor.click(send_btn)
                
                print(f"[+] [{username}] Письмо {i+1} отправлено. Ждем 30 секунд для проверки...")
                success_count += 1
                human_delay(30, 31) # Длинная задержка для отладки
                
        except Exception as e:
            print(f"[!] [{username}] Ошибка: {e}")
        finally:
            browser.close()
        return success_count

# Удалено: load_accounts перенесен в core.utils

def main():
    example_text = """
Пример использования:
  python mail_sender.py --to example@gmail.com --subject "Hello" --body "My message" --count 2 --accounts-num 5 --show
    """
    parser = argparse.ArgumentParser(
        description="Tuta Email Sender with Full Anti-Bot Protection.",
        epilog=example_text,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--to", required=True, help="Recipient email address")
    parser.add_argument("--subject", default="Hello", help="Email subject")
    parser.add_argument("--body", default="This is a test message.", help="Email body")
    parser.add_argument("--count", type=int, default=1, help="Emails per account")
    parser.add_argument("--accounts", default="data/valid_accounts.json", help="Path to accounts JSON file")
    parser.add_argument("--accounts-num", type=int, default=1, help="Number of accounts from file to use")
    parser.add_argument("--show", action="store_true", help="Show browser and cursor")
    
    args = parser.parse_args()

    accounts_data = load_accounts(args.accounts)
    if not accounts_data:
        print(f"[-] {args.accounts} не найден или пуст.")
        return

    selected_accounts = [(acc["email"], acc["password"]) for acc in accounts_data[:min(len(accounts_data), args.accounts_num)]]
    
    proxy_link = None
    if not os.path.exists("data/proxy_list.txt") or os.stat("data/proxy_list.txt").st_size == 0:
        from core import proxy_handler as pf
        pf.update_proxies_python()
    
    if os.path.exists("data/proxy_list.txt"):
        with open("data/proxy_list.txt", "r") as f:
            links = [l.strip() for l in f if l.strip().startswith(("vless://", "trojan://", "ss://", "vmess://"))]
            if links:
                proxy_link = random.choice(links)
                print(f"[*] Используем случайный прокси: {proxy_link[:40]}...")

    pm = None
    port = random.randint(10000, 20000)
    if proxy_link:
        pm = ProxyManager(proxy_link, port)
        if not pm.start():
            print("[-] Ошибка запуска прокси.")
            pm = None
        else:
            print(f"[+] Прокси запущен на порту {port}")

    total_sent = 0
    try:
        for username, password in selected_accounts:
            sent = send_tuta_email(username, password, args.to, args.subject, args.body, 
                                   proxy_port=port if pm else None, 
                                   show_cursor=args.show, 
                                   count=args.count)
            total_sent += sent
            print(f"[*] Аккаунт {username} завершил работу. Отправлено: {sent}")
    finally:
        if pm:
            pm.stop()
            print("[*] Прокси остановлен.")
    
    print(f"\n[+++] Всего отправлено писем: {total_sent} [+++]")

if __name__ == "__main__":
    if not os.path.exists("temp"): os.makedirs("temp")
    main()
