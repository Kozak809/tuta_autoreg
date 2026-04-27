"""
Utility script to clean up temporary files and directories.

This script searches for and removes junk files such as logs, temporary folders,
__pycache__ directories, error screenshots, and media records across the project,
freeing up space and maintaining a clean workspace.
"""
import os
import shutil
import glob

def clean_junk():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Папки для полного удаления (включая содержимое)
    folders_to_remove = [
        "logs",
        "log",
        "temp",
        "apps/logs",
        "apps/tuta/logs",
        "apps/tuta/temp",
        "apps/tiktok/temp"
    ]
    
    # 2. Паттерны файлов для удаления по всему проекту
    file_patterns_to_remove = [
        "**/*.png",      # скриншоты ошибок и капчи
        "**/*.log",      # лог файлы
        "**/*.mp4",      # видео записи (если есть)
        "**/*.webm"
    ]
    
    # 3. Удаление папок
    print("[*] Удаление временных папок (logs, temp)...")
    for folder in folders_to_remove:
        folder_path = os.path.join(base_dir, folder)
        if os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path)
                print(f"  [+] Удалена папка: {folder}")
            except Exception as e:
                print(f"  [-] Ошибка при удалении {folder}: {e}")
                
    # 4. Удаление __pycache__
    print("\n[*] Удаление кэша Python (__pycache__)...")
    for root, dirs, files in os.walk(base_dir):
        if "__pycache__" in dirs:
            cache_dir = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(cache_dir)
                print(f"  [+] Удален кэш: {os.path.relpath(cache_dir, base_dir)}")
            except Exception as e:
                print(f"  [-] Ошибка при удалении {cache_dir}: {e}")

    # 5. Удаление мусорных файлов по маскам
    print("\n[*] Удаление скриншотов, логов и медиа файлов...")
    for pattern in file_patterns_to_remove:
        # Используем recursive=True для поиска по всем подпапкам
        matched_files = glob.glob(os.path.join(base_dir, pattern), recursive=True)
        for file_path in matched_files:
            try:
                os.remove(file_path)
                print(f"  [+] Удален файл: {os.path.relpath(file_path, base_dir)}")
            except Exception as e:
                print(f"  [-] Ошибка при удалении {file_path}: {e}")

    print("\n[+++] Очистка мусора успешно завершена!")

if __name__ == "__main__":
    clean_junk()
