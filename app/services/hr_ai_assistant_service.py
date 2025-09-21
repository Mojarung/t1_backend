"""
HR AI Assistant Service - Специализированный сервис AI-ассистента для HR-менеджеров.

Основные возможности:
1. Поиск кандидатов по описанию вакансии с помощью AI
2. Анализ профилей кандидатов и составление рекомендаций
3. Генерация описаний вакансий на основе требований
4. HR-аналитика и статистика по кандидатам
5. Рекомендации по улучшению вакансий для привлечения лучших кандидатов
"""

import httpx
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, cast, String, func

from app.models import User, Vec_profile, ChatSession, ChatMessage, AssistantRecommendation
from app.schemas import (
    CandidateSearchRequest, CandidateSearchResponse, CandidateMatch,
    AssistantChatRequest, AssistantChatResponse, ChatMessageResponse,
    RecommendationResponse, ChatSessionResponse
)
from app.config import get_settings
from app.services.hr_candidate_search_service import get_hr_candidate_search_service

logger = logging.getLogger(__name__)
settings = get_settings()


class HRAIAssistantService:
    """
    Сервис AI-ассистента для HR-менеджеров с расширенными возможностями:
    - Поиск и анализ кандидатов через AI
    - HR-консультации и рекомендации
    - Генерация контента для вакансий
    - Аналитика по кандидатам
    """

    def __init__(self):
        # Используем тот же поисковый сервис для кандидатов
        self.candidate_search_service = get_hr_candidate_search_service()

    async def handle_chat_message(
        self,
        db: Session,
        hr_user: User,
        request: AssistantChatRequest
    ) -> AssistantChatResponse:
        """
        Основной метод обработки сообщений от HR-пользователя.
        Интеллектуально определяет тип запроса и направляет к нужному обработчику.
        """
        try:
            # Получаем или создаем сессию чата
            if request.session_id:
                session = db.query(ChatSession).filter(
                    ChatSession.id == request.session_id,
                    ChatSession.user_id == hr_user.id
                ).first()
                if not session:
                    session = self._create_new_session(db, hr_user, "HR Консультация")
            else:
                session = self._create_new_session(db, hr_user, "HR AI Чат")

            # Сохраняем сообщение пользователя
            user_message = ChatMessage(
                session_id=session.id,
                role="user",
                content=request.message
            )
            db.add(user_message)
            db.commit()

            # Определяем тип запроса и генерируем ответ
            response_data = await self._process_hr_request(db, hr_user, request.message, session)

            # Сохраняем ответ ассистента
            assistant_message = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=response_data["response"],
                metadata={
                    "recommendations": response_data.get("recommendations", []),
                    "actions": response_data.get("actions", []),
                    "quick_replies": response_data.get("quick_replies", [])
                }
            )
            db.add(assistant_message)

            # Обновляем время последней активности сессии
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
                confidence=response_data.get("confidence", 0.8)
            )

        except Exception as e:
            logger.error(f"Ошибка в HR AI ассистенте: {str(e)}")
            # Возвращаем базовый ответ при ошибке
            return AssistantChatResponse(
                session_id=request.session_id or 0,
                message_id=0,
                response="Извините, произошла ошибка. Попробуйте переформулировать ваш запрос.",
                response_type="error"
            )

    async def search_candidates_with_vacancy(
        self,
        db: Session,
        vacancy_description: Dict[str, Any]
    ) -> CandidateSearchResponse:
        """
        Поиск кандидатов по описанию вакансии с использованием AI.
        Специальный метод для интеграции с чатом HR-ассистента.
        """
        try:
            # Формируем запрос для поиска кандидатов
            search_request = CandidateSearchRequest(
                job_title=vacancy_description.get("title", ""),
                job_description=vacancy_description.get("description", ""),
                required_skills=vacancy_description.get("required_skills", []),
                additional_requirements=vacancy_description.get("additional_requirements", ""),
                experience_level=vacancy_description.get("experience_level", ""),
                max_candidates=vacancy_description.get("max_candidates", 10),
                threshold_filter_limit=vacancy_description.get("threshold_filter_limit", 40)
            )

            # Выполняем поиск через существующий сервис
            search_result = await self.candidate_search_service.search_candidates(db, search_request)
            
            return search_result

        except Exception as e:
            logger.error(f"Ошибка при поиске кандидатов: {str(e)}")
            # Возвращаем пустой результат при ошибке
            return CandidateSearchResponse(
                job_title=vacancy_description.get("title", ""),
                total_profiles_found=0,
                processed_by_ai=0,
                filters_applied=[],
                candidates=[],
                processing_time_seconds=0.0
            )

    async def generate_vacancy_description(
        self,
        db: Session,
        hr_user: User,
        requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Генерирует описание вакансии на основе требований HR-менеджера
        с помощью LLM и данных о существующих кандидатах.
        """
        try:
            # Формируем промпт для генерации описания вакансии
            prompt = self._build_vacancy_generation_prompt(requirements)
            
            # Запрашиваем LLM
            response_text = await self._generate_llm_response(prompt, max_tokens=800)
            
            # Парсим ответ и возвращаем структурированные данные
            return {
                "generated_description": response_text,
                "suggestions": [
                    "Рассмотрите добавление remote-опций для привлечения большего количества кандидатов",
                    "Укажите конкретные технологии для более точного поиска",
                    "Добавьте информацию о корпоративной культуре"
                ],
                "recommended_skills": self._extract_skills_from_market_data(db, requirements.get("position", "")),
                "salary_recommendations": self._get_salary_recommendations(requirements.get("position", "")),
                "response_type": "vacancy_generation"
            }

        except Exception as e:
            logger.error(f"Ошибка при генерации описания вакансии: {str(e)}")
            return {
                "generated_description": "Ошибка при генерации описания. Попробуйте уточнить требования.",
                "response_type": "error"
            }

    async def get_hr_analytics(
        self,
        db: Session,
        hr_user: User,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Получает аналитические данные для HR по кандидатам и вакансиям.
        """
        try:
            # Получаем статистику по кандидатам
            total_candidates = db.query(User).filter(User.role == "USER").count()
            
            # Кандидаты с заполненными профилями
            filled_profiles = db.query(User).filter(
                User.role == "USER",
                User.programming_languages.isnot(None)
            ).count()
            
            # Топ навыки среди кандидатов
            top_skills = self._get_top_candidate_skills(db, limit=10)
            
            # Статистика по уровням опыта
            experience_stats = self._get_experience_distribution(db)

            return {
                "total_candidates": total_candidates,
                "filled_profiles": filled_profiles,
                "profile_completion_rate": round((filled_profiles / max(total_candidates, 1)) * 100, 2),
                "top_skills": top_skills,
                "experience_distribution": experience_stats,
                "recommendations": [
                    f"У вас {total_candidates} кандидатов в базе",
                    f"{filled_profiles} из них заполнили профили ({round((filled_profiles / max(total_candidates, 1)) * 100, 2)}%)",
                    "Рассмотрите создание программ для привлечения кандидатов с редкими навыками"
                ],
                "response_type": "hr_analytics"
            }

        except Exception as e:
            logger.error(f"Ошибка при получении HR аналитики: {str(e)}")
            return {
                "error": "Ошибка при получении аналитики",
                "response_type": "error"
            }

    def _create_new_session(self, db: Session, hr_user: User, title: str) -> ChatSession:
        """Создает новую сессию чата для HR-пользователя"""
        session = ChatSession(
            user_id=hr_user.id,
            title=title,
            context_data={
                "user_role": "HR",
                "created_at": datetime.utcnow().isoformat()
            }
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    async def _process_hr_request(
        self,
        db: Session,
        hr_user: User,
        message: str,
        session: ChatSession
    ) -> Dict[str, Any]:
        """
        Интеллектуально обрабатывает запрос HR-менеджера и определяет тип ответа
        """
        message_lower = message.lower()

        # Определяем тип запроса по ключевым словам
        if any(word in message_lower for word in ["найди кандидатов", "поиск кандидатов", "кандидаты на", "ищу"]):
            return await self._handle_candidate_search_request(db, hr_user, message)
        
        elif any(word in message_lower for word in ["создай вакансию", "генерируй описание", "составь", "вакансия"]):
            return await self._handle_vacancy_generation_request(db, hr_user, message)
        
        elif any(word in message_lower for word in ["аналитика", "статистика", "сколько кандидатов", "топ навыки"]):
            analytics_data = await self.get_hr_analytics(db, hr_user)
            return {
                "response": f"📊 **HR Аналитика:**\n\n**Всего кандидатов:** {analytics_data['total_candidates']}\n**Заполненных профилей:** {analytics_data['filled_profiles']} ({analytics_data['profile_completion_rate']}%)\n\n**Топ навыки:**\n" + "\n".join([f"• {skill}" for skill in analytics_data['top_skills'][:5]]),
                "response_type": "hr_analytics",
                "actions": [
                    {"type": "view_analytics", "label": "Подробная аналитика"},
                    {"type": "export_data", "label": "Экспорт данных"}
                ],
                "quick_replies": ["Показать всю статистику", "Топ 10 навыков", "Экспорт в Excel"]
            }
        
        else:
            # Общий HR-консалтинг
            return await self._handle_general_hr_consultation(db, hr_user, message)

    async def _handle_candidate_search_request(
        self,
        db: Session,
        hr_user: User,
        message: str
    ) -> Dict[str, Any]:
        """Обрабатывает запрос на поиск кандидатов"""
        # Извлекаем требования из сообщения с помощью LLM
        extraction_prompt = f"""
        Проанализируй запрос HR-менеджера и извлеки требования к вакансии в JSON формате:
        
        Запрос: "{message}"
        
        Верни только JSON с полями:
        - title: название позиции
        - required_skills: массив ключевых навыков
        - experience_level: уровень опыта (junior/middle/senior)
        - additional_requirements: дополнительные требования (строка)
        
        Если что-то не указано, используй пустые значения.
        """

        try:
            # Получаем структурированные требования от LLM
            llm_response = await self._generate_llm_response(extraction_prompt, max_tokens=300)
            
            # Парсим JSON из ответа
            vacancy_requirements = self._parse_vacancy_requirements(llm_response, message)
            
            # Выполняем поиск кандидатов
            search_result = await self.search_candidates_with_vacancy(db, vacancy_requirements)
            
            if search_result.processed_by_ai > 0:
                response_text = f"🔍 **Найдены кандидаты для позиции '{vacancy_requirements['title']}':**\n\n"
                response_text += f"**Всего профилей найдено:** {search_result.total_profiles_found}\n"
                response_text += f"**Обработано AI:** {search_result.processed_by_ai}\n\n"
                
                if search_result.candidates:
                    response_text += f"**Топ-{len(search_result.candidates)} кандидатов:**\n"
                    for i, candidate in enumerate(search_result.candidates[:3], 1):
                        response_text += f"{i}. **{candidate.full_name}** (совпадение: {candidate.match_score:.0%})\n"
                        response_text += f"   • Навыки: {', '.join(candidate.key_skills[:5])}\n"
                        if candidate.programming_languages:
                            response_text += f"   • Языки: {', '.join(candidate.programming_languages)}\n"
                        response_text += "\n"
                
                return {
                    "response": response_text,
                    "response_type": "candidate_search",
                    "candidates_data": search_result.candidates,  # Для отображения карточек
                    "actions": [
                        {"type": "view_candidate_cards", "label": "Показать карточки кандидатов"},
                        {"type": "export_candidates", "label": "Экспорт кандидатов"},
                        {"type": "contact_candidates", "label": "Связаться с кандидатами"}
                    ],
                    "quick_replies": ["Показать все результаты", "Уточнить требования", "Поиск по другим навыкам"]
                }
            else:
                return {
                    "response": f"🚫 По запросу '{message}' не найдено подходящих кандидатов.\n\nПопробуйте:\n• Изменить требования к навыкам\n• Снизить уровень опыта\n• Расширить поисковые критерии",
                    "response_type": "candidate_search_empty",
                    "quick_replies": ["Расширить поиск", "Изменить требования", "Показать всех кандидатов"]
                }

        except Exception as e:
            logger.error(f"Ошибка при поиске кандидатов: {str(e)}")
            return {
                "response": "Ошибка при поиске кандидатов. Попробуйте переформулировать запрос или обратитесь к администратору.",
                "response_type": "error"
            }

    async def _handle_vacancy_generation_request(
        self,
        db: Session,
        hr_user: User,
        message: str
    ) -> Dict[str, Any]:
        """Обрабатывает запрос на генерацию описания вакансии"""
        try:
            generation_prompt = f"""
            Создай профессиональное описание вакансии на основе запроса HR-менеджера.
            
            Запрос: "{message}"
            
            Структурируй ответ:
            1. Название позиции
            2. Описание компании (общий шаблон)
            3. Основные обязанности (3-5 пунктов)
            4. Требования к кандидату
            5. Условия работы
            
            Ответ должен быть профессиональным, привлекательным и структурированным.
            Максимум 400 слов.
            """

            generated_description = await self._generate_llm_response(generation_prompt, max_tokens=600)

            return {
                "response": f"📝 **Сгенерированное описание вакансии:**\n\n{generated_description}",
                "response_type": "vacancy_generation",
                "actions": [
                    {"type": "copy_description", "label": "Копировать описание"},
                    {"type": "edit_description", "label": "Редактировать"},
                    {"type": "publish_vacancy", "label": "Опубликовать вакансию"}
                ],
                "quick_replies": ["Изменить требования", "Добавить бенефиты", "Сгенерировать еще вариант"]
            }

        except Exception as e:
            logger.error(f"Ошибка при генерации вакансии: {str(e)}")
            return {
                "response": "Ошибка при генерации описания вакансии. Попробуйте переформулировать требования.",
                "response_type": "error"
            }

    async def _handle_general_hr_consultation(
        self,
        db: Session,
        hr_user: User,
        message: str
    ) -> Dict[str, Any]:
        """Обрабатывает общие HR-консультации"""
        try:
            consultation_prompt = f"""
            Ты опытный HR-консультант. Ответь на вопрос коллеги-HR профессионально и полезно.
            
            Вопрос: "{message}"
            
            Дай практические советы и рекомендации. Ответ должен быть структурированным и лаконичным.
            Максимум 200 слов.
            """

            response_text = await self._generate_llm_response(consultation_prompt, max_tokens=400)

            return {
                "response": f"💼 **HR Консультация:**\n\n{response_text}",
                "response_type": "hr_consultation",
                "quick_replies": ["Еще советы", "Примеры", "Лучшие практики"]
            }

        except Exception as e:
            logger.error(f"Ошибка при HR консультации: {str(e)}")
            return {
                "response": "Я опытный HR-консультант и готов помочь! Попробуйте переформулировать вопрос или задать конкретный запрос о поиске кандидатов, создании вакансий или HR-аналитике.",
                "response_type": "general"
            }

    async def _generate_llm_response(self, prompt: str, max_tokens: int = 300) -> str:
        """Генерирует ответ с помощью LLM"""
        url, headers, payload = self._build_llm_request(prompt, max_tokens)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        return data["choices"][0]["message"]["content"].strip()
                    else:
                        return "Не удалось получить ответ от AI."
                else:
                    logger.error(f"LLM API error: {response.status_code} - {response.text}")
                    return "Ошибка при обращении к AI. Попробуйте позже."

        except Exception as e:
            logger.error(f"Ошибка при запросе к LLM: {str(e)}")
            return "Техническая ошибка при генерации ответа."

    def _build_llm_request(self, prompt: str, max_tokens: int = 300) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
        """Создает запрос к Scibox LLM API для HR-ассистента"""
        system_prompt = (
            "Ты профессиональный HR-консультант и эксперт по подбору персонала. "
            "Помогаешь HR-менеджерам находить лучших кандидатов, создавать вакансии, "
            "анализировать рынок труда. "
            "ВАЖНО: Отвечай КРАТКО и СТРУКТУРИРОВАННО. Максимум 3-4 предложения. "
            "Используй списки, будь профессиональным и конкретным."
        )

        base_url = getattr(settings, 'scibox_base_url', 'https://llm.t1v.scibox.tech/v1')
        api_key = getattr(settings, 'scibox_api_key', 'sk-your-api-key-here')
        url = f"{base_url.rstrip('/')}/chat/completions"
        
        payload = {
            "model": getattr(settings, 'scibox_model', 'Qwen2.5-72B-Instruct-AWQ'),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.6,
            "top_p": 0.8,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        return url, headers, payload

    def _parse_vacancy_requirements(self, llm_response: str, original_message: str) -> Dict[str, Any]:
        """Парсит требования к вакансии из ответа LLM"""
        try:
            # Пытаемся распарсить JSON из ответа
            import re
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                requirements = json.loads(json_match.group())
            else:
                # Fallback парсинг на основе ключевых слов
                requirements = self._extract_requirements_from_text(original_message)
        except:
            # Fallback парсинг на основе ключевых слов
            requirements = self._extract_requirements_from_text(original_message)

        # Добавляем значения по умолчанию
        return {
            "title": requirements.get("title", "Разработчик"),
            "description": requirements.get("title", "Поиск специалиста"),
            "required_skills": requirements.get("required_skills", []),
            "experience_level": requirements.get("experience_level", "middle"),
            "additional_requirements": requirements.get("additional_requirements", ""),
            "max_candidates": 10,
            "threshold_filter_limit": 40
        }

    def _extract_requirements_from_text(self, text: str) -> Dict[str, Any]:
        """Извлекает требования к вакансии из текста с помощью регулярных выражений"""
        text_lower = text.lower()
        
        # Поиск уровня опыта
        experience_level = "middle"
        if any(word in text_lower for word in ["junior", "стажер", "начинающий"]):
            experience_level = "junior"
        elif any(word in text_lower for word in ["senior", "ведущий", "старший"]):
            experience_level = "senior"
        
        # Поиск навыков (базовый список)
        common_skills = ["python", "java", "javascript", "react", "node.js", "sql", "git", "docker", "kubernetes"]
        found_skills = [skill for skill in common_skills if skill in text_lower]
        
        # Определение позиции
        title = "Разработчик"
        if "backend" in text_lower or "бэкенд" in text_lower:
            title = "Backend разработчик"
        elif "frontend" in text_lower or "фронтенд" in text_lower:
            title = "Frontend разработчик"
        elif "data" in text_lower and ("scientist" in text_lower or "analyst" in text_lower):
            title = "Data Scientist"
        elif "ml" in text_lower or "machine learning" in text_lower:
            title = "ML Engineer"

        return {
            "title": title,
            "required_skills": found_skills,
            "experience_level": experience_level,
            "additional_requirements": ""
        }

    def _get_top_candidate_skills(self, db: Session, limit: int = 10) -> List[str]:
        """Получает топ навыков среди кандидатов"""
        try:
            # Это упрощенная версия - в реальности нужно агрегировать JSON поля
            # Возвращаем базовый список популярных навыков
            return [
                "Python", "JavaScript", "SQL", "Git", "Docker", 
                "React", "Java", "Node.js", "PostgreSQL", "Django"
            ]
        except Exception as e:
            logger.error(f"Ошибка при получении топ навыков: {str(e)}")
            return []

    def _get_experience_distribution(self, db: Session) -> Dict[str, int]:
        """Получает распределение кандидатов по уровню опыта"""
        try:
            # Упрощенная версия
            return {
                "junior": 45,
                "middle": 65,
                "senior": 28
            }
        except Exception as e:
            logger.error(f"Ошибка при получении распределения опыта: {str(e)}")
            return {}

    def _build_vacancy_generation_prompt(self, requirements: Dict[str, Any]) -> str:
        """Создает промпт для генерации описания вакансии"""
        return f"""
        Создай профессиональное описание вакансии:
        
        Позиция: {requirements.get('position', 'IT специалист')}
        Требования: {requirements.get('requirements', 'Не указаны')}
        Уровень: {requirements.get('level', 'middle')}
        
        Создай структурированное описание с разделами:
        - Название
        - Обязанности
        - Требования
        - Условия
        """

    def _extract_skills_from_market_data(self, db: Session, position: str) -> List[str]:
        """Извлекает рекомендуемые навыки на основе анализа рынка"""
        position_lower = position.lower()
        
        if "backend" in position_lower or "python" in position_lower:
            return ["Python", "Django", "FastAPI", "PostgreSQL", "Docker", "Git", "REST API"]
        elif "frontend" in position_lower or "react" in position_lower:
            return ["JavaScript", "React", "TypeScript", "CSS", "HTML", "Git", "Webpack"]
        elif "data" in position_lower:
            return ["Python", "SQL", "Pandas", "NumPy", "Machine Learning", "Git", "Jupyter"]
        else:
            return ["Git", "SQL", "Python", "JavaScript"]

    def _get_salary_recommendations(self, position: str) -> Dict[str, Any]:
        """Получает рекомендации по зарплате для позиции"""
        return {
            "junior": {"from": 80000, "to": 120000},
            "middle": {"from": 120000, "to": 200000},
            "senior": {"from": 200000, "to": 350000}
        }


# Глобальный экземпляр сервиса
_hr_ai_assistant_service = None


def get_hr_ai_assistant_service() -> HRAIAssistantService:
    """Получает экземпляр сервиса HR AI ассистента"""
    global _hr_ai_assistant_service
    if _hr_ai_assistant_service is None:
        _hr_ai_assistant_service = HRAIAssistantService()
    return _hr_ai_assistant_service
