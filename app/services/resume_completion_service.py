"""
Сервис для обработки результатов AI-интервью и автоматического дозаполнения профиля
"""

import json
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, ResumeAnalysis


class ResumeCompletionService:
    """Сервис для обработки результатов AI-интервью и обновления профиля"""

    def __init__(self):
        self.provider = ("scibox").lower()

    def _build_request(self, prompt: str) -> tuple[str, Dict[str, str], Dict[str, Any]]:
        """Собирает URL, заголовки и payload под выбранного провайдера."""
        system_prompt = (
            "Ты профессиональный HR-аналитик, который обрабатывает результаты интервью и структурирует информацию "
            "для автоматического обновления профиля кандидата. Твоя задача - извлечь из диалога интервью "
            "структурированную информацию и подготовить обновления для профиля пользователя."
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
            "temperature": 0.3,  # Низкая температура для более точного извлечения данных
            "max_tokens": 3000,
        }

        return url, headers, payload

    async def process_interview_results(self, dialogue: List[Dict[str, Any]], gaps_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обрабатывает результаты AI-интервью и извлекает структурированную информацию для обновления профиля
        """
        try:
            # Формируем текст диалога
            dialogue_text = self._format_dialogue_for_processing(dialogue)
            
            prompt = f"""
Проанализируй диалог AI-интервью и извлеки структурированную информацию для обновления профиля кандидата.

АНАЛИЗ ПРОБЕЛОВ (что искали):
{json.dumps(gaps_analysis, ensure_ascii=False, indent=2)}

ДИАЛОГ ИНТЕРВЬЮ:
{dialogue_text}

ПРАВИЛА ИЗВЛЕЧЕНИЯ ДАННЫХ:
1. Извлекай ТОЛЬКО информацию, которая была явно упомянута в диалоге
2. Для дат используй формат YYYY-MM-DD
3. Для списков навыков возвращай МАССИВ строк
4. Для foreign_languages возвращай массив объектов с полями language и level
5. Для work_experience и education возвращай массив объектов
6. Будь строгим - не выдумывай информацию
7. Если информация неполная или неясная, не включай её в результат

ВАЖНО: Верни ТОЛЬКО валидный JSON без дополнительного текста, комментариев или markdown блоков.

{{
  "profile_updates": {{
    "personal_info": {{
      "first_name": "Имя или null",
      "last_name": "Фамилия или null", 
      "phone": "Телефон или null",
      "birth_date": "1990-01-01 или null",
      "location": "Город или null",
      "about": "Описание о себе или null"
    }},
    "skills": {{
      "programming_languages": ["Python", "JavaScript"],
      "foreign_languages": [
        {{"language": "English", "level": "Intermediate"}}
      ],
      "other_competencies": ["Git", "Docker", "AWS"]
    }},
    "experience": [
      {{
        "role": "Должность",
        "company": "Компания", 
        "period_start": "2020-01",
        "period_end": "2023-12",
        "responsibilities": "Описание обязанностей",
        "is_current": false
      }}
    ],
    "education": [
      {{
        "institution": "Учебное заведение",
        "degree": "Степень",
        "field": "Специальность",
        "year": "2020"
      }}
    ]
  }},
  "extracted_skills": ["Python", "JavaScript", "React"],
  "extracted_experience": ["Frontend Developer в компании X"],
  "confidence_score": 0.85,
  "summary": "Краткое описание того, что было извлечено из интервью"
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
                        extracted_data = json.loads(cleaned_content)
                        return extracted_data
                    except json.JSONDecodeError as e:
                        print(f"❌ Ошибка парсинга JSON ответа: {e}")
                        print(f"Контент: {content}")
                        return self._get_default_extraction_result()
                else:
                    print(f"❌ Ошибка API: {response.status_code} - {response.text}")
                    return self._get_default_extraction_result()
                    
        except Exception as e:
            print(f"❌ Ошибка обработки результатов интервью: {e}")
            return self._get_default_extraction_result()

    def _format_dialogue_for_processing(self, dialogue: List[Dict[str, Any]]) -> str:
        """Форматирует диалог для обработки AI"""
        formatted_lines = []
        
        for entry in dialogue:
            role = entry.get('role', 'unknown')
            content = entry.get('content', '')
            timestamp = entry.get('timestamp', '')
            
            if role == 'user':
                formatted_lines.append(f"КАНДИДАТ: {content}")
            elif role == 'assistant':
                formatted_lines.append(f"АЛЕКСАНДРА: {content}")
            else:
                formatted_lines.append(f"{role.upper()}: {content}")
        
        return "\n".join(formatted_lines)

    def _get_default_extraction_result(self) -> Dict[str, Any]:
        """Возвращает результат извлечения по умолчанию"""
        return {
            "profile_updates": {
                "personal_info": {},
                "skills": {},
                "experience": [],
                "education": []
            },
            "extracted_skills": [],
            "extracted_experience": [],
            "confidence_score": 0.0,
            "summary": "Не удалось извлечь информацию из интервью"
        }

    async def update_user_profile(self, user: User, profile_updates: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """
        Обновляет профиль пользователя на основе извлеченных данных
        """
        updated_fields = []
        
        try:
            # Обновляем личную информацию
            personal_info = profile_updates.get("personal_info", {})
            for field, value in personal_info.items():
                if value is not None and hasattr(user, field):
                    if field == "birth_date" and isinstance(value, str):
                        try:
                            from datetime import datetime
                            parsed_date = datetime.fromisoformat(value.replace('Z', '+00:00')).date()
                            setattr(user, field, parsed_date)
                            updated_fields.append(field)
                        except ValueError:
                            print(f"Неверный формат даты: {value}")
                            continue
                    else:
                        setattr(user, field, value)
                        updated_fields.append(field)

            # Обновляем навыки
            skills = profile_updates.get("skills", {})
            
            # Программирование
            if "programming_languages" in skills and skills["programming_languages"]:
                current_langs = getattr(user, "programming_languages", []) or []
                new_langs = list(set(current_langs + skills["programming_languages"]))
                setattr(user, "programming_languages", new_langs)
                updated_fields.append("programming_languages")

            # Иностранные языки
            if "foreign_languages" in skills and skills["foreign_languages"]:
                current_langs = getattr(user, "foreign_languages", []) or []
                for lang_data in skills["foreign_languages"]:
                    if isinstance(lang_data, dict) and lang_data not in current_langs:
                        current_langs.append(lang_data)
                setattr(user, "foreign_languages", current_langs)
                updated_fields.append("foreign_languages")

            # Другие компетенции
            if "other_competencies" in skills and skills["other_competencies"]:
                current_comp = getattr(user, "other_competencies", []) or []
                new_comp = list(set(current_comp + skills["other_competencies"]))
                setattr(user, "other_competencies", new_comp)
                updated_fields.append("other_competencies")

            # Обновляем опыт работы
            experience = profile_updates.get("experience", [])
            if experience:
                current_exp = getattr(user, "work_experience", []) or []
                for exp_data in experience:
                    if isinstance(exp_data, dict) and exp_data not in current_exp:
                        current_exp.append(exp_data)
                setattr(user, "work_experience", current_exp)
                updated_fields.append("work_experience")

            # Обновляем образование
            education = profile_updates.get("education", [])
            if education:
                current_edu = getattr(user, "education", []) or []
                for edu_data in education:
                    if isinstance(edu_data, dict) and edu_data not in current_edu:
                        current_edu.append(edu_data)
                setattr(user, "education", current_edu)
                updated_fields.append("education")

            # Сохраняем изменения
            db.commit()
            
            return {
                "success": True,
                "updated_fields": updated_fields,
                "message": f"Профиль обновлен. Изменены поля: {', '.join(updated_fields)}"
            }
            
        except Exception as e:
            db.rollback()
            print(f"❌ Ошибка обновления профиля: {e}")
            return {
                "success": False,
                "updated_fields": [],
                "message": f"Ошибка обновления профиля: {str(e)}"
            }

    async def generate_interview_summary(self, dialogue: List[Dict[str, Any]], profile_updates: Dict[str, Any], gaps_analysis: Dict[str, Any]) -> str:
        """
        Генерирует краткое резюме интервью
        """
        try:
            dialogue_text = self._format_dialogue_for_processing(dialogue)
            
            prompt = f"""
Создай краткое резюме AI-интервью для дозаполнения резюме кандидата.

АНАЛИЗ ПРОБЕЛОВ (что искали):
{json.dumps(gaps_analysis, ensure_ascii=False, indent=2)}

ДИАЛОГ ИНТЕРВЬЮ:
{dialogue_text}

ИЗВЛЕЧЕННЫЕ ДАННЫЕ:
{json.dumps(profile_updates, ensure_ascii=False, indent=2)}

Создай краткое резюме (2-3 предложения) о том:
1. Какие пробелы были выявлены в резюме
2. Какая информация была собрана в интервью
3. Какие поля профиля были обновлены

Резюме должно быть профессиональным и информативным.
"""

            url, headers, payload = self._build_request(prompt)
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return content.strip()
                else:
                    return "Интервью проведено для дозаполнения резюме. Профиль обновлен на основе собранной информации."
                    
        except Exception as e:
            print(f"❌ Ошибка генерации резюме: {e}")
            return "Интервью проведено для дозаполнения резюме. Профиль обновлен на основе собранной информации."


# Создаем глобальный экземпляр сервиса
resume_completion_service = ResumeCompletionService()

def get_resume_completion_service() -> ResumeCompletionService:
    """Возвращает экземпляр сервиса обработки результатов интервью"""
    return resume_completion_service
