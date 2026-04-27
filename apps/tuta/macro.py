import time, random, string, requests, os, shutil, re, json
import numpy as np
from scipy.special import comb
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from faker import Faker
from core import captcha_solver as capcha_solver
from core import proxy_handler as proxy
from core.mouse_engine import HumanCursor
from core import browser_factory as playwright_config
from core.utils import human_delay, get_proxy_info, check_proxy_connectivity

fake = Faker('en_US') # Только латиница

def gen_str(min_len=14, max_len=24, include_digits=False, must_include=""):
    # Генерируем основу из имени и фамилии
    base = fake.first_name().lower() + (fake.last_name().lower() if random.random() > 0.3 else str(random.randint(100, 9999)))
    base = re.sub(r'[^a-z0-9]', '', base)
    
    # Буквы, которые ДОЛЖНЫ быть в названии (если переданы)
    required_chars = list(must_include)
    
    # Обрезаем основу ЗАРАНЕЕ, чтобы после вставки обязательных букв не превысить лимит
    allowed_base_len = max_len - len(required_chars)
    if len(base) > allowed_base_len:
        base = base[:allowed_base_len]
        
    res_list = list(base)
    
    # Вставляем нужные буквы в случайные позиции (если есть)
    for char in required_chars:
        pos = random.randint(0, len(res_list))
        res_list.insert(pos, char)
    
    return "".join(res_list)

def gen_password(length=14):
    # Генерация надежного пароля
    chars = string.ascii_letters + string.digits
    pwd = ''.join(random.choices(chars, k=length-3))
    pwd += random.choice(string.digits)
    pwd += random.choice("!@#$%^&*")
    pwd += random.choice(string.ascii_uppercase)
    pwd_list = list(pwd)
    random.shuffle(pwd_list)
    return "".join(pwd_list)

# Удалено: check_block перенесен обратно в приложения (Tuta-specific)
def check_block(page):
    time.sleep(0.2)
    try:
        text = page.locator("body").inner_text().lower()
    except:
        return False
    block_phrases = ["ip address is temporarily blocked", "registration is blocked for this ip", "due to abuse", "access denied", "try again later"]
    for phrase in block_phrases:
        if phrase in text:
            print(f"[-] IP ЗАБЛОКИРОВАН (обнаружено: '{phrase}')")
            return True
    return False

# Удалено: get_proxy_info перенесен в core.utils

# Удалено: check_proxy_connectivity перенесен в core.proxy_handler

import shutil

