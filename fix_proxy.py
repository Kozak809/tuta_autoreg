import os

with open('core/proxy_handler.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\n\n# Корень проекта', 'import os, json, time, base64, shutil, requests, subprocess as sp\nfrom urllib.parse import urlparse, parse_qs, unquote\n\n# Корень проекта')

new_funcs = """

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
"""

content = content + "\n        if os.path.exists(self.tmp_config): os.remove(self.tmp_config)\n" + new_funcs

with open('core/proxy_handler.py', 'w', encoding='utf-8') as f:
    f.write(content)
