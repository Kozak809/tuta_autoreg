"""
Utility script to clean up specific temporary directories.
Restricted to safe, pre-defined folders and Python cache.
"""
import os
import shutil

def clean_junk():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Список конкретных папок для удаления
    folders_to_remove = [
        "temp",
        "log",
        "apps/tuta/temp",
        "logs"
    ]
    
    # 2. Удаление указанных папок
    print("[*] Очистка временных папок...")
    for folder in folders_to_remove:
        folder_path = os.path.join(base_dir, folder)
        if os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path)
                print(f"  [+] Удалена папка: {folder}")
            except Exception as e:
                print(f"  [-] Ошибка при удалении {folder}: {e}")
                
    # 3. Удаление __pycache__ по всему проекту
    print("\n[*] Удаление кэша Python (__pycache__)...")
    for root, dirs, files in os.walk(base_dir):
        if "__pycache__" in dirs:
            cache_dir = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(cache_dir)
                print(f"  [+] Удален кэш: {os.path.relpath(cache_dir, base_dir)}")
            except Exception as e:
                print(f"  [-] Ошибка при удалении {cache_dir}: {e}")

    print("\n[+++] Безопасная очистка завершена!")

if __name__ == "__main__":
    clean_junk()
