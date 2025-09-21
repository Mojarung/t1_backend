"""
Быстрый тест для проверки исправления SQL ошибки с JSON полями
"""

import requests
import json
import os

def test_json_fix():
    """
    Тестирует, что исправление JSON cast работает корректно
    """
    
    # Получаем JWT токен (нужно установить в переменной окружения)
    jwt_token = os.getenv('JWT_TOKEN')
    if not jwt_token:
        print("❌ JWT_TOKEN не найден. Установите переменную окружения:")
        print("   export JWT_TOKEN='your-jwt-token-here'")
        return
    
    # API endpoint
    base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    endpoint = f"{base_url}/candidate-selection/ai-search"
    
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }
    
    # Простой тест запрос
    test_request = {
        "job_title": "Python Developer",
        "job_description": "Ищем Python разработчика для работы с веб-приложениями",
        "required_skills": ["Python"],  # Этот запрос вызывал SQL ошибку
        "max_candidates": 5
    }
    
    print("🧪 Тестируем исправление JSON cast ошибки...")
    print(f"🌐 Endpoint: {endpoint}")
    print(f"📋 Запрос: {test_request}")
    print("\n🔄 Отправляем запрос...")
    
    try:
        response = requests.post(endpoint, headers=headers, json=test_request, timeout=30)
        
        print(f"📡 HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ УСПЕХ! SQL ошибка исправлена!")
            print(f"   📊 Найдено профилей: {result.get('total_profiles_found', 0)}")
            print(f"   🤖 Обработано AI: {result.get('processed_by_ai', 0)}")
            print(f"   ⏱️  Время: {result.get('processing_time_seconds', 0)}с")
            
            candidates = result.get('candidates', [])
            if candidates:
                print(f"   👥 Кандидатов найдено: {len(candidates)}")
                for i, candidate in enumerate(candidates[:2], 1):
                    print(f"      {i}. {candidate.get('full_name', 'N/A')} "
                          f"(оценка: {candidate.get('match_score', 0):.2f})")
            else:
                print("   📋 Кандидаты не найдены (но запрос прошел успешно)")
                
        elif response.status_code == 401:
            print("❌ Ошибка авторизации - проверьте JWT токен")
        elif response.status_code == 500:
            print("❌ Серверная ошибка:")
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', '')
                if 'json ~~*' in error_detail or 'operator does not exist' in error_detail:
                    print("   🔍 ЭТО СТАРАЯ JSON ОШИБКА - исправление не сработало!")
                    print(f"   📋 Детали: {error_detail[:200]}...")
                else:
                    print(f"   📋 Другая ошибка: {error_detail[:200]}...")
            except:
                print(f"   📋 Ответ: {response.text[:300]}")
        else:
            print(f"❌ HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"   📋 Детали: {error_data.get('detail', 'Unknown error')}")
            except:
                print(f"   📋 Ответ: {response.text[:200]}")
                
    except requests.Timeout:
        print("❌ Таймаут запроса")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    print("\n" + "="*60)
    print("📝 ЗАКЛЮЧЕНИЕ:")
    print("   ✅ Если статус 200 - JSON cast исправление работает!")
    print("   ❌ Если статус 500 с 'json ~~*' - нужны дополнительные исправления")
    print("   🔑 Если статус 401 - проблема с авторизацией, не с кодом")

def main():
    print("🔧 Тест исправления JSON cast ошибки")
    print("="*60)
    test_json_fix()

if __name__ == "__main__":
    main()
