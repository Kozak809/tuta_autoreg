# Tuta Autoreg

A comprehensive automation suite for **Tuta (formerly Tutanota)** email accounts. This project provides tools for automated account registration, status checking, and automated email operations with advanced anti-bot bypasses.

## 🚀 Features

- **Automated Registration:** High-success rate account creation using Playwright.
- **Advanced Anti-Bot Bypasses:** 
    - Integrates `playwright-stealth`.
    - Custom fingerprint and hardware spoofing (Canvas, WebGL, Audio, etc.).
    - Human-like mouse movements (Bezier curves) and realistic typing patterns.
- **Automatic Captcha Solving:** Solves Tuta's clock-based captchas using OpenAI's Vision API (GPT-4o/GPT-4o-mini).
- **Proxy Support:** Full support for `vless://`, `trojan://`, `ss://`, and `vmess://` protocols via `sing-box` integration.
- **Parallel Execution:** High-speed multi-threaded "Conveyor" mode for bulk registration.
- **Account Management:**
    - **Checker:** Bulk validate account status (Valid/Banned).
    - **Sender:** Automate sending emails from multiple accounts.
    - **Receiver:** Monitor and read incoming emails in real-time.
- **Visual Monitoring:** Optional visual cursor to track automation progress in real-time.

---

## 🛠 Installation

### 1. Prerequisites
- **Python 3.8+**
- **sing-box:** Must be installed and available in your system `PATH`. [Download here](https://github.com/SagerNet/sing-box/releases).

### 2. Automatic Setup
Run the included installer to create a virtual environment, install dependencies, and setup Playwright:
```bash
python install.py
```

### 3. Configuration
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and add your **OpenAI API Key**:
   ```env
   OPENAI_API_KEY=your_sk_key_here
   ```

---

## 📖 Usage

### Automated Registration

**Conveyor Mode (Continuous registration):**
```bash
python -m apps.tuta.registrar 10 --show
```
*   `10`: Number of accounts to create.
*   `--show`: (Optional) Show visual cursor movement.
*   `--headless`: (Optional) Run browsers in the background.
*   `--nologs`: (Optional) Only show success/fail summaries.

### Account Utilities

**Status Checker:**
Validates accounts in `data/accounts.json` and saves results to `data/checked_results.json`.
```bash
python -m apps.tuta.account_checker --workers 15
```

**Email Sender:**
Send emails using your registered accounts.
```bash
python -m apps.tuta.mail_sender --to target@example.com --subject "Hello" --body "Test message" --accounts-num 5
```

**Email Receiver (Real-time monitor):**
Login to an account and monitor for incoming messages.
```bash
python -m apps.tuta.mail_receiver --email yourname@tutamail.com
```

---

## 📂 Project Structure

- `apps/tuta/registrar.py`: Core registration entry points (parallel).
- `apps/tuta/account_checker.py`: Parallel account validator.
- `apps/tuta/mail_sender.py` / `apps/tuta/mail_receiver.py`: Tools for email interactions.
- `install.py`: Automated environment setup.
- `core/`:
    - `captcha_solver.py`: OpenAI Vision integration for Tuta clocks.
    - `mouse_engine.py`: Smooth, non-linear mouse movements.
    - `proxy_handler.py`: `sing-box` wrapper for multi-protocol proxy support.
    - `browser_factory.py`: Advanced browser and fingerprint configuration.

---

## 📝 Data Storage
- `data/accounts.json`: Successfully registered accounts (JSON format).
- `data/accounts.txt`: Successfully registered accounts (Email:Password format).
- `data/checked_results.json`: Results from the checker script.
- `logs/sessions/`: Detailed session logs and network traces (if debug enabled).

---

## ⚠️ Disclaimer
This tool is for **educational and research purposes only**. The authors are not responsible for any misuse of this software. Please respect Tuta's Terms of Service and use responsibly.
