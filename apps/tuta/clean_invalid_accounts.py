"""
Script to clean up invalid accounts from the database.

This module reads the account data file, identifies accounts marked as 'INVALID'
(e.g., banned or inaccessible), and removes them from the database along with
their corresponding configuration files to maintain a clean account pool.
"""
import json
import os

def clean_invalid_accounts():
    # Получаем путь к директории apps/tuta
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Путь к accounts.json относительно текущего скрипта
    accounts_file = os.path.join(base_dir, 'data', 'accounts.json')
    
    if not os.path.exists(accounts_file):
        print(f"[-] Файл {accounts_file} не найден.")
        return
        
    valid_accounts = []
    removed_accounts_count = 0
    removed_configs_count = 0

    with open(accounts_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
                
            try:
                acc = json.loads(line)
                status = acc.get('isvalid', '').upper()
                
                if status == 'INVALID':
                    removed_accounts_count += 1
                    cpath = acc.get('config_path', '')
                    
                    # Пытаемся найти и удалить файл конфигурации
                    if cpath:
                        _, real_cpath = resolve_config_path(cpath)
                        if real_cpath and os.path.exists(real_cpath):
                            os.remove(real_cpath)
                            removed_configs_count += 1
                else:
                    valid_accounts.append(line)
            except json.JSONDecodeError:
                # Если строка невалидна, сохраняем её (чтобы случайно не удалить то, что не смогли прочитать)
                valid_accounts.append(line)

    # Перезаписываем файл accounts.json только с валидными аккаунтами
    with open(accounts_file, 'w', encoding='utf-8') as f:
        for acc_line in valid_accounts:
            f.write(acc_line + '\n')

    print(f"[+] Очистка завершена!")
    print(f"    - Удалено забаненных аккаунтов из базы: {removed_accounts_count}")
    print(f"    - Удалено файлов конфигурации: {removed_configs_count}")
    print(f"    - Оставлено аккаунтов (VALID / UNKNOWN): {len(valid_accounts)}")

if __name__ == "__main__":
    clean_invalid_accounts()
