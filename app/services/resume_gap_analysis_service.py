"""
Сервис для анализа резюме и выявления пробелов для дозаполнения через AI аватара
"""

import json
import httpx
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from app.config import settings
from app.models import User, ResumeAnalysis


class ResumeGapAnalysisService:
    """Сервис для анализа резюме и выявления пробелов для дозаполнения"""

    def __init__(self):
        self.provider = ("scibox").lower()

    def _build_request(self, prompt: str) -> tuple[str, Dict[str, str], Dict[str, Any]]:
        """Собирает URL, заголовки и payload под выбранного провайдера."""
        system_prompt = (
            "Ты профессиональный HR-консультант, который анализирует резюме и выявляет пробелы в информации. "
            "Твоя задача - определить, какая информация отсутствует или недостаточно детализирована, "
            "чтобы составить план вопросов для AI-интервьюера."
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
            "max_tokens": 3000,
        }

        return url, headers, payload

    async def analyze_resume_gaps(self, user: User, resume_analysis: Optional[ResumeAnalysis] = None) -> Dict[str, Any]:
        """
        Анализирует резюме пользователя и выявляет пробелы для дозаполнения
        """
        try:
            # Формируем информацию о пользователе и резюме
            profile_info = self._format_user_profile_for_gap_analysis(user, resume_analysis)
            
            prompt = f"""
Проанализируй профиль пользователя и данные из резюме, затем определи пробелы в информации, которые нужно заполнить через AI-интервью.

ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ:
{profile_info}

ПРАВИЛА АНАЛИЗА ПРОБЕЛОВ:
1. Определи отсутствующие или недостаточно детализированные разделы
2. Выяви пробелы в профессиональном опыте, навыках, образовании
3. Проверь наличие обязательных полей (дата рождения, телефон, местоположение)
4. Оцени качество описания проектов и достижений
5. Определи приоритет заполнения пробелов

КАТЕГОРИИ ДЛЯ АНАЛИЗА:
- Личная информация (имя, контакты, дата рождения)
- Профессиональный опыт (детализация обязанностей, проектов, достижений)
- Навыки и компетенции (программирование, технологии, инструменты)
- Образование (детализация, дополнительные курсы)
- Дополнительная информация (языки, сертификаты, хобби)

ВАЖНО: Верни ТОЛЬКО валидный JSON без дополнительного текста, комментариев или markdown блоков.

{{
  "gaps_analysis": {{
    "personal_info": {{
      "missing_fields": ["birth_date", "phone"],
      "incomplete_fields": ["about"],
      "priority": "high"
    }},
    "professional_experience": {{
      "missing_fields": [],
      "incomplete_fields": ["detailed_responsibilities", "achievements", "technologies_used"],
      "priority": "high"
    }},
    "skills": {{
      "missing_fields": ["foreign_languages"],
      "incomplete_fields": ["programming_languages", "other_competencies"],
      "priority": "medium"
    }},
    "education": {{
      "missing_fields": [],
      "incomplete_fields": ["additional_courses", "certifications"],
      "priority": "low"
    }}
  }},
  "interview_plan": {{
    "total_questions": 8,
    "estimated_duration_minutes": 15,
    "focus_areas": [
      "Детализация профессионального опыта",
      "Уточнение навыков и технологий",
      "Дополнение личной информации"
    ]
  }},
  "missing_required_fields": ["birth_date", "phone"],
  "suggested_questions": [
    "Расскажите подробнее о вашем опыте работы с Python. Какие конкретные проекты вы разрабатывали?",
    "Укажите вашу дату рождения для корректного оформления документов",
    "Какие технологии и инструменты вы используете в работе?",
    "Расскажите о ваших достижениях в последней компании",
    "Укажите ваш контактный телефон для связи"
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
                        gaps_data = json.loads(cleaned_content)
                        return gaps_data
                    except json.JSONDecodeError as e:
                        print(f"❌ Ошибка парсинга JSON ответа: {e}")
                        print(f"Контент: {content}")
                        return self._get_default_gaps_analysis()
                else:
                    print(f"❌ Ошибка API: {response.status_code} - {response.text}")
                    return self._get_default_gaps_analysis()
                    
        except Exception as e:
            print(f"❌ Ошибка анализа пробелов резюме: {e}")
            return self._get_default_gaps_analysis()

    def _format_user_profile_for_gap_analysis(self, user: User, resume_analysis: Optional[ResumeAnalysis] = None) -> str:
        """Форматирует профиль пользователя для анализа пробелов"""
        profile_parts = []
        
        # Основная информация
        profile_parts.append("=== ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ===")
        profile_parts.append(f"Имя: {user.first_name or 'НЕ УКАЗАНО'}")
        profile_parts.append(f"Фамилия: {user.last_name or 'НЕ УКАЗАНО'}")
        profile_parts.append(f"Телефон: {user.phone or 'НЕ УКАЗАН'}")
        profile_parts.append(f"Дата рождения: {user.birth_date or 'НЕ УКАЗАНА'}")
        profile_parts.append(f"Местоположение: {user.location or 'НЕ УКАЗАНО'}")
        profile_parts.append(f"О себе: {user.about or 'НЕ УКАЗАНО'}")
        profile_parts.append(f"Желаемая зарплата: {user.desired_salary or 'НЕ УКАЗАНА'}")
        profile_parts.append(f"Готов к переезду: {user.ready_to_relocate or 'НЕ УКАЗАНО'}")
        
        # Навыки
        if user.programming_languages:
            profile_parts.append(f"Языки программирования: {', '.join(user.programming_languages)}")
        else:
            profile_parts.append("Языки программирования: НЕ УКАЗАНЫ")
        
        if user.other_competencies:
            profile_parts.append(f"Другие компетенции: {', '.join(user.other_competencies)}")
        else:
            profile_parts.append("Другие компетенции: НЕ УКАЗАНЫ")
        
        if user.foreign_languages:
            langs = []
            for lang in user.foreign_languages:
                if isinstance(lang, dict):
                    langs.append(f"{lang.get('language', '')} ({lang.get('level', '')})")
                else:
                    langs.append(str(lang))
            profile_parts.append(f"Иностранные языки: {', '.join(langs)}")
        else:
            profile_parts.append("Иностранные языки: НЕ УКАЗАНЫ")
        
        # Опыт работы
        if user.work_experience:
            profile_parts.append(f"\n=== ОПЫТ РАБОТЫ ===")
            for exp in user.work_experience:
                if isinstance(exp, dict):
                    profile_parts.append(f"• {exp.get('position', '')} в {exp.get('company', '')} ({exp.get('period', '')})")
                    if exp.get('description'):
                        profile_parts.append(f"  {exp.get('description', '')}")
        else:
            profile_parts.append("\n=== ОПЫТ РАБОТЫ: НЕ УКАЗАН ===")
        
        # Образование
        if user.education:
            profile_parts.append(f"\n=== ОБРАЗОВАНИЕ ===")
            for edu in user.education:
                if isinstance(edu, dict):
                    profile_parts.append(f"• {edu.get('degree', '')} по специальности {edu.get('field', '')} в {edu.get('institution', '')} ({edu.get('period', '')})")
        else:
            profile_parts.append("\n=== ОБРАЗОВАНИЕ: НЕ УКАЗАНО ===")
        
        # Данные из анализа резюме (если есть)
        if resume_analysis:
            profile_parts.append(f"\n=== АНАЛИЗ РЕЗЮМЕ ===")
            profile_parts.append(f"Найденные навыки: {', '.join(resume_analysis.key_skills or [])}")
            profile_parts.append(f"Технологии: {', '.join(resume_analysis.technologies or [])}")
            profile_parts.append(f"Проекты: {', '.join(resume_analysis.projects or [])}")
            profile_parts.append(f"Достижения: {', '.join(resume_analysis.achievements or [])}")
            profile_parts.append(f"Отсутствующие навыки: {', '.join(resume_analysis.missing_skills or [])}")
        
        return "\n".join(profile_parts)

    def _get_default_gaps_analysis(self) -> Dict[str, Any]:
        """Возвращает анализ пробелов по умолчанию"""
        return {
            "gaps_analysis": {
                "personal_info": {
                    "missing_fields": ["birth_date", "phone"],
                    "incomplete_fields": ["about"],
                    "priority": "high"
                },
                "professional_experience": {
                    "missing_fields": [],
                    "incomplete_fields": ["detailed_responsibilities", "achievements"],
                    "priority": "high"
                },
                "skills": {
                    "missing_fields": ["foreign_languages"],
                    "incomplete_fields": ["programming_languages", "other_competencies"],
                    "priority": "medium"
                },
                "education": {
                    "missing_fields": [],
                    "incomplete_fields": [],
                    "priority": "low"
                }
            },
            "interview_plan": {
                "total_questions": 6,
                "estimated_duration_minutes": 12,
                "focus_areas": [
                    "Детализация профессионального опыта",
                    "Уточнение навыков и технологий",
                    "Дополнение личной информации"
                ]
            },
            "missing_required_fields": ["birth_date", "phone"],
            "suggested_questions": [
                "Расскажите подробнее о ваших основных навыках программирования. Какие технологии вы используете?",
                "Укажите вашу дату рождения для корректного оформления документов",
                "Расскажите о вашем опыте работы. Какие проекты были наиболее интересными?",
                "Какие дополнительные технологии и инструменты вы используете в работе?",
                "Укажите ваш контактный телефон для связи",
                "Расскажите о ваших профессиональных достижениях"
            ]
        }

    async def generate_interview_questions(self, gaps_analysis: Dict[str, Any], user: User) -> List[Dict[str, Any]]:
        """
        Генерирует конкретные вопросы для AI-интервью на основе анализа пробелов
        """
        try:
            prompt = f"""
