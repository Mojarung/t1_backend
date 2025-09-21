"""
Тестовый скрипт для демонстрации работы AI Assistant API
Показывает основные возможности персонального карьерного ассистента
"""

import requests
import json
import os
from typing import Optional

class AIAssistantTester:
    """
    Класс для тестирования AI Assistant API
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.jwt_token = None
    
    def login(self, username: str, password: str) -> bool:
        """
        Авторизация и получение JWT токена
        """
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                json={"username": username, "password": password}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.jwt_token = data["access_token"]
                self.session.headers.update({
                    "Authorization": f"Bearer {self.jwt_token}"
                })
                print("✅ Успешная авторизация")
                return True
            else:
                print(f"❌ Ошибка авторизации: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False
    
    def test_chat_conversation(self):
        """
        Тест основного функционала чата с ассистентом
        """
        print("\n" + "="*60)
        print("🤖 Тестирование чата с AI-ассистентом")
        print("="*60)
        
        # Список тестовых вопросов
        test_messages = [
            "Привет! Расскажи, как ты можешь помочь в карьерном развитии?",
            "Хочу подняться по карьерной лестнице до Senior Python Developer",
            "Покажи мне подходящие курсы для изучения",
            "Какие навыки мне нужно развивать в первую очередь?"
        ]
        
        session_id = None
        
        for i, message in enumerate(test_messages, 1):
            print(f"\n📝 Сообщение {i}: {message}")
            
            try:
                request_data = {"message": message}
                if session_id:
                    request_data["session_id"] = session_id
                
                response = self.session.post(
                    f"{self.base_url}/ai-assistant/chat",
                    json=request_data,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    session_id = data["session_id"]
                    
                    print(f"🤖 Ответ ассистента:")
                    print(f"   {data['response'][:200]}...")
                    
                    if data.get("recommendations"):
                        print(f"💡 Рекомендаций: {len(data['recommendations'])}")
                        for rec in data["recommendations"][:2]:
                            print(f"   • {rec.get('title', 'Unknown')}")
                    
                    if data.get("quick_replies"):
                        print(f"⚡ Быстрые ответы: {', '.join(data['quick_replies'][:3])}")
                        
                else:
                    print(f"❌ Ошибка {response.status_code}: {response.text}")
                    
            except Exception as e:
                print(f"❌ Ошибка запроса: {e}")
    
    def test_course_recommendations(self):
        """
        Тест рекомендаций курсов
        """
        print("\n" + "="*60)
        print("📚 Тестирование рекомендаций курсов")
        print("="*60)
        
        try:
            request_data = {
                "goal": "Стать экспертом в машинном обучении",
                "current_skills": ["Python", "SQL", "Statistics"],
                "preferred_level": "middle",
                "max_recommendations": 5
            }
            
            response = self.session.post(
                f"{self.base_url}/ai-assistant/course-recommendations",
                json=request_data
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Получены рекомендации курсов")
                print(f"📋 Объяснение: {data['explanation'][:150]}...")
                print(f"⏱️ Время изучения: {data.get('estimated_time', 'Не указано')}")
                
                print(f"\n📚 Рекомендованные курсы:")
                for i, course in enumerate(data["courses"], 1):
                    print(f"   {i}. {course['title']} ({course['category']})")
                    print(f"      Уровень: {course.get('level', 'N/A')}")
                    print(f"      Навыки: {', '.join(course.get('skills', [])[:3])}")
                
                if data.get("learning_path"):
                    print(f"\n🛤️ Рекомендуемый путь изучения:")
                    for i, step in enumerate(data["learning_path"], 1):
                        print(f"   {i}. {step}")
                        
            else:
                print(f"❌ Ошибка {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"❌ Ошибка запроса: {e}")
    
    def test_career_guidance(self):
        """
        Тест карьерных советов
        """
        print("\n" + "="*60)
        print("🚀 Тестирование карьерных советов")
        print("="*60)
        
        try:
            request_data = {
                "question": "Как мне стать Team Lead в Python разработке?",
                "current_position": "Middle Python Developer",
                "target_position": "Team Lead Python"
            }
            
            response = self.session.post(
                f"{self.base_url}/ai-assistant/career-guidance",
                json=request_data
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Получены карьерные советы")
                print(f"💡 Совет: {data['advice'][:200]}...")
                print(f"📊 Заполненность профиля: {data.get('profile_completeness', 'N/A')}%")
                
                if data.get("action_plan"):
                    print(f"\n📋 План действий:")
                    for i, action in enumerate(data["action_plan"], 1):
                        print(f"   {i}. {action}")
                
                if data.get("courses"):
                    print(f"\n📚 Рекомендованные курсы:")
                    for course in data["courses"][:3]:
                        print(f"   • {course['title']}")
                
                if data.get("missing_profile_fields"):
                    print(f"\n⚠️ Незаполненные поля: {', '.join(data['missing_profile_fields'])}")
                        
            else:
                print(f"❌ Ошибка {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"❌ Ошибка запроса: {e}")
    
    def test_courses_catalog(self):
        """
        Тест каталога курсов
        """
        print("\n" + "="*60)
        print("📖 Тестирование каталога курсов")
        print("="*60)
        
        try:
            # Получаем категории
            response = self.session.get(f"{self.base_url}/ai-assistant/courses/categories")
            if response.status_code == 200:
                categories = response.json()["categories"]
                print(f"📂 Доступные категории: {', '.join(categories[:5])}")
            
            # Получаем курсы с фильтрацией
            response = self.session.get(
                f"{self.base_url}/ai-assistant/courses",
                params={"category": "Backend Development", "limit": 5}
            )
            
            if response.status_code == 200:
                courses = response.json()
                print(f"\n📚 Найдено курсов по Backend Development: {len(courses)}")
                
                for course in courses:
                    print(f"   • {course['title']} ({course.get('level', 'N/A')} уровень)")
                    if course.get("technologies"):
                        print(f"     Технологии: {', '.join(course['technologies'][:3])}")
                        
            else:
                print(f"❌ Ошибка получения курсов: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Ошибка запроса: {e}")
    
    def test_assistant_stats(self):
        """
        Тест статистики ассистента
        """
        print("\n" + "="*60)
        print("📊 Тестирование статистики")
        print("="*60)
        
        try:
            response = self.session.get(f"{self.base_url}/ai-assistant/stats")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Статистика получена:")
                print(f"   💬 Всего сессий: {data['total_sessions']}")
                print(f"   📝 Всего сообщений: {data['total_messages']}")
                print(f"   💡 Рекомендаций дано: {data['recommendations_given']}")
                print(f"   ✅ Рекомендаций выполнено: {data['recommendations_completed']}")
                print(f"   🔥 Популярные темы: {', '.join(data.get('favorite_topics', []))}")
                        
            else:
                print(f"❌ Ошибка получения статистики: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Ошибка запроса: {e}")
    
    def run_full_test(self, username: str, password: str):
        """
        Запуск полного набора тестов
        """
        print("🤖 AI Assistant API - Полное тестирование")
        print("="*60)
        
        if not self.login(username, password):
            print("❌ Не удалось авторизоваться. Проверьте учетные данные.")
            return
        
        # Запускаем все тесты
        self.test_chat_conversation()
        self.test_course_recommendations() 
        self.test_career_guidance()
        self.test_courses_catalog()
        self.test_assistant_stats()
        
        print("\n" + "="*60)
        print("🎉 Тестирование завершено!")
        print("="*60)

def main():
    """
    Основная функция для запуска тестов
    """
    # Можно настроить через переменные окружения
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    username = os.getenv("TEST_USERNAME")
    password = os.getenv("TEST_PASSWORD")
    
    if not username or not password:
        print("⚠️ Необходимо установить переменные окружения:")
        print("   export TEST_USERNAME='your-email@example.com'")
        print("   export TEST_PASSWORD='your-password'")
        print("\nИли запустите с параметрами:")
        username = input("Введите email: ")
        password = input("Введите пароль: ")
    
    tester = AIAssistantTester(base_url)
    tester.run_full_test(username, password)

if __name__ == "__main__":
    main()
