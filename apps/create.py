"""
This script provides an interactive CLI macro recorder for browser automation.
It launches a stealthy Chromium browser, injects a JavaScript event listener to
capture user interactions (such as clicks, inputs, selections, and navigation),
and automatically generates a Python automation script based on the recorded actions.
The generated script utilizes Playwright and a custom stealth core framework
for executing the recorded sequence.
"""
import os
import sys
import json
import time
import random
import textwrap

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from core import browser_factory
    from core.proxy_handler import ProxyManager, get_random_proxy
    from core.utils import get_proxy_info, check_proxy_connectivity, PROJECT_ROOT
    from core.logger import SessionLogger
except ImportError as exc:
    print(f"[ERROR] Failed to import core modules: {exc}")
    sys.exit(1)

_RECORDER_JS = r"""
(function () {
  if (window.__recorderActive) return;
  window.__recorderActive = true;

  function sig(el) {
    if (!el || el.nodeType !== 1) return null;
    const norm = s => s ? s.replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').trim() : null;
    const cls = el.className && typeof el.className === 'string'
              ? el.className.replace(/\s+/g, ' ').trim() : null;
    return {
      tag:         el.tagName,
      id:          el.id                                   || null,
      name:        el.getAttribute('name')                 || null,
      type:        el.getAttribute('type')                 || null,
      role:        el.getAttribute('role')                 || null,
      testId:      el.getAttribute('data-testid')          || null,
      ariaLabel:   norm(el.getAttribute('aria-label')),
      placeholder: norm(el.getAttribute('placeholder')),
      title:       norm(el.getAttribute('title')),
      text:        norm((el.innerText || el.value || '').slice(0, 120)),
      href:        el.getAttribute('href')                 || null,
      value:       el.value != null ? el.value             : null,
      checked:     el.checked != null ? el.checked         : null,
      cssClass:    cls                                     || null,
    };
  }

  function send(type, s) {
    if (!s) return;
    try { window.recordAction(type, s); } catch(e) {}
  }

  document.addEventListener('click', function (e) {
    const el = e.target.closest(
      'button, a, input[type="button"], input[type="submit"], input[type="reset"],' +
      'input[type="checkbox"], input[type="radio"], select,' +
      '[role="button"], [role="link"], [role="menuitem"], [role="option"],' +
      '[role="tab"], [role="switch"], [role="checkbox"], [role="radio"],' +
      '[tabindex]:not([tabindex="-1"]), label'
    );
    if (!el) return;
    const s = sig(el);
    if (!s) return;

    if (el.type === 'checkbox' || el.type === 'radio') {
      send('CHECK', { ...s, checked: el.checked });
      return;
    }
    send('CLICK', s);
  }, true);

  document.addEventListener('change', function (e) {
    const el = e.target;
    if (el.tagName === 'SELECT') {
      send('SELECT', { ...sig(el), value: el.value, options: [...el.options].map(o => o.value) });
    } else if (el.type === 'checkbox' || el.type === 'radio') {
      send('CHECK', { ...sig(el), checked: el.checked });
    }
  }, true);

  document.addEventListener('blur', function (e) {
    const el = e.target;
    if (el.tagName === 'INPUT' && !['button','submit','reset','checkbox','radio','file'].includes(el.type)) {
      const val = el.value.trim();
      if (val) send('INPUT', { ...sig(el), value: val });
    } else if (el.tagName === 'TEXTAREA') {
      const val = el.value.trim();
      if (val) send('INPUT', { ...sig(el), value: val });
    }
  }, true);

  let _lastHref = location.href;
  setInterval(function () {
    if (location.href !== _lastHref) {
      send('NAVIGATE', { url: location.href });
      _lastHref = location.href;
    }
  }, 800);

  document.addEventListener('keydown', function (e) {
    const TRACKED = ['Enter', 'Escape', 'Tab', 'ArrowDown', 'ArrowUp', 'F5'];
    if (!TRACKED.includes(e.key)) return;
    const el = e.target;
    send('KEY', { key: e.key, ...sig(el) });
  }, true);

})();
"""

