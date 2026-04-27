import os, sys, time, random, json, re, subprocess
# Добавляем корень проекта в sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from playwright.sync_api import sync_playwright
from core.proxy_handler import ProxyManager
from core import proxy_handler as proxy_fetcher
from core import browser_factory as playwright_config
from core.utils import human_delay, load_accounts, get_proxy_info, check_proxy_connectivity

def get_tiktok_code(account, timeout=120, show_cursor=False, headless=True):
    """Вызывает внешний mail_receiver.py для получения одного кода."""
    email = account['email']
    print(f"[*] [Subprocess] Запуск mail_receiver.py для {email}...")
    
    # Путь к mail_receiver.py относительно текущего скрипта
    receiver_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tuta", "mail_receiver.py"))
    accounts_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tuta", "data", "accounts.json"))
    
    cmd = [
        sys.executable, "-u", receiver_path,
        "--email", email,
        "--accounts", accounts_path,
        "--one-code"
    ]
    if not show_cursor: cmd.append("--noshow")
    if headless: cmd.append("--headless")
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        start_t = time.time()
        while time.time() - start_t < timeout:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(f"[MailReceiver] {line.strip()}") # Forwarding output for debugging
                if "CODE_FOUND:" in line:
                    code = line.split("CODE_FOUND:")[1].strip()
                    process.terminate()
                    return code
            else:
                time.sleep(0.1)
        process.terminate()
    except Exception as e:
        print(f"[-] Ошибка при вызове mail_receiver.py: {e}")
    return None

def get_tiktok_code_wrapper(account, queue, timeout, show_cursor, headless):
    code = get_tiktok_code(account, timeout, show_cursor, headless)
    queue.put(code)

# Конфигурация
ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "..", "tuta", "data", "accounts.json")

