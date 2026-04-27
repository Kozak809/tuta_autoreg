"""
Interactive CLI tool to record browser actions and generate automation scripts.

This script launches a browser instance with a specialized injection script that
records user clicks and inputs. Once the session is closed, it automatically
generates a new Python automation script (e.g., main.py) in a new app directory.
"""
import os
import sys
import json
import time
import random
from playwright.sync_api import sync_playwright

# Добавляем корень проекта в путь
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from core import browser_factory
    from core.proxy_handler import ProxyManager
    from core import proxy_fetcher
    from core.logger import SessionLogger
    print("[DEBUG] Core modules loaded successfully")
except ImportError as e:
    print(f"[ERROR] Failed to load core modules: {e}")
    sys.exit(1)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def start_recording(url, proxy_port=None, debug_mode=False, project_name="recording"):
    recorded_actions = []
    logger = None
    
    with sync_playwright() as p:
        print(f"[DEBUG] Launching browser for URL: {url} (Proxy Port: {proxy_port})...")
        browser_config = browser_factory.get_browser_config(headless=False, port=proxy_port)
        
        browser = p.chromium.launch(**browser_config)
        
        # Если есть прокси, пытаемся получить инфо о нем
        proxy_info = {"timezone": "UTC", "locale": "en-US"}
        if proxy_port:
            try:
                import requests
                proxies = {'http': f'socks5h://127.0.0.1:{proxy_port}', 'https': f'socks5h://127.0.0.1:{proxy_port}'}
                resp = requests.get("http://ip-api.com/json/?fields=status,timezone,countryCode", proxies=proxies, timeout=10)
                data = resp.json()
                if data.get("status") == "success":
                    cc = data.get("countryCode", "US")
                    proxy_info = {"timezone": data.get("timezone", "UTC"), "locale": f"en-{cc}"}
            except: pass

        context_args, hardware_info = browser_factory.get_context_config(proxy_info)
        
        # Настройка логгера
        if debug_mode:
            logger = SessionLogger(f"rec_{project_name}_{int(time.time())}")
            log_dir = logger.prepare()
            context_args["record_har_path"] = os.path.join(log_dir, "network.har")
            print(f"[*] Режим отладки ВКЛЮЧЕН. Логи: {log_dir}")

        context = browser.new_context(**context_args)
        
        if debug_mode:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)

        stealth_script = browser_factory.get_stealth_script(hardware_info)
        context.add_init_script(stealth_script)
        
        page = context.new_page()
        
        if debug_mode:
            logger.setup_page_logging(page)

        print("[DEBUG] Page created and Stealth applied.")

        # Функция для приема данных из браузера
        def log_action(action_type, details):
            recorded_actions.append({"type": action_type, "details": details})
            print(f"\n[REC] {action_type}: {details}", flush=True)

        page.expose_function("recordAction", log_action)

        # Инжектируем скрипт для перехвата событий
        page.add_init_script("""
            console.log("Injected recording script active");
            window.addEventListener('click', e => {
                const target = e.target.closest('button, a, input, [role="button"], div[tabindex]');
                if (!target) return;
                
                const text = target.innerText || target.value || '';
                const label = target.getAttribute('aria-label') || target.getAttribute('placeholder') || target.getAttribute('title') || '';
                const testId = target.getAttribute('data-testid') || target.getAttribute('id');
                const role = target.getAttribute('role');
                const name = target.getAttribute('name');
                
                window.recordAction('CLICK', {
                    text: text.slice(0, 50).trim(),
                    label: label.trim(),
                    testId: testId,
                    tag: target.tagName,
                    role: role,
                    name: name
                });
            }, true);

            window.addEventListener('blur', e => {
                const target = e.target;
                if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
                    const placeholder = target.getAttribute('placeholder') || '';
                    const label = target.getAttribute('aria-label') || '';
                    const testId = target.getAttribute('data-testid') || target.getAttribute('id');
                    
                    window.recordAction('INPUT', {
                        label: placeholder || label || target.name || target.id || 'input',
                        testId: testId,
                        name: target.name,
                        value: target.value
                    });
                }
            }, true);
        """)

        print(f"[*] Переход на {url} (Таймаут 90с)...")
        try:
            # Используем domcontentloaded для скорости и большой таймаут
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
        except Exception as e:
            print(f"[!] Ошибка при загрузке: {e}")
            print("[*] Попробуем подождать еще немного или просто закройте браузер...")

        print("\n" + "="*50)
        print(" ЗАПИСЬ АКТИВНА")
        print(" 1. Делайте клики и вводы в браузере.")
        print(" 2. После каждого клика в этой консоли должен появиться лог [REC].")
        print(" 3. Когда закончите — ЗАКРОЙТЕ ВКЛАДКУ БРАУЗЕРА.")
        print("="*50 + "\n", flush=True)
        
        # Ждем закрытия страницы
        page.wait_for_event("close", timeout=0)
        print("[*] Вкладка закрыта. Завершаю сессию...")
        
        if debug_mode and logger:
            logger.stop_tracing(context)
            print(f"[+] Трейс сохранен в папку логов.")
            
        browser.close()
            
    return recorded_actions