def _is_empty_element(d):
    return not any([
        d.get("id"), d.get("testId"), d.get("ariaLabel"),
        d.get("placeholder"), d.get("name"), d.get("title"),
        (d.get("text") or "").strip(),
        d.get("role"),
    ])

def _same_element(a, b):
    for key in ("testId", "id", "name", "ariaLabel"):
        if a.get(key) and a[key] == b.get(key):
            return True
    if a.get("text") and a["text"] == b.get("text") and a["text"].strip():
        return True
    return False

def _clean_actions(raw):
    out = []
    for i, a in enumerate(raw):
        t, d = a["type"], a["details"]

        if t == "INPUT" and not (d.get("value") or "").strip():
            continue

        if t == "CLICK" and _is_empty_element(d) and not d.get("cssClass"):
            continue

        if t == "CLICK" and out and out[-1]["type"] == "CLICK":
            if _same_element(out[-1]["details"], d):
                continue

        if t == "CHECK" and out and out[-1]["type"] == "CHECK":
            if _same_element(out[-1]["details"], d):
                out[-1] = a
                continue

        if t == "CLICK" and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt["type"] == "INPUT":
                if _same_element(d, nxt["details"]):
                    continue

        if t == "NAVIGATE" and out and out[-1]["type"] == "CLICK":
            a = {"type": "WAIT_NAV", "details": d}

        out.append(a)
    return out

def _best_selector(d, for_input=False):
    tag = (d.get("tag") or "").upper()

    if d.get("testId"):
        return f"page.get_by_test_id('{_esc(d['testId'])}')"

    if d.get("id"):
        return f"page.locator('#{_esc(d['id'])}').first"

    if d.get("ariaLabel"):
        return f"page.get_by_label('{_esc(d['ariaLabel'])}').first"

    if for_input and d.get("placeholder"):
        return f"page.get_by_placeholder('{_esc(d['placeholder'])}').first"

    if d.get("name"):
        lo = tag.lower() if tag else "input"
        return f"page.locator('{lo}[name=\"{_esc(d['name'])}\"]').first"

    role = d.get("role") or ""
    text = (d.get("text") or "").strip()

    if role and text:
        return f"page.get_by_role('{_esc(role)}', name='{_esc(text)}').first"

    if text and len(text) <= 80:
        return f"page.get_by_text('{_esc(text)}', exact=False).first"

    if d.get("cssClass"):
        lo = tag.lower() if tag else "*"
        classes = [c for c in d["cssClass"].split() if len(c) > 2]
        if classes:
            css_sel = f"{lo}.{'.'.join(classes[:2])}"
            return f"page.locator('{_esc(css_sel)}').first"

    return None

def _esc(s):
    return str(s).replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ").replace("\r", "")

