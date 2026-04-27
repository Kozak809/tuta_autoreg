"""
Integrates with external APIs to solve image-based captchas.

Specifically configured to process images, adjust contrast, and send them
to the OpenAI API (GPT vision models) to resolve visual challenges like clocks.
"""
import os
import base64
import requests
import numpy as np
from PIL import Image
from dotenv import load_dotenv

# --- НАСТРОЙКИ ---
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
# Основная мощная модель (март 2026)
MODEL_NAME = "gpt-5.4" 

def process_image(input_path, output_path):
    try:
        img = Image.open(input_path).convert("RGB")
        arr = np.array(img).astype(np.float32)

        # Увеличиваем контраст и резкость (более агрессивно)
        arr = (arr - 128) * 6 + 128
        arr = arr * 8

        # Ч/Б фильтр
        gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        arr = np.stack([gray, gray, gray], axis=2)

        arr = np.clip(arr, 0, 255)
        result = Image.fromarray(arr.astype(np.uint8))
        result.save(output_path)
        return output_path
    except Exception as e:
        print(f"[-] Ошибка обработки: {e}")
        return None

def solve_captcha(image_path):
    try:
        if not API_KEY:
            return "Ошибка: OPENAI_API_KEY не найден в .env"

        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": (
                                "Определи время на часах. Ответ дай строго в формате 00:00.\n"
                                "ПРАВИЛА:\n"
                                "1. ДЛИННАЯ стрелка — это МИНУТЫ (кратны 5).\n"
                                "2. КОРОТКАЯ стрелка — это ЧАСЫ.\n"
                                "3. Если часовая стрелка находится МЕЖДУ цифрами, выбирай меньшее значение (кроме случая 12 и 1).\n"
                                "Пример: если часы между 2 и 3, а минуты 45, то время 02:45.\n"
                                "Выведи только время 00:00."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            "max_completion_tokens": 50 
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        
        if response.status_code != 200:
            return f"Ошибка API {response.status_code}: {response.text}"

        result = response.json()
        return result['choices'][0]['message']['content'].strip()

    except Exception as e:
        return f"Критический сбой: {e}"

if __name__ == "__main__":
    # Проверка работы
    print(f"[*] Модель: {MODEL_NAME}")
    if API_KEY:
        print("[+] API_KEY загружен из .env")
    else:
        print("[-] API_KEY не найден!")
