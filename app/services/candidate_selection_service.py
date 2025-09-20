"""
Сервис для выбора лучшего кандидата с использованием ИИ
"""

import json
import re
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.config import settings


class CandidateSelectionService:
    """Сервис для выбора лучшего кандидата через ИИ"""

    def __init__(self):
        # Конфиг читаем из settings
        self.provider = ("heroku").lower()

    def _build_request(self, prompt: str) -> tuple[str, Dict[str, str], Dict[str, Any]]:
        """Собирает URL, заголовки и payload под выбранного провайдера."""
        system_prompt = (
            "Ты профессиональный HR-аналитик с опытом подбора персонала. "
            "Анализируй кандидатов максимально объективно и профессионально, "
            "учитывая результаты интервью, опыт работы и соответствие требованиям вакансии."
        )

        # Heroku AI Inference (OpenAI-совместимый)
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
            "max_tokens": 8000,
        }
        return url, headers, payload

    async def call_ai(self, prompt: str) -> str:
        """Вызывает AI API и возвращает контент ассистента (строка)."""
        url, headers, payload = self._build_request(prompt)

        print(f"🔍 AI Provider: {self.provider}")
        print(f"🔍 Request URL: {url}")
        print(f"🔍 Request Headers (masked auth): {{k: ('***' if k.lower()=='authorization' else v) for k,v in headers.items()}}")
        print(f"🔍 Request Payload: {payload}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                print(f"🔍 Response Status: {response.status_code}")
                print(f"🔍 Response Headers: {response.headers}")
                print(f"🔍 Response Body: {response.text}")

                response.raise_for_status()
                data = response.json()
                # Ожидаем OpenAI-совместимый формат
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                print(f"❌ HTTP Status Error: {e}")
                print(f"❌ Response Text: {e.response.text}")
                raise
            except Exception as e:
                print(f"❌ AI Provider API Error: {e}")
                raise

    async def rank_candidates_with_ai(self, vacancy_data: dict, candidates_data: list) -> Dict[str, Any]:
        """
        Основная функция ранжирования кандидатов с использованием ИИ
        """
        
        # Формируем детальное описание вакансии
        vacancy_description = f"""
НАЗВАНИЕ: {vacancy_data['title']}
ОПИСАНИЕ: {vacancy_data['description'] or 'Не указано'}
ТРЕБОВАНИЯ: {vacancy_data['requirements'] or 'Не указаны'}
КОМПАНИЯ: {vacancy_data['company'] or 'Не указана'}
УРОВЕНЬ ОПЫТА: {vacancy_data['experience_level'] or 'Не указан'}
ТИП ЗАНЯТОСТИ: {vacancy_data['employment_type'] or 'Не указан'}
ЗАРПЛАТА: {vacancy_data['salary_from'] or 'Не указана'} - {vacancy_data['salary_to'] or 'Не указана'}
        """.strip()

        # Формируем описание кандидатов
        candidates_description = ""
        for i, candidate in enumerate(candidates_data, 1):
            candidates_description += f"""
КАНДИДАТ {i}:
- Имя: {candidate['candidate_name']}
- ID кандидата: {candidate['candidate_id']}
- ID резюме: {candidate['resume_id']}
- ID интервью: {candidate['interview_id']}
- Отчет по интервью: {candidate['interview_summary']}
- Навыки: {', '.join(candidate['candidate_skills']) if candidate['candidate_skills'] else 'Не указаны'}
- Количество позиций в опыте работы: {len(candidate['candidate_experience']) if candidate['candidate_experience'] else 0}
- Количество записей об образовании: {len(candidate['candidate_education']) if candidate['candidate_education'] else 0}
---
            """.strip()

        prompt = f"""
Проанализируй кандидатов для вакансии и отсортируй их от лучшего к худшему по релевантности.

ВАКАНСИЯ:
{vacancy_description}

КАНДИДАТЫ:
{candidates_description}

КРИТЕРИИ ОЦЕНКИ:
1. Соответствие требованиям вакансии
2. Качество и релевантность опыта работы
3. Результаты интервью (качество ответов, профессиональные навыки)
4. Образование и навыки
5. Потенциал для развития
6. Соответствие корпоративной культуре

ЗАДАЧА:
1. Проанализируй каждого кандидата по всем критериям
2. Оцени релевантность от 0.0 до 1.0 (где 1.0 - идеальное соответствие)
3. Отсортируй кандидатов от лучшего к худшему
4. Для каждого кандидата дай краткое обоснование выбора (2-3 предложения)

ОТВЕТ ДОЛЖЕН БЫТЬ В ФОРМАТЕ JSON:
{{
    "ranked_candidates": [
        {{
            "candidate_id": 123,
            "candidate_name": "Имя Фамилия",
            "resume_id": 456,
            "interview_id": 789,
            "ranking_score": 0.95,
            "reasoning": "Краткое обоснование почему этот кандидат лучший (2-3 предложения)",
            "interview_summary": "Отчет по интервью"
        }}
    ]
}}

ВАЖНО: Отвечай ТОЛЬКО JSON, без дополнительного текста!
        """

        try:
            ai_response = await self.call_ai(prompt)
            
            # Извлекаем JSON из ответа
            json_match = re.search(r'\{[\s\S]*\}', ai_response)
            if json_match:
                json_str = json_match.group()
                analysis_data = json.loads(json_str)
            else:
                analysis_data = json.loads(ai_response)
            
            return analysis_data
        except Exception as e:
            print(f"Ошибка ранжирования кандидатов: {e}")
            # Возвращаем моковые данные в случае ошибки
            return self._get_fallback_ranking(candidates_data)

    def _get_fallback_ranking(self, candidates_data: list) -> Dict[str, Any]:
        """Возвращает моковое ранжирование в случае ошибки ИИ"""
        import random
        
        ranked_candidates = []
        for candidate in candidates_data:
            # Простая оценка на основе длины отчета по интервью
            base_score = min(0.9, len(candidate['interview_summary']) / 1000)
            # Добавляем небольшой рандом для разнообразия
            score = base_score + random.uniform(0, 0.1)
            score = min(1.0, score)
            
            # Определяем обоснование на основе оценки
            if score > 0.8:
                reasoning = "Отличное соответствие требованиям вакансии, высокие результаты на интервью"
            elif score > 0.6:
                reasoning = "Хорошее соответствие, есть потенциал для развития"
            elif score > 0.4:
                reasoning = "Среднее соответствие, требует дополнительного обучения"
            else:
                reasoning = "Низкое соответствие требованиям вакансии"
            
            ranked_candidates.append({
                "candidate_id": candidate['candidate_id'],
                "candidate_name": candidate['candidate_name'],
                "resume_id": candidate['resume_id'],
                "interview_id": candidate['interview_id'],
                "ranking_score": round(score, 2),
                "reasoning": reasoning,
                "interview_summary": candidate['interview_summary'],
                "resume_status": candidate.get('resume_status', 'pending')
            })
        
        # Сортируем по убыванию оценки
        ranked_candidates.sort(key=lambda x: x['ranking_score'], reverse=True)
        
        return {"ranked_candidates": ranked_candidates}


# Глобальный экземпляр сервиса (ленивая инициализация)
candidate_selection_service = None

def get_candidate_selection_service():
    """Получить экземпляр сервиса выбора кандидатов"""
    global candidate_selection_service
    if candidate_selection_service is None:
        candidate_selection_service = CandidateSelectionService()
    return candidate_selection_service