def create_app_structure(name, actions):
    app_dir = os.path.join(BASE_DIR, 'apps', name)
    if os.path.exists(app_dir):
        # Удаляем если уже есть (для перезаписи по просьбе пользователя) или просто предупреждаем
        print(f"[*] Папка {app_dir} уже существует. Обновляю main.py...")
    else:
        os.makedirs(app_dir, exist_ok=True)
        with open(os.path.join(app_dir, '__init__.py'), 'w') as f: pass

    main_path = os.path.join(app_dir, 'main.py')
    with open(main_path, 'w', encoding='utf-8') as f:
        f.write(f"# Бот для {name}\n")
        f.write("import time, random\n\n")
        f.write("def run(page, cursor):\n")
        f.write("    print(f'[*] Запуск сценария {name}...')\n\n")
        
        for action in actions:
            t, d = action['type'], action['details']
            if t == 'CLICK':
                comment = f"    # [КЛИК] {d['tag']} ({d['text'] or d['label'] or d['testId']})"
                f.write(f"{comment}\n")
                
                selector = ""
                if d.get('testId'):
                    # Проверяем, выглядит ли testId как реальный селектор или просто ID
                    if d['testId'].startswith(('btn:', 'tfi:', 'login-')):
                        selector = f"page.get_by_test_id('{d['testId']}')"
                    else:
                        selector = f"page.locator('#{d['testId']}').first"
                elif d.get('label'):
                    selector = f"page.get_by_label('{d['label']}').first"
                elif d.get('text'):
                    clean_text = d['text'].replace('\n', ' ').strip()
                    selector = f"page.get_by_text('{clean_text}', exact=False).first"
                
                if selector:
                    f.write(f"    try:\n")
                    f.write(f"        el = {selector}\n")
                    f.write(f"        if el.is_visible():\n")
                    f.write(f"            cursor.click(el)\n")
                    f.write(f"            time.sleep(random.uniform(0.5, 1.5))\n")
                    f.write(f"    except: pass\n\n")
                else:
                    f.write(f"    # TODO: Не удалось определить селектор для клика\n\n")

            elif t == 'INPUT':
                f.write(f"    # [ВВОД] '{d['value']}' в {d['label']}\n")
                selector = ""
                if d.get('testId'):
                    selector = f"page.get_by_test_id('{d['testId']}')"
                elif d.get('label'):
                    selector = f"page.get_by_placeholder('{d['label']}').first"
                elif d.get('name'):
                    selector = f"page.locator('input[name=\"{d['name']}\"]').first"
                
                if selector:
                    f.write(f"    try:\n")
                    f.write(f"        el = {selector}\n")
                    f.write(f"        if el.is_visible():\n")
                    f.write(f"            cursor.click(el)\n")
                    f.write(f"            page.keyboard.type('{d['value']}', delay=random.randint(40, 90))\n")
                    f.write(f"            time.sleep(random.uniform(0.3, 0.8))\n")
                    f.write(f"    except: pass\n\n")
        
        f.write("    print('[+] Сценарий завершен.')\n")
    return True

def main():
    print("\n--- Рекордер v2.1 (с прокси) ---", flush=True)
    try:
        project_name = input("Название проекта: ").strip().lower()
        url = input("URL сайта: ").strip()
        if not url.startswith("http"): url = "https://" + url

        use_proxy = input("Использовать прокси? (y/n): ").lower() == 'y'
        debug_mode = input("Включить режим отладки (логи + трейс)? (y/n): ").lower() == 'y'
        
        pm = None
        proxy_port = None
        
        if use_proxy:
            # Приоритет: приватные прокси из proxy.txt в корне проекта
            private_proxy_file = "proxy.txt"
            proxy_link = None
            
            if os.path.exists(private_proxy_file):
                try:
                    with open(private_proxy_file, "r", encoding="utf-8") as f:
                        p_links = [l.strip() for l in f if l.strip().startswith(("vless://", "trojan://", "ss://", "vmess://"))]
                        if p_links:
                            proxy_link = random.choice(p_links)
                            print(f"[*] Взят приватный прокси из {private_proxy_file}")
                except Exception as e:
                    print(f"[-] Ошибка при чтении {private_proxy_file}: {e}")

            if not proxy_link:
                proxy_link = proxy_fetcher.get_random_proxy()
                if not proxy_link:
                    print("[!] Прокси не найдены в data/proxy_list.txt, обновляю...")
                    links = proxy_fetcher.update_proxies_python()
                    if links: proxy_link = random.choice(links)
            
            if proxy_link:
                proxy_port = random.randint(15000, 25000)
                pm = ProxyManager(proxy_link, proxy_port)
                print(f"[*] Запуск прокси на порту {proxy_port}...")
                if not pm.start():
                    print("[-] Ошибка запуска прокси. Используем реальный IP.")
                    proxy_port = None
                    pm = None
            else:
                print("[-] Не удалось получить прокси. Используем реальный IP.")

        actions = start_recording(url, proxy_port=proxy_port, debug_mode=debug_mode, project_name=project_name)
        
        if pm: pm.stop()

        if actions:
            print(f"\n[+] Записано действий: {len(actions)}")
            if create_app_structure(project_name, actions):
                print(f"[+++] Готово! Проверьте apps/{project_name}/main.py")
        else:
            print("[-] Действий не записано.")
    except KeyboardInterrupt:
        print("\n[!] Прервано пользователем.")

if __name__ == "__main__":
    main()
