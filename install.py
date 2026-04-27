import os
import sys
import subprocess
import platform
import shutil

def run_command(command, shell=False):
    """Runs a shell command and returns its output."""
    try:
        process = subprocess.Popen(
            command,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        for line in process.stdout:
            print(line, end='')
        process.wait()
        return process.returncode == 0
    except Exception as e:
        print(f"Error executing command: {e}")
        return False

def setup():
    print("--- Tuta Autoreg Installer ---")
    
    # 1. Check Python version
    if sys.version_info < (3, 8):
        print("[-] Python 3.8 or higher is required.")
        sys.exit(1)
    
    # 2. Determine OS and paths
    is_windows = platform.system() == "Windows"
    venv_dir = "venv"
    
    if is_windows:
        python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
        pip_exe = os.path.join(venv_dir, "Scripts", "pip.exe")
    else:
        python_exe = os.path.join(venv_dir, "bin", "python")
        pip_exe = os.path.join(venv_dir, "bin", "pip")

    # 3. Create Virtual Environment
    if not os.path.exists(venv_dir):
        print(f"[*] Creating virtual environment in '{venv_dir}'...")
        if not run_command([sys.executable, "-m", "venv", venv_dir]):
            print("[-] Failed to create virtual environment.")
            sys.exit(1)
    else:
        print("[*] Virtual environment already exists.")

    # 4. Upgrade pip
    print("[*] Upgrading pip and installing PySocks...")
    run_command([python_exe, "-m", "pip", "install", "--upgrade", "pip", "PySocks"])

    # 5. Install requirements
    if os.path.exists("requirements.txt"):
        print("[*] Installing requirements from requirements.txt...")
        if not run_command([pip_exe, "install", "-r", "requirements.txt"]):
            print("[-] Failed to install requirements.")
            sys.exit(1)
    else:
        print("[-] requirements.txt not found!")

    # 6. Install Playwright browsers
    print("[*] Installing Playwright browsers...")
    if not run_command([python_exe, "-m", "playwright", "install"]):
        print("[-] Failed to install Playwright browsers.")
    
    if not is_windows:
        print("[!] Note: On Linux, you might need to run: 'sudo playwright install-deps' if browsers fail to launch.")
    
    # 7. Check for sing-box
    print("[*] Checking for sing-box...")
    sing_box_found = shutil.which("sing-box")
    if not sing_box_found:
        print("[!] 'sing-box' not found in PATH.")
        if is_windows:
            print("[!] Please download sing-box from https://github.com/SagerNet/sing-box/releases and add it to PATH.")
        else:
            print("[!] On Linux, you can install it using: sudo apt install sing-box (if available) or download from GitHub.")
    else:
        print(f"[+] Found sing-box at: {sing_box_found}")

    # 8. Setup .env file
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            print("[*] Creating .env from .env.example...")
            shutil.copy(".env.example", ".env")
            print("[!] Please edit .env and add your OPENAI_API_KEY and other settings.")
        else:
            print("[!] .env.example not found. Please create .env manually.")
    else:
        print("[*] .env file already exists.")

    print("\n[+] Installation complete!")
    if is_windows:
        print(f"To start, run: {venv_dir}\\Scripts\\activate && python apps/tuta/registrar.py")
    else:
        print(f"To start, run: source {venv_dir}/bin/activate && python apps/tuta/registrar.py")

if __name__ == "__main__":
    setup()
