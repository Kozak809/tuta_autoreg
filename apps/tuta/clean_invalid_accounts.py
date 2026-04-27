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
                        # cpath обычно выглядит как "data/configs/config_xxx.json"
                        # base_dir указывает на apps/tuta
                        full_cpath = os.path.join(base_dir, cpath)
                        
                        deleted = False
                        if os.path.exists(full_cpath):
                            os.remove(full_cpath)
                            deleted = True
                        # На случай, если конфиг лежит относительно корня проекта
                        elif os.path.exists(cpath):
                            os.remove(cpath)
                            deleted = True
                            
                        if deleted:
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
