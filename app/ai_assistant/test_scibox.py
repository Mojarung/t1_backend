import requests

# Чтение API ключа из .env файла
import os

def load_api_key_from_env():
    env_path = '.env'
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"Файл {env_path} не найден.")
    with open(env_path, 'r') as f:
        for line in f:
            if line.strip().startswith('API_KEY_LLM'):
                # Разделяем по знаку равенства и убираем кавычки и пробелы
                key = line.split('=', 1)[1].strip().strip('"').strip("'")
                return key
    raise ValueError("API_KEY_LLM не найден в .env файле.")

api_key = load_api_key_from_env()

# URL для SciBox API
URL = "https://llm.t1v.scibox.tech/v1/chat/completions"

# Параметры запроса
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": "Qwen2.5-72B-Instruct-AWQ",
    "messages": [
        {"role": "system", "content": "Ты дружелюбный помощник"},
        {"role": "user", "content": "Привет! Как у тебя дела?"}
    ],
    "temperature": 0.7,
    "top_p": 0.9,
    "max_tokens": 256
}

# Выполнение запроса
try:
    response = requests.post(URL, headers=headers, json=payload)
    
    # Проверка успешности запроса
    if response.status_code == 200:
        result = response.json()
        print("Ответ от модели:")
        print(result['choices'][0]['message']['content'])
    else:
        print(f"Ошибка: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"Произошла ошибка: {e}")
