"""
Тестовый скрипт для проверки AI-поиска кандидатов
Демонстрирует работу эндпоинта /candidate-selection/ai-search
"""

import requests
import json
import os
from typing import Optional

def load_jwt_token() -> Optional[str]:
    """
    Загружает JWT токен из переменной окружения или возвращает тестовый токен.
    Для получения токена нужно авторизоваться через /auth/login
    ""sd"
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzdHJpbmciLsdCJleHAiOjE3NTg0NDEyMjd9.Xs28sKBJRv86_dw1tJmudBg-A2Q2dp5-xSIKOCOLhBQ"
    if not token:
        print("⚠️  JWT_TOKEN не найден в переменных окружения")
        print("💡 Для тестирования сначала авторизуйтесь:")
        print("   1. POST /auth/login с credentials HR пользователя")
        print("   2. Скопируйте access_token из ответа")
        print("   3. Экспортируйте: export JWT_TOKEN='your-token-here'")
        return None
    return token

def test_ai_candidate_search(base_url: str = "http://localhost:8000"):
    """
    Тестирует AI-поиск кандидатов с несколькими примерами запросов
    """
    
    # Загружаем токен авторизации
    jwt_token = load_jwt_token()
    if not jwt_token:
        print("❌ Невозможно выполнить тест без JWT токена")
        return
    
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }
    
    endpoint = f"{base_url}/candidate-selection/ai-search"
    
    # Примеры тестовых запросов
    test_cases = [
        {
            "name": "🐍 Python Backend Developer",
            "request": {
                "job_title": "Senior Python Developer",
                "job_description": "Ищем опытного Python разработчика для работы с Django, PostgreSQL, Docker. Требуется опыт в разработке REST API, работе в команде и знание основ DevOps.",
                "required_skills": ["Python", "Django"],
                "additional_requirements": "Опыт с микросервисами и Docker будет большим плюсом",
                "experience_level": "senior",
                "max_candidates": 10,
                "threshold_filter_limit": 40
            }
        },
        {
            "name": "📊 Data Analyst", 
            "request": {
                "job_title": "Data Analyst",
                "job_description": "Нужен аналитик данных для работы с большими данными. SQL, Python, статистический анализ, создание отчетов и дашбордов.",
                "required_skills": ["SQL", "Python"],
                "additional_requirements": "Опыт с Power BI, Tableau или аналогичными инструментами визуализации",
                "experience_level": "middle", 
                "max_candidates": 15
            }
        },
        {
            "name": "⚛️ React Frontend Developer",
            "request": {
                "job_title": "React Frontend Developer", 
                "job_description": "Frontend разработчик для создания современных SPA приложений. React, TypeScript, Redux, современные инструменты разработки и тестирования.",
                "required_skills": ["React", "JavaScript"],
                "additional_requirements": "Знание TypeScript и опыт с state management",
                "experience_level": "middle",
                "max_candidates": 12
            }
        }
    ]
    
    print("🚀 Начинаем тестирование AI-поиска кандидатов...\n")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"{'='*60}")
        print(f"🧪 Тест {i}: {test_case['name']}")
        print(f"{'='*60}")
        
        print(f"📋 Описание: {test_case['request']['job_title']}")
        print(f"🎯 Навыки: {', '.join(test_case['request']['required_skills'])}")
        print(f"⚙️  Макс. кандидатов: {test_case['request'].get('max_candidates', 20)}")
        print("\n🔄 Отправляем запрос...")
        
        try:
            response = requests.post(endpoint, headers=headers, json=test_case['request'], timeout=30)
            
            print(f"📡 Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                print(f"✅ Успешно! Найдено кандидатов: {result['processed_by_ai']}")
                print(f"⏱️  Время обработки: {result.get('processing_time_seconds', 'N/A')}s")
                print(f"🔍 Фильтры: {', '.join(result.get('filters_applied', []))}")
                
                # Показываем топ-3 кандидата
                candidates = result.get('candidates', [])[:3]
                if candidates:
                    print(f"\n👥 Топ-{len(candidates)} кандидат(ов):")
                    for j, candidate in enumerate(candidates, 1):
                        print(f"\n  {j}. {candidate['full_name']} (Оценка: {candidate['match_score']})")
                        print(f"     📧 {candidate['email']}")
                        print(f"     🏢 {candidate.get('current_position', 'Позиция не указана')}")
                        print(f"     🛠️  Навыки: {', '.join(candidate.get('programming_languages', [])[:3])}")
                        print(f"     🤖 AI-саммари: {candidate['ai_summary'][:120]}...")
                        if candidate.get('strengths'):
                            print(f"     💪 Сильные стороны: {', '.join(candidate['strengths'][:2])}")
                else:
                    print("\n❌ Кандидаты не найдены")
                    
            elif response.status_code == 401:
                print("❌ Ошибка авторизации. Проверьте JWT токен")
                break
            elif response.status_code == 403:
                print("❌ Доступ запрещен. Требуются HR права")
                break
            else:
                print(f"❌ Ошибка: {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Детали: {error_detail.get('detail', 'Unknown error')}")
                except:
                    print(f"   Ответ: {response.text[:200]}")
                    
        except requests.RequestException as e:
            print(f"❌ Ошибка подключения: {e}")
        except Exception as e:
            print(f"❌ Неожиданная ошибка: {e}")
        
        print("\n" + "─" * 60 + "\n")
    
    print("🏁 Тестирование завершено!")
    print("\n💡 Советы:")
    print("   • Убедитесь, что база данных содержит пользователей с заполненными профилями")
    print("   • Проверьте наличие векторных профилей в таблице vec_profiles")
    print("   • Для лучших результатов добавьте пользователей с разнообразными навыками")

def main():
    """
    Основная функция для запуска тестов
    """
    print("🤖 AI HR Assistant - Тестирование поиска кандидатов")
    print("="*60)
    
    # Можно изменить базовый URL для тестирования в других средах
    base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    print(f"🌐 API URL: {base_url}")
    
    test_ai_candidate_search(base_url)

if __name__ == "__main__":
    main()
