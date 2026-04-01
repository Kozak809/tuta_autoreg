import time, random, string, requests
import numpy as np
from scipy.special import comb
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import capcha_solver
import proxy

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
]

class HumanCursor:
    def __init__(self, page):
        self.page = page
        self.cur_x, self.cur_y = random.randint(50, 500), random.randint(50, 500)
        self._setup_visual_cursor()

    def _setup_visual_cursor(self):
        """Уберите если вам не нужно смотреть за курсором"""
        script = """
        function ensureCursor() {
            if (!document.getElementById('human-cursor-dot')) {
                const cursor = document.createElement('div');
                cursor.id = 'human-cursor-dot';
                cursor.style.position = 'fixed';
                cursor.style.width = '14px';
                cursor.style.height = '14px';
                cursor.style.backgroundColor = 'red';
                cursor.style.border = '2px solid white';
                cursor.style.borderRadius = '50%';
                cursor.style.zIndex = '9999999';
                cursor.style.pointerEvents = 'none';
                cursor.style.top = '0';
                cursor.style.left = '0';
                cursor.style.boxShadow = '0 0 5px rgba(0,0,0,0.5)';
                document.documentElement.appendChild(cursor);
            }
        }
        window.updateCursor = (x, y) => {
            ensureCursor();
            const cursor = document.getElementById('human-cursor-dot');
            if (cursor) cursor.style.transform = `translate(${x}px, ${y}px)`;
        };
        new MutationObserver(ensureCursor).observe(document.documentElement, {childList: true, subtree: true});
        ensureCursor();
        """
        self.page.add_init_script(script)

    def _bernstein_poly(self, i, n, t):
        return comb(n, i) * (t**i) * (1 - t)**(n - i)

    def _generate_bezier_path(self, x1, y1, x2, y2):
        n_points = max(15, int(np.hypot(x2 - x1, y2 - y1) / 10))
        knots = np.array([
            [x1, y1],
            [x1 + (x2 - x1) * random.random() + random.randint(-150, 150), 
             y1 + (y2 - y1) * random.random() + random.randint(-150, 150)],
            [x2, y2]
        ])
        n = len(knots) - 1
        t = np.linspace(0, 1, n_points)
        path = np.zeros((n_points, 2))
        for i in range(len(knots)):
            path += np.outer(self._bernstein_poly(i, n, t), knots[i])
        return path

    def move_to(self, locator):
        locator.scroll_into_view_if_needed()
        time.sleep(random.uniform(0.1, 0.3))
        
        box = locator.bounding_box()
        if not box:
            time.sleep(0.5)
            box = locator.bounding_box()
            if not box: return False
        
        target_x = box['x'] + box['width'] * random.uniform(0.3, 0.7)
        target_y = box['y'] + box['height'] * random.uniform(0.3, 0.7)
        
        path = self._generate_bezier_path(self.cur_x, self.cur_y, target_x, target_y)
        for x, y in path:
            self.page.mouse.move(x, y)
            try: self.page.evaluate(f"window.updateCursor({x}, {y})")
            except: pass
            time.sleep(random.uniform(0.001, 0.003))
            
        self.cur_x, self.cur_y = target_x, target_y
        return True

    def click(self, locator):
        if self.move_to(locator):
            time.sleep(random.uniform(0.1, 0.2))
            self.page.mouse.down()
            time.sleep(random.uniform(0.05, 0.1))
            self.page.mouse.up()
            time.sleep(random.uniform(0.2, 0.4))
            return True
        return False

def human_delay(min_s=1.5, max_s=4.0):
    time.sleep(random.uniform(min_s, max_s))

def gen_str(min_len=10, max_len=14, include_digits=False, must_include=""):
    length = random.randint(min_len, max_len)
    chars = string.ascii_lowercase
    if include_digits:
        chars += string.digits
    res = ''.join(random.choices(chars, k=length))
    if must_include and must_include not in res:
        pos = random.randint(0, length - len(must_include))
        res = res[:pos] + must_include + res[pos + len(must_include):]
    if not res[0].isalpha():
        res = random.choice(string.ascii_lowercase) + res[1:]
    return res

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

