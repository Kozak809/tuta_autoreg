import os
import time
import json
import random
import re
import subprocess
from core.utils import human_delay

def resolve_config_path(config_path):
    """
    Разрешает путь к файлу конфигурации аккаунта, пробуя несколько вариантов.
    Возвращает (parsed_json, real_path) или (None, None).
    """
    if not config_path:
        return None, None
        
    possible_paths = [
        config_path, 
        os.path.join(os.path.dirname(__file__), config_path),
        os.path.join("apps", "tuta", config_path),
        os.path.join(os.path.dirname(__file__), "..", "..", config_path)
    ]
    for cp in possible_paths:
        if os.path.exists(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    return json.load(f), cp
            except: pass
    return None, None

def start_xvfb(start_port=99, end_port=300):
    """
    Ищет свободный дисплей и запускает Xvfb.
    Возвращает объект процесса (или None) и устанавливает os.environ["DISPLAY"].
    """
    for display in range(start_port, end_port + 1):
        if not os.path.exists(f"/tmp/.X11-unix/X{display}"):
            print(f"[*] Запускаем Xvfb на дисплее :{display}...")
            xvfb_process = subprocess.Popen(
                ["Xvfb", f":{display}", "-screen", "0", "1920x1080x24", "-ac", "+extension", "RANDR"], 
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            os.environ["DISPLAY"] = f":{display}"
            time.sleep(2)
            return xvfb_process
    print("[-] Не удалось найти свободный дисплей для Xvfb.")
    return None

def check_block(page):
    """
    Проверяет, заблокирован ли IP на странице регистрации/входа.
    """
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

def check_tuta_errors(page):
    """
    Проверка на критические ошибки на странице входа/почты. 
    Возвращает (status, is_critical).
    status: "INVALID", "BANNED", "CONNECTION_LOST", "IP_BLOCKED" или None.
    """
    try:
        body_text = page.evaluate("() => document.body.innerText")
        
        # 1. Неверный логин
        invalid_texts = ["Invalid login credentials", "Неверные данные для входа", "Date de autentificare incorecte"]
        if any(msg in body_text for msg in invalid_texts):
            return "INVALID", True
            
        # 2. Аккаунт забанен/отключен
        ban_phrases = ["Your account has been disabled", "Your account is temporarily locked", "Account disabled", "Аккаунт заблокирован"]
        if any(phrase in body_text for phrase in ban_phrases):
            return "BANNED", True
            
        # 3. Потеря соединения
        lost_conn_texts = ["The connection to the server was lost", "Соединение с сервером потеряно"]
        if any(msg in body_text for msg in lost_conn_texts):
            return "CONNECTION_LOST", False
            
        # 4. IP Блок
        block_phrases = ["ip address is temporarily blocked", "registration is blocked for this ip", "due to abuse", "access denied"]
        if any(phrase in body_text.lower() for phrase in block_phrases):
            return "IP_BLOCKED", False

    except: pass
    return None, False

def login_to_tuta(page, cursor, email, password, timeout=60000):
    """
    Универсальная функция ввода логина и пароля на странице Tuta.
    """
    try:
        page.wait_for_selector("input[type='email'], [data-testid='tfi:username']", timeout=timeout)
    except: pass

    # Поиск поля почты
    u_field = page.locator("input[type='email']").first
    if not u_field.is_visible():
        u_field = page.get_by_test_id("tfi:username").locator("input").first
    if not u_field.is_visible():
        u_field = page.get_by_test_id("tfi:username_label")
    
    if u_field.is_visible():
        cursor.click(u_field)
        human_delay(0.2, 0.5)
        page.keyboard.type(email, delay=random.randint(50, 120))
        human_delay(0.5, 0.8)
    
    # Поиск поля пароля
    p_field = page.locator("input[type='password']").first
    if not p_field.is_visible():
        p_field = page.get_by_test_id("tfi:password").locator("input").first
    if not p_field.is_visible():
        p_field = page.get_by_test_id("tfi:password_label")
    
    if p_field.is_visible():
        cursor.click(p_field)
        human_delay(0.2, 0.5)
        page.keyboard.type(password, delay=random.randint(50, 120))
        human_delay(0.6, 1.0)
    
    # Клик по чекбоксу "Запомнить меня"
    try:
        checkbox = page.locator("input.checkbox.list-checkbox.click").first
        if checkbox.is_visible():
            cursor.click(checkbox)
            human_delay(0.4, 0.7)
    except: pass
    
    # Нажимаем Login
    login_btn = page.get_by_test_id("btn:login_action")
    if not login_btn.is_visible():
        login_btn = page.locator("button[type='submit']").first
    if not login_btn.is_visible():
        login_btn = page.locator("button").filter(has_text=re.compile("Log in|Войти", re.IGNORECASE)).first
    
    if login_btn.is_visible():
        cursor.click(login_btn)
    
    human_delay(1.5, 2.5)
    # Fallback: если кнопка все еще видна или url не изменился, жмем Enter
    if page.url.endswith("/login") and login_btn.is_visible():
        page.keyboard.press("Enter")
