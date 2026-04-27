import os
import re
import random
import requests
from concurrent.futures import ThreadPoolExecutor
from core.utils import DATA_DIR, PROXY_PATH

def fetch_page(link, base_url, headers):
    full_url = base_url.rstrip('/') + link
    try:
        srv_resp = requests.get(full_url, headers=headers, timeout=10)
        if srv_resp.status_code == 200:
            textareas = re.findall(r'<textarea[^>]*>(.*?)</textarea>', srv_resp.text, re.DOTALL)
            proxies = []
            for content in textareas:
                lines = content.strip().splitlines()
                for line in lines:
                    line = line.strip()
                    if line.startswith(("vless://", "trojan://", "ss://", "vmess://", "http://", "https://", "socks4://", "socks5://")):
                        proxies.append(line)
            return proxies
    except Exception: pass
    return []

def update_proxies_python():
    """Получает свежие прокси с v2nodes.com."""
    print("[*] Обновление списка прокси с v2nodes...")
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"}
    try:
        base_url = "https://www.v2nodes.com/"
        response = requests.get(base_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        server_links = re.findall(r'href="(/servers/[^"]+)"', response.text)
        random.shuffle(server_links)
        server_links = server_links[:50]
        
        all_proxies = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(lambda l: fetch_page(l, base_url, headers), server_links))
            
        for res in results:
            all_proxies.extend(res)

        if all_proxies:
            all_proxies = list(set(all_proxies))
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(PROXY_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(all_proxies))
            print(f"[+] Найдено и сохранено {len(all_proxies)} уникальных прокси в {PROXY_PATH}")
            return all_proxies
        else:
            print("[-] Прокси не найдены.")
            return []
    except Exception as e:
        print(f"[!] Критическая ошибка при обновлении прокси: {e}")
        return []
