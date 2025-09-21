"""
AI Assistant Service - Сервис для персонального карьерного ассистента
Реализует RAG-модель для персонализированных рекомендаций согласно idea.md

Основной функционал:
- Персонализированные рекомендации на основе профиля
- Автоподбор вакансий с процентом совпадения  
- Рекомендации курсов для заполнения пробелов в навыках
- RAG-поиск по векторным представлениям вакансий
- Генерация пошаговых планов развития
"""

import json
import re
import httpx
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc

from app.config import settings
from app.models import (
    User, ChatSession, ChatMessage, Course, Vacancy, Vec_profile, 
    AssistantRecommendation, UserRole
)
from app.schemas import (
    AssistantChatRequest, AssistantChatResponse, CourseRecommendationRequest,
    CourseRecommendationResponse, CareerGuidanceRequest, CareerGuidanceResponse,
    RecommendationResponse, CourseResponse, VacancyRecommendationResponse
)

# Импорты для векторного поиска
import numpy as np


class AIAssistantService:
    """
    Основной сервис AI-ассистента для карьерного консультирования.
    
    Реализует концепцию из idea.md:
    - RAG-модель для поиска релевантных вакансий
    - Сравнение навыков пользователя с требованиями
    - Персонализированные рекомендации курсов
    - Векторный поиск с процентами совпадения
    """

    def __init__(self):
        self.provider = "scibox"
        self.embedding_dimension = 1024  # bge-m3 embeddings
        
    def _build_llm_request(self, prompt: str, is_embedding: bool = False) -> tuple[str, Dict[str, str], Dict[str, Any]]:
        """
        Создает запрос к Scibox LLM API.
        Поддерживает как chat completion, так и embeddings.
        """
        system_prompt = (
            "Ты персональный карьерный консультант и HR-эксперт. "
            "Помогаешь сотрудникам IT-компании развиваться в карьере, "
            "рекомендуешь курсы, вакансии и составляешь планы развития. "
            "ВАЖНО: Отвечай КРАТКО и ПО СУЩЕСТВУ. Максимум 3-4 предложения. "
            "Используй списки и структурированный текст. Будь дружелюбным но лаконичным."
        )

        # Используем разные URL для embeddings и chat
        if is_embedding:
            base_url = getattr(settings, 'scibox_embeddings_base_url', 'https://llm.t1v.scibox.tech/v1')
            api_key = getattr(settings, 'scibox_embeddings_api_key', 'sk-your-api-key-here')
            url = f"{base_url.rstrip('/')}/embeddings"
            payload = {
                "model": "bge-m3",
                "input": prompt
            }
        else:
            base_url = getattr(settings, 'scibox_base_url', 'https://llm.t1v.scibox.tech/v1')
            api_key = getattr(settings, 'scibox_api_key', 'sk-your-api-key-here')
            url = f"{base_url.rstrip('/')}/chat/completions"
            payload = {
                "model": getattr(settings, 'scibox_model', 'Qwen2.5-72B-Instruct-AWQ'),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 300,  # Короткие ответы для чата
                "temperature": 0.6,  # Менее творческие, более структурированные ответы
                "top_p": 0.8,
            }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        return url, headers, payload

    async def _call_llm(self, prompt: str, is_embedding: bool = False) -> Any:
        """
        Выполняет запрос к LLM API
        """
        url, headers, payload = self._build_llm_request(prompt, is_embedding)

        print(f"🤖 AI Assistant LLM Request: {self.provider}")
        print(f"📍 URL: {url}")
        print(f"📊 Type: {'Embedding' if is_embedding else 'Chat'}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                
                if is_embedding:
                    return data["data"][0]["embedding"]
                else:
                    return data["choices"][0]["message"]["content"]
                    
            except httpx.HTTPStatusError as e:
                print(f"❌ HTTP Error: {e.response.status_code} - {e.response.text}")
                raise Exception(f"LLM API Error: {e.response.status_code}")
            except Exception as e:
                print(f"❌ Request Error: {e}")
                raise Exception(f"LLM Request Failed: {str(e)}")

    def _analyze_user_profile(self, user: User) -> Dict[str, Any]:
        """
        Анализирует профиль пользователя для персонализации ответов.
        Возвращает структурированную информацию о пользователе.
        """
        profile_analysis = {
            "basic_info": {
                "name": user.full_name or f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                "email": user.email,
                "location": user.location,
                "about": user.about
            },
            "skills": {
                "programming_languages": user.programming_languages or [],
                "other_competencies": user.other_competencies or [],
                "total_skills": len((user.programming_languages or []) + (user.other_competencies or []))
            },
            "experience": {
                "work_experience": user.work_experience or [],
                "education": user.education or [],
                "experience_count": len(user.work_experience or [])
            },
            "career": {
                "desired_salary": user.desired_salary,
                "ready_to_relocate": user.ready_to_relocate,
                "employment_type": user.employment_type.value if user.employment_type else None
            },
            "completeness": self._calculate_profile_completeness(user)
        }
        
        return profile_analysis

    def _calculate_profile_completeness(self, user: User) -> Dict[str, Any]:
        """
        Вычисляет процент заполненности профиля и определяет отсутствующие поля
        """
        required_fields = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "about": user.about,
            "location": user.location,
            "programming_languages": user.programming_languages,
            "other_competencies": user.other_competencies,
            "work_experience": user.work_experience,
            "education": user.education
        }
        
        filled_fields = sum(1 for value in required_fields.values() if value)
        total_fields = len(required_fields)
        completeness_percentage = (filled_fields / total_fields) * 100
        
        missing_fields = [
            field for field, value in required_fields.items() 
            if not value
        ]
        
        return {
            "percentage": round(completeness_percentage, 1),
            "filled_fields": filled_fields,
            "total_fields": total_fields,
            "missing_fields": missing_fields,
            "is_complete": completeness_percentage >= 80  # Считаем полным при 80%+
        }

    async def _find_relevant_vacancies(self, user: User, db: Session, limit: int = 5) -> List[Tuple[Vacancy, float]]:
        """
        Находит релевантные вакансии для пользователя с использованием векторного поиска.
        Реализует RAG-модель из idea.md для автоподбора вакансий.
        """
        # Создаем текстовое представление профиля пользователя
        user_profile_text = self._create_user_profile_text(user)
        
        # Получаем embedding профиля пользователя
        try:
            user_embedding = await self._call_llm(user_profile_text, is_embedding=True)
        except Exception as e:
            print(f"❌ Failed to generate user embedding: {e}")
            return []

        # Получаем активные вакансии
        vacancies = db.query(Vacancy).filter(
            Vacancy.status == "open"
        ).limit(50).all()  # Ограничиваем для производительности
        
        vacancy_similarities = []
        
        for vacancy in vacancies:
            try:
                # Создаем описание вакансии для векторизации
                vacancy_text = f"Вакансия: {vacancy.title}\nОписание: {vacancy.description or ''}\nТребования: {vacancy.requirements or ''}\nКомпания: {vacancy.company or ''}"
                
                # Получаем embedding вакансии
                vacancy_embedding = await self._call_llm(vacancy_text, is_embedding=True)
                
                # Вычисляем cosine similarity
                similarity = self._cosine_similarity(user_embedding, vacancy_embedding)
                vacancy_similarities.append((vacancy, similarity))
                
            except Exception as e:
                print(f"❌ Failed to process vacancy {vacancy.id}: {e}")
                continue

        # Сортируем по убыванию сходства и возвращаем топ
        vacancy_similarities.sort(key=lambda x: x[1], reverse=True)
        return vacancy_similarities[:limit]

    def _create_user_profile_text(self, user: User) -> str:
        """
        Создает текстовое представление профиля пользователя для векторизации
        """
        profile_parts = []
        
        # Основная информация
        if user.about:
            profile_parts.append(f"О себе: {user.about}")
        
        # Навыки
        if user.programming_languages:
            languages = ', '.join(user.programming_languages)
            profile_parts.append(f"Языки программирования: {languages}")
        
        if user.other_competencies:
            competencies = ', '.join(user.other_competencies)
            profile_parts.append(f"Навыки и компетенции: {competencies}")
        
        # Опыт работы (краткое описание)
        if user.work_experience:
            for i, exp in enumerate(user.work_experience[:3], 1):
                if isinstance(exp, dict):
                    role = exp.get('role', '')
                    company = exp.get('company', '')
                    if role:
                        profile_parts.append(f"Опыт {i}: {role}" + (f" в {company}" if company else ""))
        
        # Образование
        if user.education:
            for i, edu in enumerate(user.education[:2], 1):
                if isinstance(edu, dict):
                    degree = edu.get('degree', '')
                    field = edu.get('field_of_study', '') or edu.get('specialty', '')
                    if degree or field:
                        profile_parts.append(f"Образование {i}: {degree} {field}".strip())
        
        profile_text = '. '.join(filter(None, profile_parts))
        
        if not profile_text.strip():
            profile_text = f"Пользователь {user.username}, профиль заполнен частично"
        
        return profile_text

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Вычисляет косинусное сходство между векторами"""
        try:
            a = np.array(vec1)
            b = np.array(vec2)
            
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            similarity = dot_product / (norm_a * norm_b)
            return float(similarity)
        except Exception:
            return 0.0

    async def _recommend_courses(self, user: User, db: Session, goal: Optional[str] = None, limit: int = 5) -> List[Course]:
        """
        Рекомендует курсы на основе анализа пробелов в навыках пользователя.
        Реализует логику из idea.md для персонализированных рекомендаций.
        """
        user_skills = set()
        if user.programming_languages:
            user_skills.update([skill.lower() for skill in user.programming_languages])
        if user.other_competencies:
            user_skills.update([skill.lower() for skill in user.other_competencies])

        # Получаем все активные курсы
        courses = db.query(Course).filter(Course.is_active == True).all()
        
        recommended_courses = []
        
        for course in courses:
            course_skills = set()
            if course.skills:
                course_skills.update([skill.lower() for skill in course.skills])
            if course.technologies:
                course_skills.update([tech.lower() for tech in course.technologies])
            
            # Вычисляем пересечение навыков (что уже знает пользователь)
            skill_intersection = user_skills.intersection(course_skills)
            
            # Вычисляем новые навыки (что получит пользователь)
            new_skills = course_skills - user_skills
            
            # Логика рекомендации:
            # 1. Курс должен давать новые навыки (new_skills > 0)
            # 2. Но при этом иметь некоторую базу (небольшое пересечение приветствуется)
            if len(new_skills) > 0:
                # Вычисляем релевантность курса
                relevance_score = len(new_skills) * 1.0 + len(skill_intersection) * 0.3
                recommended_courses.append((course, relevance_score))
        
        # Сортируем по релевантности
        recommended_courses.sort(key=lambda x: x[1], reverse=True)
        
        return [course for course, _ in recommended_courses[:limit]]

    def _detect_career_growth_question(self, message: str) -> bool:
        """
        Определяет, задает ли пользователь вопрос о карьерном росте.
        Возвращает True, если нужно дать совет о заполнении профиля и прохождении курсов.
        """
        career_keywords = [
            "карьер", "рост", "развитие", "повысить", "продвинуться", 
            "стать", "senior", "middle", "junior", "позиция", 
            "должность", "повышение", "лестниц", "план развития"
        ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in career_keywords)

    async def process_chat_message(self, request: AssistantChatRequest, user: User, db: Session) -> AssistantChatResponse:
        """
        Основная функция обработки сообщения от пользователя.
        Анализирует запрос и генерирует персонализированный ответ с рекомендациями.
        """
        print(f"🤖 Processing chat message from user {user.id}: {request.message[:50]}...")
        
        # Анализируем профиль пользователя
        profile_analysis = self._analyze_user_profile(user)
        
        # Получаем или создаем сессию чата
        if request.session_id:
            session = db.query(ChatSession).filter(
                ChatSession.id == request.session_id,
                ChatSession.user_id == user.id
            ).first()
        else:
            session = None
            
        if not session:
            # Создаем новую сессию
            session = ChatSession(
                user_id=user.id,
                title=f"Чат {datetime.now().strftime('%d.%m %H:%M')}",
                context_data=profile_analysis
            )
            db.add(session)
            db.flush()
        
        # Сохраняем сообщение пользователя
        user_message = ChatMessage(
            session_id=session.id,
            role="user",
            content=request.message
        )
        db.add(user_message)
        db.flush()
        
        # Определяем тип запроса и генерируем ответ
        if self._detect_career_growth_question(request.message):
            # Специальная логика для вопросов о карьерном росте
            response_data = await self._handle_career_growth_question(user, db, request.message, profile_analysis)
        else:
            # Общий ответ ассистента
            response_data = await self._handle_general_question(user, db, request.message, profile_analysis)
        
        # Сохраняем ответ ассистента
        assistant_message = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=response_data["response"],
            metadata=response_data.get("metadata", {})
        )
        db.add(assistant_message)
        
        # Обновляем активность сессии
        session.last_activity_at = datetime.utcnow()
        
        db.commit()
        
        return AssistantChatResponse(
            session_id=session.id,
            message_id=assistant_message.id,
            response=response_data["response"],
            recommendations=response_data.get("recommendations", []),
            actions=response_data.get("actions", []),
            quick_replies=response_data.get("quick_replies", []),
            response_type=response_data.get("response_type", "general"),
            confidence=response_data.get("confidence")
        )

    async def _handle_career_growth_question(self, user: User, db: Session, message: str, profile_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Специальная обработка вопросов о карьерном росте.
        Согласно ТЗ: советует заполнить профиль и пройти курсы.
        """
        completeness = profile_analysis["completeness"]
        
        if not completeness["is_complete"]:
            # Профиль заполнен не полностью - советуем дозаполнить
            missing_fields_ru = {
                "first_name": "имя",
                "last_name": "фамилия", 
                "about": "описание \"о себе\"",
                "location": "местоположение",
                "programming_languages": "языки программирования",
                "other_competencies": "навыки и компетенции",
                "work_experience": "опыт работы",
                "education": "образование"
            }
            
            missing_list = [missing_fields_ru.get(field, field) for field in completeness["missing_fields"]]
            
            response = f"""Для построения карьерного плана мне нужно лучше узнать вас! 📊

Ваш профиль заполнен на {completeness['percentage']}%. Для персонализированных рекомендаций рекомендую дозаполнить:

{chr(10).join([f"• {field}" for field in missing_list[:5]])}

После заполнения профиля я смогу:
✅ Подобрать подходящие вакансии в компании
✅ Рекомендовать курсы для развития нужных навыков  
✅ Составить пошаговый план карьерного роста
✅ Показать, какие навыки нужно подтянуть

Хотите начать с заполнения профиля?"""

            return {
                "response": response,
                "response_type": "profile_completion_required",
                "actions": [
                    {"type": "navigate", "target": "/candidate/profile", "label": "Заполнить профиль"}
                ],
                "quick_replies": [
                    "Покажи мой прогресс",
                    "Какие навыки нужны для Senior?",
                    "Покажи доступные курсы"
                ],
                "confidence": 0.9
            }
        else:
            # Профиль заполнен - даем рекомендации по развитию
            courses = await self._recommend_courses(user, db, goal=message)
            vacancies = await self._find_relevant_vacancies(user, db)
            
            course_recommendations = []
            for course in courses[:3]:
                course_recommendations.append({
                    "type": "course",
                    "id": course.id,
                    "title": course.title,
                    "category": course.category,
                    "skills": course.skills[:3] if course.skills else []
                })

            response = f"""Отличный вопрос о карьерном развитии! 🚀

На основе анализа вашего профиля, вот мой план действий:

**📚 Рекомендуемые курсы:**
{chr(10).join([f"• {course.title} ({course.category})" for course in courses[:3]])}

**🎯 Подходящие вакансии в компании:**
{chr(10).join([f"• {vacancy.title}" + (f" — {int(similarity*100)}% совпадение" if similarity > 0.5 else "") for vacancy, similarity in vacancies[:2]])}

**📈 Следующие шаги:**
1. Пройти ключевые курсы по недостающим навыкам
2. Обновить профиль новыми компетенциями  
3. Откликнуться на подходящие внутренние вакансии
4. Получить обратную связь от текущего руководителя

Хотите подробнее обсудить конкретный курс или вакансию?"""

            return {
                "response": response,
                "response_type": "career_guidance",
                "recommendations": course_recommendations,
                "actions": [
                    {"type": "navigate", "target": "/candidate/vacancies", "label": "Смотреть вакансии"},
                    {"type": "show_courses", "courses": [c.id for c in courses[:3]], "label": "Изучить курсы"}
                ],
                "quick_replies": [
                    "Расскажи про Senior позиции",
                    "Какие навыки самые важные?",
                    "Покажи план развития"
                ],
                "confidence": 0.85
            }

    async def _handle_general_question(self, user: User, db: Session, message: str, profile_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка общих вопросов к ассистенту.
        Использует LLM для генерации персонализированного ответа.
        """
        # Контекст для LLM на основе профиля пользователя
        user_context = f"""
Профиль пользователя:
- Имя: {profile_analysis['basic_info']['name']}
- Навыки программирования: {', '.join(profile_analysis['skills']['programming_languages']) or 'Не указаны'}
- Прочие навыки: {', '.join(profile_analysis['skills']['other_competencies']) or 'Не указаны'}
- Опыт работы: {profile_analysis['experience']['experience_count']} позиций
- Заполненность профиля: {profile_analysis['completeness']['percentage']}%
- О себе: {profile_analysis['basic_info']['about'] or 'Не заполнено'}
"""

        prompt = f"""
{user_context}

Вопрос пользователя: "{message}"

Дай персонализированный ответ как карьерный консультант. Учитывай профиль пользователя.
Если уместно, рекомендуй курсы или внутренние вакансии.
Отвечай дружелюбно и профессионально, не более 300 слов.
"""

        try:
            ai_response = await self._call_llm(prompt)
            
            # Пытаемся найти релевантные курсы, если в ответе упоминаются технологии
            courses = await self._recommend_courses(user, db, goal=message)
            course_recommendations = []
            
            if courses:
                course_recommendations = [{
                    "type": "course",
                    "id": course.id,
                    "title": course.title,
                    "category": course.category
                } for course in courses[:2]]

            return {
                "response": ai_response,
                "response_type": "general",
                "recommendations": course_recommendations,
                "quick_replies": [
                    "Покажи мои навыки",
                    "Как развиваться дальше?",
                    "Покажи подходящие вакансии"
                ],
                "confidence": 0.7
            }
            
        except Exception as e:
            print(f"❌ LLM error: {e}")
            # Fallback ответ
            return {
                "response": "Спасибо за вопрос! Я анализирую ваш запрос. Пока что рекомендую изучить доступные курсы и внутренние вакансии для развития карьеры.",
                "response_type": "fallback",
                "actions": [
                    {"type": "navigate", "target": "/candidate/vacancies", "label": "Посмотреть вакансии"}
                ],
                "confidence": 0.3
            }


# Глобальный экземпляр сервиса
_ai_assistant_service = None

def get_ai_assistant_service() -> AIAssistantService:
    """Получить экземпляр AI-ассистента"""
    global _ai_assistant_service
    if _ai_assistant_service is None:
        _ai_assistant_service = AIAssistantService()
    return _ai_assistant_service
