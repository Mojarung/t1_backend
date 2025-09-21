"""
Улучшенный тестовый скрипт для проверки исправленного AI-поиска кандидатов
Демонстрирует работу с реальными данными из базы
"""

import requests
import json
import os
from typing import Optional

def load_jwt_token() -> Optional[str]:
    """
    Загружает JWT токен из переменной окружения
    """
    token = os.getenv('JWT_TOKEN')
    if not token:
        print("⚠️  JWT_TOKEN не найден в переменных окружения")
        print("💡 Для тестирования:")
        print("   1. Авторизуйтесь через /auth/login")
        print("   2. Скопируйте access_token")
        print("   3. export JWT_TOKEN='your-token'")
        return None
    return token

def test_improved_search(base_url: str = "http://localhost:8000"):
    """
    Тестирует исправленный AI-поиск кандидатов
    """
    
    jwt_token = load_jwt_token()
    if not jwt_token:
        print("❌ Невозможно выполнить тест без JWT токена")
        return
    
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }
    
    endpoint = f"{base_url}/candidate-selection/ai-search"
    
    # Тестовые сценарии с более гибкой фильтрацией
    test_cases = [
        {
            "name": "🔍 Общий поиск без фильтров",
            "description": "Ищем всех активных пользователей без фильтрации по навыкам",
            "request": {
                "job_title": "IT Специалист",
                "job_description": "Ищем IT специалиста для работы в команде разработки. Приветствуется любой технический опыт.",
                "required_skills": [],  # Пустой массив - поиск по всем пользователям
                "max_candidates": 20,
                "threshold_filter_limit": 100
            }
        },
        {
            "name": "🐍 Python разработчик (мягкая фильтрация)",
            "description": "Поиск с одним навыком, но допускаются разные уровни",
            "request": {
                "job_title": "Python Developer",
                "job_description": "Нужен разработчик для работы с Python. Уровень опыта любой - от начинающего до эксперта.",
                "required_skills": ["Python"],
                "max_candidates": 15,
                "threshold_filter_limit": 50
            }
        },
        {
            "name": "📊 Data Scientist",
            "description": "Поиск специалиста по данным с широким спектром навыков",
            "request": {
                "job_title": "Data Scientist", 
                "job_description": "Специалист по анализу данных. Нужны знания Python, SQL, машинного обучения, статистики.",
                "required_skills": ["Python", "SQL"],
                "additional_requirements": "Опыт с машинным обучением, pandas, numpy",
                "experience_level": "middle",
                "max_candidates": 10
            }
        },
        {
            "name": "🌟 Senior разработчик",
            "description": "Поиск опытного разработчика",
            "request": {
                "job_title": "Senior Software Developer",
                "job_description": "Ищем опытного разработчика для ведения проектов. Нужен опыт руководства командой и архитектурных решений.",
                "required_skills": [],
                "experience_level": "senior",
                "additional_requirements": "Опыт лидерства, архитектурные навыки",
                "max_candidates": 8
            }
        },
        {
            "name": "🚀 Стартап разработчик",
            "description": "Универсальный разработчик для стартапа",
            "request": {
                "job_title": "Full-Stack Developer",
                "job_description": "Ищем универсального разработчика для стартапа. Готовность работать с разными технологиями, быстро обучаться.",
                "required_skills": ["JavaScript"],
                "additional_requirements": "Гибкость, готовность к обучению, стартап опыт",
                "max_candidates": 12
            }
        }
    ]
    
    print("🚀 Тестирование улучшенного AI-поиска кандидатов...")
    print(f"🌐 API: {endpoint}")
    print("=" * 80)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 ТЕСТ {i}: {test_case['name']}")
        print("─" * 60)
        print(f"📝 {test_case['description']}")
        
        request_data = test_case['request']
        print(f"\n📋 Параметры:")
        print(f"   • Вакансия: {request_data['job_title']}")
        print(f"   • Навыки: {request_data.get('required_skills', [])}")
        print(f"   • Уровень: {request_data.get('experience_level', 'любой')}")
        print(f"   • Макс. кандидатов: {request_data.get('max_candidates', 20)}")
        
        print(f"\n🔄 Отправляем запрос...")
        
        try:
            response = requests.post(endpoint, headers=headers, json=request_data, timeout=60)
            
            print(f"📡 HTTP Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                # Основная статистика
                print(f"✅ УСПЕХ!")
                print(f"   📊 Найдено профилей: {result.get('total_profiles_found', 0)}")
                print(f"   🤖 Обработано AI: {result.get('processed_by_ai', 0)}")
                print(f"   ⏱️  Время: {result.get('processing_time_seconds', 0)}с")
                print(f"   🔍 Фильтры: {', '.join(result.get('filters_applied', []))}")
                
                # Детали кандидатов
                candidates = result.get('candidates', [])
                if candidates:
                    print(f"\n👥 ТОП-{min(len(candidates), 3)} КАНДИДАТ(ОВ):")
                    for j, candidate in enumerate(candidates[:3], 1):
                        print(f"\n   {j}. {candidate.get('full_name', 'Имя не указано')} "
                              f"(⭐ {candidate.get('match_score', 0):.2f})")
                        
                        email = candidate.get('email', 'email не указан')
                        print(f"      📧 {email}")
                        
                        position = candidate.get('current_position')
                        if position:
                            print(f"      🏢 {position}")
                        
                        exp = candidate.get('experience_years')
                        if exp:
                            print(f"      📅 Опыт: {exp}")
                        
                        # Навыки
                        prog_langs = candidate.get('programming_languages', [])
                        if prog_langs:
                            print(f"      💻 Языки: {', '.join(prog_langs[:4])}")
                        
                        skills = candidate.get('key_skills', [])
                        if skills:
                            print(f"      🛠️  Навыки: {', '.join(skills[:4])}")
                        
                        # AI анализ
                        summary = candidate.get('ai_summary', '')
                        if summary:
                            print(f"      🤖 AI: {summary[:150]}...")
                        
                        # Сильные стороны
                        strengths = candidate.get('strengths', [])
                        if strengths:
                            print(f"      💪 Сильные: {', '.join(strengths[:2])}")
                        
                        # Векторная схожесть
                        similarity = candidate.get('similarity_score')
                        if similarity is not None:
                            print(f"      📈 Схожесть: {similarity:.3f}")
                
                else:
                    print(f"\n❓ Кандидаты не найдены")
                    if result.get('total_profiles_found', 0) > 0:
                        print(f"   💡 Найдено профилей, но не обработано AI - возможна проблема с векторизацией")
                    
            elif response.status_code == 401:
                print("❌ Ошибка авторизации - проверьте JWT токен")
                break
            elif response.status_code == 403:
                print("❌ Доступ запрещен - нужны HR права")
                break
            else:
                print(f"❌ Ошибка {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   📋 Детали: {error_data.get('detail', 'Неизвестная ошибка')}")
                except:
                    print(f"   📋 Ответ: {response.text[:300]}")
        
        except requests.Timeout:
            print("❌ Таймаут запроса (>60s)")
        except requests.RequestException as e:
            print(f"❌ Ошибка соединения: {e}")
        except Exception as e:
            print(f"❌ Неожиданная ошибка: {e}")
        
        if i < len(test_cases):
            print("\n" + "─" * 60)
    
    print("\n" + "=" * 80)
    print("🏁 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
    
    print("\n💡 РЕКОМЕНДАЦИИ:")
    print("   • Убедитесь что база содержит пользователей с ролью 'user'")
    print("   • Проверьте заполненность полей: programming_languages, other_competencies, about")
    print("   • Для лучшей работы добавьте разнообразный контент в профили пользователей")
    print("   • Векторные профили создаются автоматически при первом поиске")
    print("   • При ошибках LLM API используется fallback логика")

def main():
    """
    Основная функция запуска тестов
    """
    print("🤖 AI HR Assistant - Тестирование улучшенного поиска кандидатов")
    print("=" * 80)
    
    # Можно переопределить URL через переменную окружения
    api_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    print(f"🌐 API URL: {api_url}")
    
    test_improved_search(api_url)

if __name__ == "__main__":
    main()
