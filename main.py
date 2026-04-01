import os, time, subprocess, sys
import macro

# --- НАСТРОЙКИ ЯДРА ---
target_accounts = 20
ACCOUNTS_FILE = "accounts.txt"
PROXY_COMMAND = 'curl -s https://www.v2nodes.com/ | grep "/servers/" | sed -n \'s/.*href="\\([^"]*\\)".*/https:\\/\\/www.v2nodes.com\\1/p\' | xargs curl -s | awk -v RS=\'</textarea>\' \'/<textarea/{gsub(/.*<textarea[^>]*>/,""); print}\' > proxy.txt'

def save_account(email, password, recovery_code="N/A"):
    with open(ACCOUNTS_FILE, "a") as f:
        f.write(f"{email}:{password}:{recovery_code}\n")

def update_proxies():
    print("[*] Обновление списка прокси...")
    subprocess.run(PROXY_COMMAND, shell=True)

def get_success_count():
    if not os.path.exists(ACCOUNTS_FILE): return 0
    with open(ACCOUNTS_FILE, "r") as f:
        return sum(1 for line in f if line.strip())

def main():
    global target_accounts
    if len(sys.argv) > 1:
        try:
            target_accounts = int(sys.argv[1])
        except ValueError:
            pass

    initial_count = get_success_count()
    print(f"[*] Цель: {target_accounts} новых аккаунтов. Уже есть: {initial_count}")
    
    attempts = 0
    while True:
        current_count = get_success_count()
        needed = target_accounts - (current_count - initial_count)
        
        if needed <= 0:
            print(f"[+] Цель достигнута! Зарегистрировано новых: {target_accounts}")
            break
            
        update_proxies()
        if not os.path.exists("proxy.txt"):
            time.sleep(5); continue
            
        with open("proxy.txt", "r", encoding="utf-8") as f:
            links = [l.strip() for l in f if l.lower().startswith(("vless://", "trojan://", "ss://", "vmess://"))]
        
        if os.path.exists("proxy.txt"): os.remove("proxy.txt")

        if not links:
            print("[-] Прокси не найдены, ждем...")
            time.sleep(5); continue
            
        batch = links[:min(50, needed)]
        
        print(f"[*] Запуск {len(batch)} попыток последовательно (Нужно еще: {needed})...")
        for link in batch:
            # Разносим порты для каждого прокси
            port = 5000 + (attempts % 1000)
            try:
                macro.run(link, port, save_account)
            except Exception as e:
                print(f"[-] Ошибка при выполнении: {e}")
            attempts += 1
            
            # Проверяем, не достигли ли мы цели внутри цикла
            if get_success_count() - initial_count >= target_accounts:
                break
        
        time.sleep(2)

if __name__ == "__main__":
    main()