def run(link, port, save_callback, show_cursor=False, debug_mode=False, headless=False):
    pm = proxy.ProxyManager(link, port)
    if not pm.start():
        print(f"[-] Ошибка парсинга прокси-ссылки.")
        return False
    
    log_path = f"log/session_{port}"
    if debug_mode:
        if os.path.exists(log_path): shutil.rmtree(log_path)
        os.makedirs(log_path, exist_ok=True)

    print(f"[*] Проверка прокси...")
    if not check_proxy_connectivity(port):
        print(f"[-] Прокси не работает (timeout/fail). Пропуск.")
        pm.stop()
        return False # Сигнал для смены прокси

    proxy_info = get_proxy_info(port)
    print(f"[*] Локаль: {proxy_info['locale']}, Таймзона: {proxy_info['timezone']}")

    print(f"[+] Прокси рабочий. Запуск браузера...")
    try:
        with sync_playwright() as pw:
            browser_config = playwright_config.get_browser_config(headless=headless, port=port)
            browser = pw.chromium.launch(**browser_config)
            
            context_args, hardware_info = playwright_config.get_context_config(proxy_info)
            
            # Собираем полную конфигурацию
            full_config = {
                "proxy": link,
                "browser_config": browser_config,
                "context_args": context_args,
                "hardware_info": hardware_info,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            if debug_mode:
                context_args["record_har_path"] = f"{log_path}/network.har"
            
            context = browser.new_context(**context_args)
            
            # Скрипт глубокой подделки Fingerprint (NATIVE LINUX MODE)
            stealth_script = playwright_config.get_stealth_script(hardware_info)
            context.add_init_script(stealth_script)
            
            if debug_mode:
                context.tracing.start(screenshots=True, snapshots=True, sources=True)

            page, cursor = playwright_config.init_page(context, show_cursor=show_cursor)
            
            # Логирование консоли браузера
            if debug_mode:
                page.on("console", lambda msg: open(f"{log_path}/console.log", "a").write(f"[{msg.type}] {msg.text}\n"))
                page.on("request", lambda req: open(f"{log_path}/requests.log", "a").write(f"{req.method} {req.url}\n"))

            print(f"[*] Переход на Tuta...")
            page.goto("https://app.tuta.com/signup", wait_until="domcontentloaded", timeout=90000)
            human_delay(3, 5)

            if check_block(page): return True # Блок - это не ошибка прокси в плане коннекта, но можно считать за фейл

            try:
                print(f"[*] Выбор тарифа Free...")
                page.wait_for_selector('div.flex-space-between:has-text("Free")', timeout=30000)
                free_row = page.locator("div.flex-space-between").filter(has_text="Free").first
                radio = free_row.locator('input[type="radio"]')
                
                # Цикл подтверждения клика по тарифу
                for i in range(10):
                    time.sleep(random.uniform(0.5, 1.5)) # Микро-задумчивость перед выбором
                    cursor.click(radio)
                    time.sleep(0.25)
                    if radio.is_checked():
                        print(f"[*] Тариф Free успешно выбран.")
                        break
                    print(f"[*] Попытка #{i+1} не сработала, кликаем еще раз...")
                
                human_delay(1, 2) # Читаем описание тарифа
                cont_btn = page.get_by_role("button", name="Continue").first
                try:
                    cont_btn.scroll_into_view_if_needed(timeout=5000)
                    cursor.click(cont_btn)
                except Exception as e:
                    print(f"[-] Не удалось нажать Continue: {e}")
                    page.screenshot(path=f"temp/fail_tariff_{port}.png")
                    return True

                human_delay(7, 10) # Читаем "Terms and Conditions" - ВАЖНАЯ ПАУЗА
                
                if check_block(page): return True
                try: 
                    ok_btn = page.get_by_role("button", name="Ok").first
                    if ok_btn.is_visible(timeout=5000): 
                        cursor.click(ok_btn)
                except: pass
                print(f"[*] Тариф подтвержден.")
            except Exception as e:
                if check_block(page): return True
                print(f"[-] Ошибка тарифа: {e}")
                page.screenshot(path=f"temp/fail_tariff_general_{port}.png")
                return True

            username = gen_str(14, 24, include_digits=False)
            password = gen_password(16)
            
            def human_type(locator, text):
                cursor.click(locator)
                for char in text:
                    locator.press(char)
                    time.sleep(random.uniform(0.05, 0.15))
                    if random.random() < 0.1: # Шанс на микро-паузу
                        time.sleep(random.uniform(0.2, 0.5))
                time.sleep(random.uniform(0.3, 0.7))

            try:
                page.wait_for_selector('[data-testid="tfi:username_label"]', timeout=20000)
                print(f"[*] Заполнение формы ({username})...")
                
                u_field = page.get_by_test_id("tfi:username_label")
                human_type(u_field, username)
                
                p_field = page.get_by_test_id("tfi:newPassword_label")
                human_type(p_field, password)
                
                rp_field = page.get_by_test_id("tfi:repeatedPassword_label")
                human_type(rp_field, password)

                for cb in page.locator('input[type="checkbox"]').all():

                    cursor.click(cb)
                    human_delay(0.5, 1.0)
                
                create_btn = page.get_by_test_id("btn:create_new_account_label")
                try: page.wait_for_function("btn => !btn.disabled", create_btn, timeout=15000)
                except: pass

                for retry in range(3):
                    if "Preparing account" in page.content() or page.get_by_test_id("tfi:captcha_input").is_visible(): break
                    cursor.click(create_btn)
                    print(f"[*] Клик 'Create account' (#{retry+1})...")
                    human_delay(4, 6)
                    if check_block(page): return True
                    if "already taken" in page.content(): return True
            except Exception as e:
                if check_block(page): return True
                print(f"[-] Ошибка формы: {e}"); return True

            print(f"[*] Ожидание капчи или финала...")
            # Ждем либо капчу, либо уже код восстановления (если капчу пропустили)
            found_element = None
            for _ in range(30): # 60 секунд ожидания (30 * 2)
                if check_block(page): return True
                
                # Проверяем капчу
                if page.get_by_test_id("tfi:captcha_input").is_visible():
                    found_element = "captcha"
                    break
                # Проверяем код восстановления
                if page.get_by_test_id("monoTextContent").is_visible():
                    found_element = "recovery"
                    break
                
                # Дополнительная проверка на ошибки формы
                error_btn = page.get_by_test_id("btn:ok_action").first
                if error_btn.is_visible():
                    print(f"[-] Обнаружена ошибка при создании: {page.content()[:100]}")
                    return True

                human_delay(1.5, 2.0)

            if found_element == "captcha":
                print(f"[*] Появилась капча. Начинаем решение...")
                for attempt in range(3):
                    captcha_img = None
                    for _ in range(15):
                        for img in page.locator('img').all():
                            src, alt = img.get_attribute('src') or "", img.get_attribute('alt') or ""
                            if "blob:" in src or "captcha" in src.lower() or "captcha" in alt.lower():
                                if img.is_visible(): captcha_img = img; break
                        if captcha_img: break
                        human_delay(0.5, 1.0)
                    
                    if captcha_img:
                        img_p, res_p = f"temp/captcha_images/c_{port}.jpg", f"temp/captcha_images/r_{port}.jpg"
                        captcha_img.screenshot(path=img_p)
                        print(f"[*] Решение капчи (попытка {attempt+1})...")
                        if capcha_solver.process_image(img_p, res_p):
                            ans = capcha_solver.solve_captcha(res_p)
                            print(f"[+] Ответ: {ans}")
                            c_input = page.get_by_test_id("tfi:captcha_input")
                            human_type(c_input, ans)
                            
                            try: 
                                ok_btn = page.get_by_role("button", name="OK").first
                                cursor.click(ok_btn)
                            except: 
                                page.locator('button').filter(has_text="OK").first.click(force=True)
                            
                            human_delay(8, 10)
                            if check_block(page): return True
                            error_btn = page.get_by_test_id("btn:ok_action").first
                            if error_btn.is_visible():
                                if "captcha" in page.content().lower() or "invalid" in page.content().lower():
                                    print(f"[-] Неверная капча, сброс..."); cursor.click(error_btn); human_delay(4, 5); continue
                                else: break
                            else: break
                    else: break
            elif found_element == "recovery":
                print(f"[+] Капча пропущена! Переходим сразу к коду восстановления.")
            else:
                print(f"[-] Не дождались ни капчи, ни кода восстановления.")
                return True

            print(f"[*] Ожидание кода восстановления...")
            recovery_code = "N/A"
            final_success = False
            
            for _ in range(40):
                if page.is_closed(): break
                if page.get_by_test_id("monoTextContent").is_visible():
                    human_delay(2, 3)
                    recovery_code = page.get_by_test_id("monoTextContent").inner_text().replace('\n', ' ').strip()
                    print(f"[+] КОД ВОССТАНОВЛЕНИЯ: {recovery_code}")
                    
                    try:
                        if page.is_closed(): break
                        cb = page.locator('input[type="checkbox"]').first
                        cb.wait_for(state="visible", timeout=15000)
                        cursor.click(cb)
                        human_delay(1, 2)
                        
                        start_btn = page.get_by_test_id("btn:recovery_kit_page_continue_label").first
                        if not start_btn.is_visible():
                            start_btn = page.get_by_role("button", name="Let's get started").first
                        
                        cursor.click(start_btn)
                    except Exception as fe:
                        print(f"[-] Ошибка финализации: {fe}")
                    break
                time.sleep(2)

            if page.is_closed(): return True
            print(f"[*] Проверка интерфейса почты...")
            for _ in range(20):
                if page.is_closed(): break
                if "Sent" in page.content() or "Inbox" in page.content():
                    print(f"[+] ВХОД ПОДТВЕРЖДЕН (вижу Sent/Inbox)!")
                    final_success = True
                    break
                time.sleep(2)

            if final_success:
                try:
                    # Ищем кнопку "Wait for automatic approval" по test-id
                    wait_btn = page.get_by_test_id("btn:waitApprovalButton_action")
                    if wait_btn.is_visible(timeout=5000):
                        print("[*] Найдена кнопка 'Wait for automatic approval', кликаем...")
                        cursor.click(wait_btn)
                        human_delay(2, 3)
                except: pass

                try:
                    # Пытаемся кликнуть по папке Sent в боковом меню
                    sent_link = page.get_by_role("button", name="Sent").first
                    if sent_link.is_visible(timeout=5000):
                        print("[*] Переход в папку Sent...")
                        cursor.click(sent_link)
                        human_delay(2, 3)
                except: pass

                acc_email = username + "@tutamail.com"
                acc = f"{acc_email}:{password}"
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [!!!] АККАУНТ ПОЛНОСТЬЮ ГОТОВ: {acc} КОД ВОССТАНОВЛЕНИЯ: {recovery_code}")
                
                # Сохраняем конфигурацию в файл
                config_filename = f"config_{username}.json"
                config_path = os.path.join("data/configs", config_filename)
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(full_config, f, indent=4, ensure_ascii=False)
                
                save_callback(acc_email, password, recovery_code, config_path)
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Регистрация не завершена (не вошли в почту).")

            human_delay(5, 7)
    except Exception as e: 
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Сбой: {e}")
    finally:
        pm.stop()
    return True
