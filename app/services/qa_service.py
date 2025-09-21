"""
Сервис для генерации вопросов QA-сессии и анализа ответов пользователя
"""

import json
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.config import settings
from app.models import User


class QAService:
    """Сервис для генерации вопросов и анализа ответов в QA-сессии"""

    def __init__(self):
        self.provider = ("scibox").lower()

    def _build_request(self, prompt: str) -> tuple[str, Dict[str, str], Dict[str, Any]]:
        """Собирает URL, заголовки и payload под выбранного провайдера."""
        system_prompt = (
            "Ты профессиональный HR-консультант, который помогает кандидатам улучшить их профиль. "
            "Твоя задача - задавать релевантные, конкретные вопросы для уточнения и расширения информации о навыках и опыте работы. "
            "Будь вежливым, но настойчивым в получении качественной информации."
        )

        if self.provider == "scibox":
            url = settings.scibox_base_url or "http://176.119.5.23:4000/v1"
            api_key = settings.scibox_api_key or "sk-qyu9jfUQ5rpT5RqfjyEjlg"
            model = settings.scibox_model or "Qwen2.5-72B-Instruct-AWQ"
            
            if not url.endswith("/chat/completions"):
                url = url.rstrip("/") + "/chat/completions"
        else:
            url = settings.heroku_ai_base_url or ""
            api_key = settings.heroku_ai_api_key or ""
            model = settings.heroku_ai_model or "gpt-4o-mini"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 2000,
        }

        return url, headers, payload

    async def generate_questions(self, user: User, resume_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Генерирует список вопросов для QA-сессии на основе профиля пользователя и данных резюме
        """
        try:
            # Формируем информацию о пользователе
            profile_info = self._format_user_profile_for_qa(user, resume_data)
            
            prompt = f"""
Проанализируй профиль пользователя и данные из резюме, затем сгенерируй 5-7 релевантных вопросов для уточнения и расширения информации.

ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ:
{profile_info}

ПРАВИЛА ГЕНЕРАЦИИ ВОПРОСОВ:
1. Фокусируйся на уточнении навыков, опыта работы и профессиональных компетенций
2. Задавай конкретные вопросы о технологиях, проектах, достижениях
3. Если в резюме упомянута компания, спроси о конкретных обязанностях и проектах
4. Проверь наличие обязательных полей (дата рождения, телефон, местоположение)
5. Избегай общих вопросов, будь специфичным
6. Максимум 7 вопросов, приоритет - самые важные для HR

ВАЖНО: Верни ТОЛЬКО валидный JSON без дополнительного текста, комментариев или markdown блоков.

{{
  "questions": [
    {{
      "id": "q1",
      "question": "Расскажите подробнее о вашем опыте работы с Python. Какие проекты вы разрабатывали?",
      "field": "programming_languages",
      "required": false,
      "max_attempts": 3
    }},
    {{
      "id": "q2", 
      "question": "Укажите вашу дату рождения для корректного оформления документов",
      "field": "birth_date",
      "required": true,
      "max_attempts": 3
    }}
  ]
}}
"""

            url, headers, payload = self._build_request(prompt)
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    try:
                        # Очищаем контент от markdown блоков и лишнего текста
                        cleaned_content = content.strip()
                        
                        # Убираем markdown блоки
                        if '```json' in cleaned_content:
                            start = cleaned_content.find('```json') + 7
                            end = cleaned_content.find('```', start)
                            if end != -1:
                                cleaned_content = cleaned_content[start:end]
                        elif '```' in cleaned_content:
                            start = cleaned_content.find('```') + 3
                            end = cleaned_content.find('```', start)
                            if end != -1:
                                cleaned_content = cleaned_content[start:end]
                        
                        # Ищем JSON объект в тексте
                        if '{' in cleaned_content and '}' in cleaned_content:
                            start = cleaned_content.find('{')
                            end = cleaned_content.rfind('}') + 1
                            cleaned_content = cleaned_content[start:end]
                        
                        cleaned_content = cleaned_content.strip()
                        
                        # Парсим JSON ответ
                        qa_data = json.loads(cleaned_content)
                        questions = qa_data.get("questions", [])
                        
                        # Добавляем current_attempt для каждого вопроса
                        for i, question in enumerate(questions):
                            question["current_attempt"] = 0
                            question["id"] = f"q{i+1}"
                        
                        return questions
                    except json.JSONDecodeError as e:
                        print(f"❌ Ошибка парсинга JSON ответа: {e}")
                        print(f"Контент: {content}")
                        return self._get_default_questions()
                else:
                    print(f"❌ Ошибка API: {response.status_code} - {response.text}")
                    return self._get_default_questions()
                    
        except Exception as e:
            print(f"❌ Ошибка генерации вопросов: {e}")
            return self._get_default_questions()

    def _format_user_profile_for_qa(self, user: User, resume_data: Dict[str, Any]) -> str:
        """Форматирует профиль пользователя для анализа"""
        profile_parts = []
        
        # Основная информация
        profile_parts.append("=== ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ===")
        profile_parts.append(f"Имя: {user.first_name or 'Не указано'}")
        profile_parts.append(f"Фамилия: {user.last_name or 'Не указано'}")
        profile_parts.append(f"Телефон: {user.phone or 'Не указан'}")
        profile_parts.append(f"Дата рождения: {user.birth_date or 'Не указана'}")
        profile_parts.append(f"Местоположение: {user.location or 'Не указано'}")
        profile_parts.append(f"О себе: {user.about or 'Не указано'}")
        
        # Навыки
        if user.programming_languages:
            profile_parts.append(f"Языки программирования: {', '.join(user.programming_languages)}")
        
        if user.other_competencies:
            profile_parts.append(f"Другие компетенции: {', '.join(user.other_competencies)}")
        
        if user.foreign_languages:
            langs = []
            for lang in user.foreign_languages:
                if isinstance(lang, dict):
                    langs.append(f"{lang.get('language', '')} ({lang.get('level', '')})")
                else:
                    langs.append(str(lang))
            profile_parts.append(f"Иностранные языки: {', '.join(langs)}")
        
        # Опыт работы
        if user.work_experience:
            profile_parts.append(f"\n=== ОПЫТ РАБОТЫ ===")
            for exp in user.work_experience:
                if isinstance(exp, dict):
                    profile_parts.append(f"• {exp.get('position', '')} в {exp.get('company', '')} ({exp.get('period', '')})")
                    if exp.get('description'):
                        profile_parts.append(f"  {exp.get('description', '')}")
        
        # Образование
        if user.education:
            profile_parts.append(f"\n=== ОБРАЗОВАНИЕ ===")
            for edu in user.education:
                if isinstance(edu, dict):
                    profile_parts.append(f"• {edu.get('degree', '')} по специальности {edu.get('field', '')} в {edu.get('institution', '')} ({edu.get('period', '')})")
        
        return "\n".join(profile_parts)

    def _get_default_questions(self) -> List[Dict[str, Any]]:
        """Возвращает список вопросов по умолчанию"""
        return [
            {
                "id": "q1",
                "question": "Расскажите подробнее о ваших основных навыках программирования. Какие технологии вы используете?",
                "field": "programming_languages",
                "required": False,
                "max_attempts": 3,
                "current_attempt": 0
            },
            {
                "id": "q2",
                "question": "Укажите вашу дату рождения для корректного оформления документов",
                "field": "birth_date",
                "required": True,
                "max_attempts": 3,
                "current_attempt": 0
            },
            {
                "id": "q3",
                "question": "Расскажите о вашем опыте работы. Какие проекты были наиболее интересными?",
                "field": "work_experience",
                "required": False,
                "max_attempts": 3,
                "current_attempt": 0
            },
            {
                "id": "q4",
                "question": "Какие дополнительные технологии и инструменты вы используете в работе?",
                "field": "other_competencies",
                "required": False,
                "max_attempts": 3,
                "current_attempt": 0
            },
            {
                "id": "q5",
                "question": "Укажите ваш контактный телефон для связи",
                "field": "phone",
                "required": True,
                "max_attempts": 3,
                "current_attempt": 0
            }
        ]

    async def analyze_answer(self, question: Dict[str, Any], answer: str, user: User) -> Dict[str, Any]:
        """
        Анализирует ответ пользователя и возвращает обновления для профиля
        """
        try:
            prompt = f"""
Проанализируй ответ пользователя на вопрос и определи, какую информацию можно извлечь для обновления профиля.

ВОПРОС: {question['question']}
ПОЛЕ ПРОФИЛЯ: {question['field']}
ОТВЕТ ПОЛЬЗОВАТЕЛЯ: {answer}

ПРАВИЛА АНАЛИЗА:
1. Если ответ информативный и содержит полезную информацию - извлеки её
2. Если ответ неинформативный или слишком краткий - верни флаг для переспроса
3. Для дат используй формат YYYY-MM-DD
4. Для списков навыков (programming_languages, other_competencies) возвращай МАССИВ строк, а не строку с запятыми
5. Для foreign_languages возвращай массив объектов с полями language и level
6. Будь строгим к качеству информации

ВАЖНО: Верни ТОЛЬКО валидный JSON без дополнительного текста, комментариев или markdown блоков.

{{
  "is_informative": true,
  "profile_update": {{
    "programming_languages": ["Python", "JavaScript", "Java"],
    "other_competencies": ["Git", "Docker", "AWS"],
    "birth_date": "1990-01-01"
  }},
  "suggestion": ""
}}
"""

            url, headers, payload = self._build_request(prompt)
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    try:
                        # Очищаем контент от markdown блоков и лишнего текста
                        cleaned_content = content.strip()
                        
                        # Убираем markdown блоки
                        if '```json' in cleaned_content:
                            start = cleaned_content.find('```json') + 7
                            end = cleaned_content.find('```', start)
                            if end != -1:
                                cleaned_content = cleaned_content[start:end]
                        elif '```' in cleaned_content:
                            start = cleaned_content.find('```') + 3
                            end = cleaned_content.find('```', start)
                            if end != -1:
                                cleaned_content = cleaned_content[start:end]
                        
                        # Ищем JSON объект в тексте
                        if '{' in cleaned_content and '}' in cleaned_content:
                            start = cleaned_content.find('{')
                            end = cleaned_content.rfind('}') + 1
                            cleaned_content = cleaned_content[start:end]
                        
                        cleaned_content = cleaned_content.strip()
                        
                        analysis = json.loads(cleaned_content)
                        return analysis
                    except json.JSONDecodeError as e:
                        print(f"❌ Ошибка парсинга JSON ответа: {e}")
                        print(f"Контент: {content}")
                        return {
                            "is_informative": False,
                            "profile_update": {},
                            "suggestion": "Не удалось обработать ответ. Пожалуйста, попробуйте еще раз."
                        }
                else:
                    print(f"❌ Ошибка API: {response.status_code} - {response.text}")
                    return {
                        "is_informative": False,
                        "profile_update": {},
                        "suggestion": "Произошла ошибка при обработке ответа."
                    }
                    
        except Exception as e:
            print(f"❌ Ошибка анализа ответа: {e}")
            return {
                "is_informative": False,
                "profile_update": {},
                "suggestion": "Произошла ошибка при обработке ответа."
            }


# Создаем глобальный экземпляр сервиса
qa_service = QAService()

def get_qa_service() -> QAService:
    """Возвращает экземпляр сервиса QA"""
    return qa_service