_SCRIPT_TEMPLATE = '''\
"""
Auto-generated macro for: {name}
URL: {url}
Generated at: {ts}

Usage:
    from apps.{name}.main import run
    run(link, port, save_callback, show_cursor=False, debug_mode=False, headless=False)
"""
import os
import sys
import time
import random
import shutil

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core import browser_factory
from core.proxy_handler import ProxyManager
from core.utils import human_delay, get_proxy_info, check_proxy_connectivity
from core.mouse_engine import HumanCursor
from core.logger import SessionLogger

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
    pm = ProxyManager(link, port)
    if not pm.start():
        print(f"[-] Failed to start proxy tunnel on port {{port}}.")
        return False

    print(f"[*] Checking proxy connectivity on port {{port}}...")
    if not check_proxy_connectivity(port):
        print("[-] Proxy is not reachable. Skipping.")
        pm.stop()
        return False

    proxy_info = get_proxy_info(port)
    print(f"[+] Proxy OK — timezone: {{proxy_info.get('timezone')}}, locale: {{proxy_info.get('locale')}}")

    logger = None
    log_path = None
    if debug_mode:
        logger = SessionLogger(f"{{int(time.time())}}_port{{port}}")
        log_path = logger.prepare()
        print(f"[*] Debug mode — logs: {{log_path}}")

    try:
        with sync_playwright() as pw:
            browser_config = browser_factory.get_browser_config(headless=headless, port=port)
            browser = pw.chromium.launch(**browser_config)

            context_args, hardware_info = browser_factory.get_context_config(proxy_info)
            if debug_mode and log_path:
                context_args["record_har_path"] = os.path.join(log_path, "network.har")

            context = browser.new_context(**context_args)

            if debug_mode:
                context.tracing.start(screenshots=True, snapshots=True, sources=True)

            stealth_script = browser_factory.get_stealth_script(hardware_info)
            context.add_init_script(stealth_script)

            page, cursor = browser_factory.init_page(context, show_cursor=show_cursor)

            if debug_mode and logger:
                logger.setup_page_logging(page)

            print(f"[*] Navigating to {url}...")
            page.goto("{url}", wait_until="domcontentloaded", timeout=90000)
            human_delay(2, 4)

{actions_code}

            print("[+] Scenario complete.")
            if save_callback:
                pass

    except Exception as exc:
        print(f"[-] Runtime error: {{exc}}")
        return False
    finally:
        if debug_mode and logger:
            logger.stop_tracing(context)
            print(f"[+] Trace saved → {{log_path}}")
        pm.stop()

    return True
'''

_CLICK_TMPL = """\
            try:
                _el = {selector}
                if _el.is_visible(timeout=7000):
                    _el.scroll_into_view_if_needed(timeout=5000)
                    cursor.click(_el)
                    human_delay(0.6, 1.4)
            except Exception as _e:
                print(f"[-] Click failed ({label!r}): {{_e}}")
"""

_INPUT_TMPL = """\
            try:
                _el = {selector}
                if _el.is_visible(timeout=7000):
                    _el.scroll_into_view_if_needed(timeout=5000)
                    cursor.click(_el)
                    _el.fill("")
                    page.keyboard.type({value!r}, delay=random.randint(40, 90))
                    human_delay(0.4, 0.9)
            except Exception as _e:
                print(f"[-] Input failed ({label!r}): {{_e}}")
"""

_SELECT_TMPL = """\
            try:
                _el = {selector}
                if _el.is_visible(timeout=7000):
                    _el.select_option("{value}")
                    human_delay(0.3, 0.7)
            except Exception as _e:
                print(f"[-] Select failed ({label!r}): {{_e}}")
"""

_CHECK_TMPL = """\
            try:
                _el = {selector}
                if _el.is_visible(timeout=7000):
                    _el.scroll_into_view_if_needed(timeout=5000)
                    if _el.is_checked() != {checked}:
                        cursor.click(_el)
                        human_delay(0.3, 0.7)
            except Exception as _e:
                print(f"[-] Check failed ({label!r}): {{_e}}")
"""

_KEY_TMPL = """\
            page.keyboard.press("{key}")
            human_delay(0.2, 0.5)
"""

_NAV_TMPL = """\
            print("[*] Navigating to {url}...")
            page.goto("{url}", wait_until="domcontentloaded", timeout=90000)
            human_delay(2, 4)
"""

_WAIT_NAV_TMPL = """\
            try:
                page.wait_for_url("{url}*", timeout=30000)
                human_delay(1, 3)
            except Exception:
                print("[*] Navigation did not reach {url}, continuing...")
"""

def _safe_label(d):
    raw = (
        d.get("ariaLabel") or d.get("text") or d.get("testId")
        or d.get("id") or d.get("name") or d.get("cssClass") or "element"
    )
    return raw.replace("\n", " ").replace("\r", "").strip()[:60]

