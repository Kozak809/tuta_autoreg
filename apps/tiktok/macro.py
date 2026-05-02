"""
Auto-generated macro for: tiktok
URL: https://www.tiktok.com/signup/phone-or-email/phone
Generated at: 2026-05-01 16:20:21

Usage:
    from apps.tiktok.main import run
    run(link, port, save_callback, show_cursor=False, debug_mode=False, headless=False)
"""
import os
import sys
import time
import random
import json
import threading
import queue
import subprocess
import string

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from core import browser_factory
from core.proxy_handler import ProxyManager
from core.utils import human_delay, get_proxy_info, check_proxy_connectivity
from core.logger import SessionLogger



# ── entry point ──────────────────────────────────────────────────────────────

def run(link, port, save_callback=None, show_cursor=False, debug_mode=False, headless=False):
    """
    :param link:          Proxy URI string (vless://, trojan://, ss://, etc.)
    :param port:          Local SOCKS port for the sing-box tunnel
    :param save_callback: Optional callable(email, password, code, path) to persist account data
    :param show_cursor:   Render a red dot to visualise mouse movement
    :param debug_mode:    Save HAR + Playwright trace to logs/sessions/
    :param headless:      Run browser without visible window
    :returns: True on success, False on failure
    """
    # ── pick account ─────────────────────────────────────────────────────────
    accounts_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'accounts.json'))
    tiktok_accounts_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'accounts_tiktok.json'))
    
    # Получаем уже зарегистрированные email'ы
    registered_emails = set()
    try:
        if os.path.exists(tiktok_accounts_path):
            with open(tiktok_accounts_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        registered_emails.add(data.get("email"))
    except Exception:
        pass

    try:
        with open(accounts_path, 'r', encoding='utf-8') as f:
            accounts_data = [json.loads(line) for line in f if line.strip()]
        
        # Фильтруем: берем валидные и те, которых еще нет в базе TikTok
        valid_accounts = [acc for acc in accounts_data if acc.get('isvalid') == 'VALID' and acc.get('email') not in registered_emails]
        
        if not valid_accounts:
            print("[-] Нет доступных аккаунтов (все валидные уже зарегистрированы в TikTok).")
            return "NO_ACCOUNTS"
            
        # Берем ПЕРВЫЙ аккаунт по порядку (а не рандомно)
        account = valid_accounts[0]
    except Exception as e:
        print(f"[-] Ошибка загрузки аккаунтов: {e}")
        return False

    email = account['email']
    # Generate random strong password for TikTok (must contain letter, number, and special char)
    letter = random.choice(string.ascii_letters)
    number = random.choice(string.digits)
    special = random.choice("!@#$%^&*")
    all_chars = string.ascii_letters + string.digits + "!@#$%^&*"
    rest = [random.choice(all_chars) for _ in range(13)]
    pwd_list = [letter, number, special] + rest
    random.shuffle(pwd_list)
    password = ''.join(pwd_list)
    
    print(f"[*] Используем аккаунт: {email}")

    # в code_queue складываются коды из tuta
    code_queue = queue.Queue()
    receiver_script = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tuta', 'receiver.py'))
    cmd = [sys.executable, receiver_script, "--email", email, "--one-code", "--headless"]
    
    def read_stdout(proc):
        for line in iter(proc.stdout.readline, ''):
            if not line:
                break
            # print(f"[Tuta] {line.strip()}")
            if "CODE_FOUND:" in line:
                code_queue.put(line.split("CODE_FOUND:")[1].strip())

    print(f"[*] Запускаем фоновый получатель почты для {email}...")
    receiver_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    t = threading.Thread(target=read_stdout, args=(receiver_proc,), daemon=True)
    t.start()

    # ── start proxy tunnel ───────────────────────────────────────────────────
    pm = ProxyManager(link, port)
    if not pm.start():
        print(f"[-] Ошибка запуска прокси-туннеля на порту {port}.")
        receiver_proc.terminate()
        return False

    # ── check connectivity ───────────────────────────────────────────────────
    print(f"[*] Проверка подключения к прокси на порту {port}...")
    if not check_proxy_connectivity(port):
        print("[-] Прокси недоступен. Пропускаем.")
        pm.stop()
        return False

    proxy_info = get_proxy_info(port)
    print(f"[+] Прокси работает — таймзона: {proxy_info.get('timezone')}, локаль: {proxy_info.get('locale')}")

    # ── optional debug logger ────────────────────────────────────────────────
    logger = None
    log_path = None
    if debug_mode:
        logger = SessionLogger(f"{int(time.time())}_port{port}")
        log_path = logger.prepare()
        print(f"[*] Режим отладки — логи в: {log_path}")

    try:
        with sync_playwright() as pw:
            browser_config = browser_factory.get_browser_config(headless=headless, port=port)
            context_config, hardware_info = browser_factory.get_context_config(proxy_info=proxy_info)
            if debug_mode and log_path:
                context_config["record_har_path"] = os.path.join(log_path, "network.har")

            full_config = {
                "proxy": link,
                "browser_config": browser_config,
                "context_args": context_config,
                "hardware_info": hardware_info,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            browser = pw.chromium.launch(**browser_config)
            context = browser.new_context(**context_config)
            context.add_init_script(browser_factory.get_stealth_script(hardware_info))
            page, cursor = browser_factory.init_page(context, show_cursor=show_cursor)

            if debug_mode:
                context.tracing.start(screenshots=True, snapshots=True, sources=True)
            if debug_mode and logger:
                logger.setup_page_logging(page)

            # ── Navigation to Signup via Homepage ─────────────────────────────
            print(f"[*] Переход на главную страницу TikTok...")
            try:
                # Даем 30 секунд на первичную загрузку DOM
                page.goto("https://www.tiktok.com/", wait_until="domcontentloaded", timeout=30000)
            except Exception:
                print("[-] Страница не загрузилась за 30 секунд. Пропускаем.")
                return False

            # Проверяем наличие любого контента (тег body)
            if not page.locator('body').is_visible():
                print("[-] Контент не обнаружен. Скип.")
                return False
            
            print("[*] Контент есть, ожидаем окончательную загрузку (до 2 мин)...")
            try:
                # Если контент пошел, расширяем таймер до 2 минут для медленных прокси
                page.wait_for_load_state("networkidle", timeout=120000)
            except Exception:
                print("[!] Превышено время ожидания networkidle, но продолжаем...")
            
            human_delay(1, 3)

            # 1. Принять куки
            try:
                _banner = page.locator('.tiktok-cookie-banner, [class*="cookie-banner"]').first
                if _banner.is_visible(timeout=3000):
                    print("[*] Убираем куки...")
                    _allow_btn = _banner.locator('button').last
                    cursor.click(_allow_btn)
                    human_delay(1, 2)
            except: pass

            # 2. Баннер GDPR
            try:
                _gdpr = page.locator('div[role="alert"]').first
                if _gdpr.is_visible(timeout=3000):
                    print("[*] Убираем GDPR баннер")
                    # Ищем основную (primary) кнопку в баннере
                    _btn = _gdpr.locator('button[class*="primary"], button[class*="Primary"]').first
                    if _btn.is_visible(timeout=2000):
                        cursor.click(_btn)
                        human_delay(1, 2)
            except: pass

            # 3. Клик по кнопке входа (Log in)
            try:
                print("[*] Поиск кнопки входа")
                _login_btn = page.locator('#header-login-button:visible, [data-e2e="top-login-button"]:visible').first
                
                if not _login_btn.is_visible(timeout=5000):
                    print("[*] Кнопка скрыта, пробуем прокрутку для активации...")
                    page.evaluate("window.scrollBy(0, 100);")
                    human_delay(0.5, 1)
                    page.evaluate("window.scrollBy(0, -100);")
                    human_delay(0.5, 1)
                
                if _login_btn.is_visible(timeout=5000):
                    print("[*] Нажимаем кнопку Log in...")
                    cursor.click(_login_btn)
                    human_delay(2, 4)
                else:
                    # Последняя попытка: кликнуть по любому элементу с таким ID, даже если Playwright считает его скрытым
                    print("[!] Видимая кнопка не найдена, пробуем принудительный клик...")
                    _any_btn = page.locator('#header-login-button').first
                    if _any_btn.count() > 0:
                        cursor.click(_any_btn) # cursor.click использует координаты, может сработать
                        human_delay(2, 4)
                    else:
                        print("[-] Кнопка входа не найдена.")
                        return False
            except Exception as e:
                print(f"[-] Ошибка клика по кнопке: {e}")
                return False

            # 4. Переход к регистрации (Sign up)
            try:
                # Ссылка "Sign up" внизу модального окна (языконезависимо через data-e2e)
                _signup_link = page.locator('[data-e2e="bottom-sign-up"]').first
                if _signup_link.is_visible(timeout=5000):
                    print("[*] Переходим к регистрации...")
                    cursor.click(_signup_link)
                    human_delay(1.5, 2.5)
            except Exception as e:
                print(f"[-] Ошибка перехода к Sign up: {e}")

            # 5. Выбор метода (Phone or Email)
            try:
                # Метод "Use phone or email" (первый в списке channel-item)
                _method = page.locator('[data-e2e="channel-item"]').first
                if _method.is_visible(timeout=5000):
                    print("[*] Выбираем метод регистрации...")
                    cursor.click(_method)
                    human_delay(2, 4)
            except Exception as e:
                print(f"[-] Ошибка выбора метода: {e}")

            # 6. Заполнение даты рождения (языконезависимо по структуре)
            try:
                print("[*] Заполняем дату рождения...")
                
                # Месяц
                _m = page.locator('[data-e2e="select-container"]').nth(0)
                cursor.click(_m) # Используем человеческий клик
                human_delay(1.5, 2.5)
                # Выбираем случайный месяц через ID
                _m_opt = page.locator(f'[id*="Month-options-item-{random.randint(0, 11)}"]').first
                cursor.click(_m_opt)
                human_delay(1, 1.5)

                # День
                _d = page.locator('[data-e2e="select-container"]').nth(1)
                cursor.click(_d)
                human_delay(1.5, 2.5)
                # Выбираем случайный день (до 28) через ID
                _d_opt = page.locator(f'[id*="Day-options-item-{random.randint(0, 27)}"]').first
                cursor.click(_d_opt)
                human_delay(1, 1.5)

                # Год
                _y = page.locator('[data-e2e="select-container"]').nth(2)
                cursor.click(_y)
                human_delay(1.5, 2.5)
                # Для года ищем по тексту внутри контейнера лет
                _year_val = str(random.randint(1990, 2005))
                _y_opt = page.locator(f'[id*="Year-options-item-"]:has-text("{_year_val}")').first
                cursor.click(_y_opt)
                human_delay(1.5, 2.5)
            except Exception as e:
                print(f"[-] Ошибка даты рождения: {e}")

            # 7. Переключение на Email
            try:
                # Ссылка "Sign up with email"
                _email_switch = page.locator('a[href*="email"]').first
                if _email_switch.is_visible(timeout=5000):
                    cursor.click(_email_switch)
                    human_delay(1.5, 2.5)
            except: pass

            # 8. Email и Пароль
            try:
                # Поле Email
                _email_input = page.locator('input[name="email"], [data-e2e="email-input"]').first
                if _email_input.is_visible(timeout=5000):
                    cursor.click(_email_input)
                    _email_input.fill("")
                    page.keyboard.type(email, delay=random.randint(50, 100))
                    human_delay(0.5, 1)

                # Поле Пароль
                _pass_input = page.locator('input[type="password"]').first
                if _pass_input.is_visible(timeout=5000):
                    cursor.click(_pass_input)
                    _pass_input.fill("")
                    page.keyboard.type(password, delay=random.randint(50, 100))
                    human_delay(0.8, 1.5)
            except Exception as e:
                print(f"[-] Ошибка ввода данных: {e}")

            # 9. Согласие и Отправка кода
            try:
                # Чекбокс согласия (может быть скрыт, кликаем по label или самому input)
                _consent = page.locator('label[class*="LabelCheck"], input[type="checkbox"]').first
                if _consent.is_visible(timeout=3000):
                    cursor.click(_consent)
                    human_delay(0.4, 0.7)

                # Кнопка "Send code"
                _send_btn = page.locator('button[data-e2e="send-code-button"]').first
                if _send_btn.is_visible(timeout=5000):
                    cursor.click(_send_btn)
                    print("[+] Код запрошен. Проверка на ошибки...")
                    human_delay(2, 4)

                    # 1. Проверка на лимит попыток (Rate Limit)
                    _error_toast = page.locator('[role="status"], [class*="toast"], [class*="error"]').first
                    _rate_limit_texts = ["Maximum number of attempts", "Too many attempts", "Try again later", "S\u043bшком много попыток"]
                    for text in _rate_limit_texts:
                        if page.get_by_text(text, exact=False).first.is_visible(timeout=500):
                            print(f"[-] ОБНАРУЖЕН ЛИМИТ: {text}. Нужна смена прокси.")
                            return False

                    # 2. Проверка "Аккаунт уже существует"
                    if page.get_by_text("Already signed up", exact=False).first.is_visible(timeout=500):
                        print("[-] Этот Email уже зарегистрирован в TikTok.")
                        if save_callback:
                            save_callback(email, password, config_path="N/A", note="ALREADY_REGISTERED")
                        return False

                    print("[+] Ошибок не обнаружено, продолжаем.")
            except Exception as e:
                print(f"[-] Ошибка на этапе отправки кода: {e}")

            # 10. Ввод кода подтверждения
            try:
                print("[*] Ожидаем код из очереди...")
                code = code_queue.get(timeout=180)
                print(f"[+] Код получен: {code}")
                
                _code_input = page.locator('input[data-e2e="code-input"], input[maxlength="6"]').first
                if _code_input.is_visible(timeout=10000):
                    cursor.click(_code_input)
                    page.keyboard.type(code, delay=random.randint(40, 80))
                    human_delay(1, 2)
                    
                    _next_btn = page.locator('button[data-e2e="signup-btn"], button[type="submit"]').first
                    if _next_btn.is_visible(timeout=5000):
                        _next_btn.wait_for(state="enabled", timeout=10000)
                        cursor.click(_next_btn)
                        human_delay(4, 8)
            except Exception as e:
                print(f"[-] Ошибка при вводе кода: {e}")

            # 11. Финальная проверка и сохранение аккаунта
            print("[*] Проверка успешной регистрации...")
            final_success = False
            for _ in range(20):
                if page.is_closed(): break
                if page.locator('[data-e2e="profile-icon"]').first.is_visible():
                    print("[+] РЕГИСТРАЦИЯ ПОДТВЕРЖДЕНА!")
                    final_success = True
                    break
                time.sleep(2)

            if final_success:
                try:
                    full_config["storage_state"] = context.storage_state()
                except: pass
                username = email.split('@')[0]
                config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "configs_tiktok", f"config_{username}.json"))
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(full_config, f, indent=4, ensure_ascii=False)
                if save_callback:
                    save_callback(email, password, config_path=f"data/configs_tiktok/config_{username}.json")
                print(f"[+++] АККАУНТ СОХРАНЕН: {email}")

    except Exception as exc:
        print(f"[-] Ошибка во время выполнения: {exc}")
        return False
    finally:
        if debug_mode and logger:
            logger.stop_tracing(context)
            print(f"[+] Трассировка сохранена → {log_path}")
        pm.stop()
        if 'receiver_proc' in locals() and receiver_proc.poll() is None:
            receiver_proc.terminate()

    return True