def get_proxy_info(port):
    try:
        proxies = {'http': f'socks5h://127.0.0.1:{port}', 'https': f'socks5h://127.0.0.1:{port}'}
        resp = requests.get("http://ip-api.com/json/?fields=status,timezone,countryCode", proxies=proxies, timeout=10)
        data = resp.json()
        if data.get("status") == "success":
            cc = data.get("countryCode", "US")
            timezone = data.get("timezone", "UTC")
            locale = f"en-{cc}" if cc == "US" else f"{cc.lower()}-{cc}"
            return {"timezone": timezone, "locale": locale}
    except: pass
    return {"timezone": "UTC", "locale": "en-US"}

def check_proxy_connectivity(port, timeout=15):
    try:
        proxies = {'http': f'socks5h://127.0.0.1:{port}', 'https': f'socks5h://127.0.0.1:{port}'}
        resp = requests.get("https://app.tuta.com/", proxies=proxies, timeout=timeout)
        return resp.status_code == 200
    except: return False

def run(link, port, save_callback):
    pm = proxy.ProxyManager(link, port)
    if not pm.start():
        print(f"[-] Ошибка парсинга прокси-ссылки.")
        return
    
    print(f"[*] Проверка прокси...")
    if not check_proxy_connectivity(port):
        print(f"[-] Прокси не работает (timeout/fail). Пропуск.")
        pm.stop()
        return

    proxy_info = get_proxy_info(port)
    print(f"[*] Локаль: {proxy_info['locale']}, Таймзона: {proxy_info['timezone']}")

    print(f"[+] Прокси рабочий. Запуск браузера...")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=False, 
                channel="chrome", 
                proxy={"server": f"socks5://127.0.0.1:{port}"}, 
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=WebRTCPeerConnection",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-position=0,0",
                    "--ignore-certificate-errors",
                    "--ignore-certificate-errors-spki-list",
                ]
            )
            
            vw, vh = random.randint(1200, 1600), random.randint(700, 900)
            ua = random.choice(USER_AGENTS)
            context = browser.new_context(viewport={"width": vw, "height": vh}, user_agent=ua, locale=proxy_info['locale'], timezone_id=proxy_info['timezone'])
            page = context.new_page()
            
            # Активируем визуализацию курсора
            cursor = HumanCursor(page)
            Stealth().apply_stealth_sync(page)
            
            print(f"[*] Переход на Tuta...")
            page.goto("https://app.tuta.com/signup?websiteLang=en", wait_until="domcontentloaded", timeout=90000)
            human_delay(4, 6)

            if check_block(page): return

            try:
                print(f"[*] Выбор тарифа Free...")
                page.wait_for_selector('div.flex-space-between:has-text("Free")', timeout=30000)
                free_row = page.locator("div.flex-space-between").filter(has_text="Free").first
                radio = free_row.locator('input[type="radio"]')
                
                # Цикл подтверждения клика по тарифу
                for i in range(10):
                    cursor.click(radio)
                    time.sleep(0.25)
                    if radio.is_checked():
                        print(f"[*] Тариф Free успешно выбран.")
                        break
                    print(f"[*] Попытка #{i+1} не сработала, кликаем еще раз...")
                
                human_delay(1, 2)
                cont_btn = page.get_by_role("button", name="Continue").first
                cursor.click(cont_btn)
                human_delay(4, 6)
                
                if check_block(page): return
                try: 
                    ok_btn = page.get_by_role("button", name="Ok").first
                    if ok_btn.is_visible(timeout=5000): 
                        cursor.click(ok_btn)
                except: pass
                print(f"[*] Тариф подтвержден.")
            except Exception as e:
                if check_block(page): return
                print(f"[-] Ошибка тарифа: {e}"); return

            username = gen_str(10, 14, include_digits=False, must_include="kozak")
            password = gen_str(12, 16, include_digits=True) + "B2!"
            try:
                page.wait_for_selector('[data-testid="tfi:username_label"]', timeout=20000)
                print(f"[*] Заполнение формы ({username})...")
                
                u_field = page.get_by_test_id("tfi:username_label")
                cursor.click(u_field)
                u_field.fill(username)
                human_delay(1, 2)
                
                p_field = page.get_by_test_id("tfi:newPassword_label")
                cursor.click(p_field)
                p_field.fill(password)
                human_delay(0.5, 1.5)
                
                rp_field = page.get_by_test_id("tfi:repeatedPassword_label")
                cursor.click(rp_field)
                rp_field.fill(password)
                human_delay(1, 2)

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
                    human_delay(5, 8)
                    if check_block(page): return
                    if "already taken" in page.content(): return
            except Exception as e:
                if check_block(page): return
                print(f"[-] Ошибка формы: {e}"); return

            print(f"[*] Ожидание появления капчи...")
            try:
                page.wait_for_selector('[data-testid="tfi:captcha_input"]', timeout=40000)
                human_delay(3, 5)
            except:
                if check_block(page): return
                print(f"[-] Капча не появилась."); return

            for attempt in range(3):
                captcha_img = None
                for _ in range(15):
                    for img in page.locator('img').all():
                        src, alt = img.get_attribute('src') or "", img.get_attribute('alt') or ""
                        if "blob:" in src or "captcha" in src.lower() or "captcha" in alt.lower():
                            if img.is_visible(): captcha_img = img; break
                    if captcha_img: break
                    time.sleep(1)
                
                if captcha_img:
                    img_p, res_p = f"temp/c_{port}.jpg", f"temp/r_{port}.jpg"
                    captcha_img.screenshot(path=img_p)
                    print(f"[*] Решение капчи (попытка {attempt+1})...")
                    if capcha_solver.process_image(img_p, res_p):
                        ans = capcha_solver.solve_captcha(res_p)
                        print(f"[+] Ответ: {ans}")
                        c_input = page.get_by_test_id("tfi:captcha_input")
                        cursor.click(c_input)
                        c_input.fill(ans)
                        human_delay(1, 2)
                        
                        try: 
                            ok_btn = page.get_by_role("button", name="OK").first
                            cursor.click(ok_btn)
                        except: 
                            page.locator('button').filter(has_text="OK").first.click(force=True)
                        
                        human_delay(10, 15)
                        if check_block(page): return
                        error_btn = page.get_by_test_id("btn:ok_action").first
                        if error_btn.is_visible():
                            if "captcha" in page.content().lower() or "invalid" in page.content().lower():
                                print(f"[-] Неверная капча, сброс..."); cursor.click(error_btn); human_delay(4, 6); continue
                            else: break
                        else: break
                else: break

            print(f"[*] Ожидание кода восстановления...")
            recovery_code = "N/A"
            final_success = False
            
            for _ in range(40):
                if page.is_closed(): break
                if page.get_by_test_id("monoTextContent").is_visible():
                    human_delay(2, 3)
                    recovery_code = page.get_by_test_id("monoTextContent").inner_text().replace('\n', ' ').strip()
                    print(f"[!!!] КОД ВОССТАНОВЛЕНИЯ: {recovery_code}")
                    
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

            if page.is_closed(): return
            print(f"[*] Проверка интерфейса почты...")
            for _ in range(20):
                if page.is_closed(): break
                if "Sent" in page.content() or "Inbox" in page.content():
                    print(f"[!!!] ВХОД ПОДТВЕРЖДЕН (вижу Sent/Inbox)!")
                    final_success = True
                    break
                time.sleep(2)

            if final_success:
                acc = f"{username}@tutamail.com:{password}"
                print(f"[!!!] АККАУНТ ПОЛНОСТЬЮ ГОТОВ: {acc}")
                save_callback(username + "@tutamail.com", password, recovery_code)
            else:
                print(f"[-] Регистрация не завершена (не вошли в почту).")

            human_delay(5, 7)
    except Exception as e: print(f"[-] Сбой: {e}")
    finally:
        pm.stop()