def _generate_action_lines(actions):
    lines = []
    for a in actions:
        t, d = a["type"], a["details"]

        if t == "CLICK":
            sel = _best_selector(d)
            if not sel:
                continue
            label = _safe_label(d)
            lines.append(_CLICK_TMPL.format(label=label, selector=sel))

        elif t == "INPUT":
            sel = _best_selector(d, for_input=True)
            if not sel:
                continue
            label = (
                d.get("placeholder") or d.get("ariaLabel") or d.get("name") or d.get("id") or "field"
            ).replace("\n", " ").strip()[:60]
            value = d.get("value", "")
            lines.append(_INPUT_TMPL.format(
                label=label,
                selector=sel,
                value=value,
                value_preview=value[:40],
            ))

        elif t == "SELECT":
            sel = _best_selector(d)
            if not sel:
                continue
            label = _safe_label(d)
            lines.append(_SELECT_TMPL.format(
                label=label,
                selector=sel,
                value=_esc(d.get("value", "")),
            ))

        elif t == "CHECK":
            sel = _best_selector(d)
            if not sel:
                continue
            label = _safe_label(d)
            lines.append(_CHECK_TMPL.format(
                label=label,
                selector=sel,
                checked=str(d.get("checked", True)),
            ))

        elif t == "KEY":
            lines.append(_KEY_TMPL.format(key=d.get("key", "")))

        elif t == "NAVIGATE":
            url = d.get("url", "")
            if url:
                lines.append(_NAV_TMPL.format(url=_esc(url)))

        elif t == "WAIT_NAV":
            url = d.get("url", "")
            if url:
                lines.append(_WAIT_NAV_TMPL.format(url=_esc(url)))

    return "".join(lines) if lines else "            pass\n"

def _create_app(name, url, actions):
    app_dir = os.path.join(PROJECT_ROOT, "apps", name)
    os.makedirs(app_dir, exist_ok=True)

    init_path = os.path.join(app_dir, "__init__.py")
    if not os.path.exists(init_path):
        open(init_path, "w").close()

    actions_code = _generate_action_lines(actions)

    script = _SCRIPT_TEMPLATE.format(
        name=name,
        url=url,
        ts=time.strftime("%Y-%m-%d %H:%M:%S"),
        actions_code=actions_code,
    )

    main_path = os.path.join(app_dir, "main.py")
    with open(main_path, "w", encoding="utf-8") as fh:
        fh.write(script)

    return main_path

def _do_record(url, proxy_port=None, debug_mode=False, project_name="recording"):
    """
    Запускает Playwright в невидимом (стелс) режиме с внедренным JS-скриптом 
    и записывает все действия пользователя, пока вкладка не будет закрыта.
    """
    recorded = []
    logger = None

    with sync_playwright() as p:
        print(f"[*] Launching browser → {url}  (proxy port: {proxy_port})")
        browser_cfg = browser_factory.get_browser_config(headless=False, port=proxy_port)
        browser = p.chromium.launch(**browser_cfg)

        if proxy_port:
            proxy_info = get_proxy_info(proxy_port)
            print(f"[+] Proxy geo: {proxy_info}")
        else:
            proxy_info = {"timezone": "UTC", "locale": "en-US"}

        context_args, hw = browser_factory.get_context_config(proxy_info)

        if debug_mode:
            logger = SessionLogger(f"rec_{project_name}_{int(time.time())}")
            log_dir = logger.prepare()
            context_args["record_har_path"] = os.path.join(log_dir, "network.har")
            print(f"[*] Debug mode — logs: {log_dir}")

        context = browser.new_context(**context_args)

        if debug_mode:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)

        stealth = browser_factory.get_stealth_script(hw)
        context.add_init_script(stealth)
        context.add_init_script(_RECORDER_JS)

        page = context.new_page()

        if debug_mode and logger:
            logger.setup_page_logging(page)

        def _record_action(action_type, details):
            recorded.append({"type": action_type, "details": details})
            label = (
                details.get("ariaLabel")
                or details.get("text")
                or details.get("placeholder")
                or details.get("name")
                or details.get("id")
                or details.get("key")
                or details.get("url")
                or ""
            )
            print(f"  [REC] {action_type:10s} {label[:70]}", flush=True)

        page.expose_function("recordAction", _record_action)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        except Exception as exc:
            print(f"[!] Navigation error: {exc}")
            print("[*] The page may still have loaded partially. Continue in the browser.")

        print()
        print("=" * 55)
        print("  RECORDING ACTIVE — interact in the browser window")
        print("  Every click / input / select will log here in real-time.")
        print("  Close the BROWSER TAB (not the whole window) when done.")
        print("=" * 55)
        print()

        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass

        print("[*] Tab closed — wrapping up session...")

        if debug_mode and logger:
            logger.stop_tracing(context)
            print(f"[+] Trace saved.")

        try:
            browser.close()
        except Exception:
            pass

    return _clean_actions(recorded)