На основе анализа пробелов в профиле пользователя сгенерируй конкретные вопросы для AI-интервьюера.

АНАЛИЗ ПРОБЕЛОВ:
{json.dumps(gaps_analysis, ensure_ascii=False, indent=2)}

ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:
{self._format_user_profile_for_gap_analysis(user)}

ПРАВИЛА ГЕНЕРАЦИИ ВОПРОСОВ:
1. Фокусируйся на заполнении выявленных пробелов
2. Задавай конкретные, уточняющие вопросы
3. Приоритизируй обязательные поля (дата рождения, телефон)
4. Детализируй профессиональный опыт и навыки
5. Избегай общих вопросов, будь специфичным
6. Максимум 8 вопросов
7. Запрещены вопросы о личных данных (адрес, семейное положение)

ВАЖНО: Верни ТОЛЬКО валидный JSON без дополнительного текста, комментариев или markdown блоков.

{{
  "questions": [
    {{
      "id": "q1",
      "question": "Расскажите подробнее о вашем опыте работы с Python. Какие конкретные проекты вы разрабатывали?",
      "field": "programming_languages",
      "category": "skills",
      "priority": "high",
      "max_attempts": 3
    }},
    {{
      "id": "q2", 
      "question": "Укажите вашу дату рождения для корректного оформления документов",
      "field": "birth_date",
      "category": "personal_info",
      "priority": "high",
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
                        return gaps_analysis.get("suggested_questions", [])
                else:
                    print(f"❌ Ошибка API: {response.status_code} - {response.text}")
                    return gaps_analysis.get("suggested_questions", [])
                    
        except Exception as e:
            print(f"❌ Ошибка генерации вопросов: {e}")
            return gaps_analysis.get("suggested_questions", [])


# Создаем глобальный экземпляр сервиса
resume_gap_analysis_service = ResumeGapAnalysisService()

def get_resume_gap_analysis_service() -> ResumeGapAnalysisService:
    """Возвращает экземпляр сервиса анализа пробелов резюме"""
    return resume_gap_analysis_service