def register_tiktok(account, show_cursor=True, headless=False):
    email = account['email']
    password = account['password']
    
    print(f"[*] Регистрация TikTok на почту: {email}")
    
    for attempt_idx in range(5):
        proxy_link = proxy_fetcher.get_random_proxy()
        if not proxy_link:
            print("[*] Нет доступных прокси, пытаюсь обновить список...")
            proxy_fetcher.update_proxies_python()
            proxy_link = proxy_fetcher.get_random_proxy()
            
        if not proxy_link:
            print("[-] Нет доступных прокси после обновления.")
            return False
            
        print(f"[*] [Попытка {attempt_idx+1}] Прокси: {proxy_link[:60]}...")
        port = 8000 + random.randint(0, 1000)
        pm = ProxyManager(proxy_link, port)
        if not pm.start():
            print("[-] Прокси не прошел проверку связи. Пробую следующий...")
            continue
            
        try:
            with sync_playwright() as pw:
                browser_config = playwright_config.get_browser_config(headless=headless, port=port)
                proxy_info = get_proxy_info(port)
                context_args, hardware_info = playwright_config.get_context_config(proxy_info)
                
                browser = pw.chromium.launch(**browser_config)
                context = browser.new_context(**context_args)
                stealth_script = playwright_config.get_stealth_script(hardware_info)
                context.add_init_script(stealth_script)
                page, cursor = playwright_config.init_page(context, show_cursor=show_cursor)
                
                print("[*] Переход на TikTok...")
                try:
                    page.goto("https://www.tiktok.com/signup/phone-or-email/email", wait_until="domcontentloaded", timeout=45000)
                    human_delay(2, 4)
                    
                    page_text = page.evaluate("() => document.body.innerText")
                    if "Hong Kong" in page_text and "discontinued" in page_text:
                        print("[-] ОШИБКА: Прокси из Гонконга, TikTok здесь не работает. Скипаю...")
                        browser.close()
                        pm.stop()
                        continue
                except Exception as e:
                    print(f"[-] Ошибка загрузки: {e}")
                    browser.close()
                    pm.stop()
                    continue

                # Куки / Попапы
                try:
                    cookie_btn = page.locator("button").filter(has_text=re.compile("Accept all|Allow all|Zezwól|Принять", re.I)).first
                    if cookie_btn.is_visible():
                        cursor.click(cookie_btn)
                        human_delay(1, 2)
                except: pass

                print("[*] Выбор даты рождения...")
                try:
                    selectors = page.locator("[data-e2e='select-container']").all()
                    if len(selectors) >= 3:
                        for i, (sel, val) in enumerate(zip(selectors, [random.randint(0,11), random.randint(0,27), random.randint(1990,2000)])):
                            cursor.click(sel)
                            human_delay(0.5, 1.2)
                            item_id = f"{['Month','Day','Year'][i]}-options-item-{val if i < 2 else 2024-val}"
                            item = page.locator(f"#{item_id}").first
                            if item.is_visible():
                                cursor.click(item)
                                human_delay(0.5, 1.0)
                except Exception as e:
                    print(f"[-] Ошибка даты рождения: {e}")

                print(f"[*] Ввод Email: {email}")
                email_input = page.locator("input[name='email']").first
                cursor.click(email_input)
                page.keyboard.type(email, delay=random.randint(50, 100))
                
                print("[*] Ввод пароля...")
                pass_input = page.locator("input[type='password']").first
                cursor.click(pass_input)
                page.keyboard.type(password, delay=random.randint(50, 100))
                
                # Галочка согласия
                try:
                    checkbox = page.locator("input[type='checkbox']").first
                    if not checkbox.is_checked():
                        cursor.click(checkbox)
                        human_delay(1, 2)
                except: pass

                # --- Нажатие 'Send code' ---
                code_sent = False
                for try_send in range(3):
                    print(f"[*] Нажимаю 'Send code' (попытка {try_send+1})...")
                    try:
                        send_btn = page.locator("button[data-e2e='send-code-button']").first
                        if not send_btn.is_visible():
                            # Ищем кнопку отправки кода внутри того же контейнера, что и поле ввода кода (независимо от языка)
                            send_btn = page.locator("xpath=//input[@name='code']/ancestor::*[.//button][1]//button").first
                        
                        if send_btn.is_visible():
                            cursor.smooth_scroll_to(send_btn)
                            cursor.click(send_btn)
                            human_delay(5, 8)
                            
                            code_input = page.locator("input[name='code'], input[placeholder*='6-digit']").first
                            btn_text = send_btn.inner_text()
                            
                            if code_input.is_visible() or any(char.isdigit() for char in btn_text) or send_btn.is_disabled():
                                print(f"[+] Код отправлен! (Статус кнопки: {btn_text})")
                                code_sent = True
                                break
                    except: pass
                    page.keyboard.press("Enter")
                    human_delay(3, 5)

                if not code_sent:
                    print("[-] Не удалось отправить код (блок/капча).")
                    browser.close()
                    pm.stop()
                    continue

                # --- Получение кода ---
                from multiprocessing import Process, Queue
                print("[*] Запрашиваю код из почты Tuta...")
                queue = Queue()
                proc = Process(target=get_tiktok_code_wrapper, args=(account, queue, 150, False, True))
                proc.start()
                try:
                    # Ждем максимум 160 секунд (с небольшим запасом от таймаута внутри функции)
                    import queue as q_lib # На всякий случай для исключения
                    code = queue.get(timeout=160)
                except Exception:
                    code = None
                    
                if proc.is_alive():
                    proc.terminate()
                    proc.join()
                else:
                    proc.join()
                
                if not code:
                    print("[-] Код не получен (или истек таймаут).")
                    browser.close()
                    pm.stop()
                    continue
                
                print(f"[+] Код получен: {code}. Ввожу...")
                code_field = page.locator("input[name='code'], input[placeholder*='6-digit']").first
                cursor.click(code_field)
                page.keyboard.type(code, delay=random.randint(100, 200))
                human_delay(2, 4)
                
                # Финиш
                next_btn = page.locator("button[type='submit']").filter(has_text=re.compile("Next|Sign up|Zarejestruj", re.I)).first
                cursor.click(next_btn)
                print("[*] Ожидание регистрации...")
                human_delay(10, 15)
                
                if "signup" not in page.url or page.locator("text=Registration successful").is_visible():
                    print(f"[!!!] УСПЕХ: {email}")
                    return True
                else:
                    print(f"[-] Не удалось завершить. URL: {page.url}")
                    browser.close()
                    pm.stop()

        except Exception as e:
            print(f"[-] Критическая ошибка: {e}")
        finally:
            pm.stop()
    return False

if __name__ == "__main__":
    accounts = load_accounts(ACCOUNTS_FILE)
    if accounts:
        target = accounts[0]
        # Можно передать конкретный email через аргументы, если нужно
        for arg in sys.argv:
            if "@" in arg:
                for a in accounts:
                    if a['email'] == arg:
                        target = a
                        break
        register_tiktok(target, show_cursor=True, headless=False)