def _setup_proxy():
    """
    Подготавливает прокси для сессии. Сначала пытается взять приватные прокси
    из файла proxy.txt, затем использует резервный список. Запускает туннель.
    """
    private_file = os.path.join(PROJECT_ROOT, "proxy.txt")
    proxy_link = None

    if os.path.exists(private_file):
        with open(private_file, "r", encoding="utf-8") as fh:
            candidates = [
                l.strip() for l in fh
                if l.strip().startswith(("vless://", "trojan://", "ss://", "vmess://",
                                         "http://", "https://", "socks4://", "socks5://"))
            ]
        if candidates:
            proxy_link = random.choice(candidates)
            print(f"[*] Using private proxy from proxy.txt")

    if not proxy_link:
        proxy_link = get_random_proxy()
        if not proxy_link:
            print("[!] No proxies found in data/proxy_list.txt.")

    if not proxy_link:
        return None, None

    port = random.randint(15_000, 25_000)
    pm = ProxyManager(proxy_link, port)
    print(f"[*] Starting proxy tunnel on port {port}...")
    if pm.start():
        if check_proxy_connectivity(port):
            print(f"[+] Proxy is reachable on port {port}.")
            return pm, port
        else:
            print("[-] Proxy started but not reachable. Proceeding without proxy.")
            pm.stop()
    else:
        print("[-] Failed to start proxy tunnel.")

    return None, None

def main():
    """
    Главная функция запуска. Инициализирует интерактивный CLI, 
    спрашивает настройки и запускает процесс записи макроса.
    """
    print()
    print("╔══════════════════════════════════════╗")
    print("║    Macro Recorder v3.0 (core stack)  ║")
    print("╚══════════════════════════════════════╝")
    print()

    try:
        project_name = input("Project name (e.g. tuta_reg): ").strip().lower()
        if not project_name:
            project_name = "recording"

        url = input("Target URL: ").strip()
        if not url.startswith("http"):
            url = "https://" + url

        use_proxy = input("Use proxy? (y/n) [n]: ").strip().lower() == "y"
        debug_mode = input("Debug mode — HAR + trace? (y/n) [n]: ").strip().lower() == "y"

        pm = None
        proxy_port = None

        if use_proxy:
            pm, proxy_port = _setup_proxy()
            if not proxy_port:
                print("[!] Proceeding without proxy (real IP).")

        actions = _do_record(
            url,
            proxy_port=proxy_port,
            debug_mode=debug_mode,
            project_name=project_name,
        )

        if pm:
            pm.stop()

        if not actions:
            print("\n[-] No actions were recorded.")
            return

        print(f"\n[+] Recorded {len(actions)} actions:")
        for i, a in enumerate(actions, 1):
            d = a["details"]
            label = (
                d.get("ariaLabel") or d.get("text") or d.get("placeholder")
                or d.get("name") or d.get("id") or d.get("key") or d.get("url") or ""
            )
            print(f"    {i:3d}. {a['type']:10s} {label[:60]}")

        out_path = _create_app(project_name, url, actions)
        print(f"\n[✓] Script written to: {out_path}")
        print(f"    Run it with:\n")
        print(f"        from apps.{project_name}.main import run")
        print(f"        run(link, port, save_callback)")
        print()

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user.")
        if "pm" in dir() and pm:
            pm.stop()

if __name__ == "__main__":
    main()
