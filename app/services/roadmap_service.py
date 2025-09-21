from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import User, DevelopmentRoadmap
from app.services.xp_service import xp_service
import httpx
import json
from app.config import settings


class RoadmapService:
    """Сервис генерации и хранения роадмапа развития пользователя."""

    def __init__(self) -> None:
        self.provider = "scibox"

    async def generate_for_user(self, db: Session, user: User) -> Dict[str, Any]:
        """
        Генерирует карту развития для пользователя через LLM, если профиль заполнен на 60%+.
        Сохраняет и возвращает JSON-карту.
        """
        xp_info = xp_service.calculate_user_xp(user)
        if xp_info.get("completion_percentage", 0) < 60:
            raise ValueError("Профиль заполнен менее чем на 60%")

        prompt = self._build_prompt_from_profile(user)
        roadmap_json = await self._call_llm(prompt)

        # Валидация минимальной структуры
        if not isinstance(roadmap_json, dict) or "nodes" not in roadmap_json or "edges" not in roadmap_json:
            raise ValueError("LLM вернул некорректный формат роадмапа")

        # Сохранение в БД (upsert по user_id)
        existing = db.query(DevelopmentRoadmap).filter(DevelopmentRoadmap.user_id == user.id).first()
        if existing:
            existing.roadmap = roadmap_json
        else:
            db.add(DevelopmentRoadmap(user_id=user.id, roadmap=roadmap_json))
        db.commit()

        return roadmap_json

    def get_for_user(self, db: Session, user: User) -> Optional[Dict[str, Any]]:
        record = db.query(DevelopmentRoadmap).filter(DevelopmentRoadmap.user_id == user.id).first()
        return record.roadmap if record else None

    def _build_prompt_from_profile(self, user: User) -> str:
        # Краткое текстовое представление профиля
        parts = []
        name = user.full_name or f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}".strip() or user.username
        parts.append(f"Профиль кандидата: {name}")
        if user.about:
            parts.append(f"О себе: {user.about}")
        if user.programming_languages:
            parts.append(f"ЯП: {', '.join(user.programming_languages or [])}")
        if user.other_competencies:
            parts.append(f"Навыки: {', '.join(user.other_competencies or [])}")
        if user.work_experience:
            parts.append(f"Опыт позиций: {len(user.work_experience or [])}")
        if user.education:
            parts.append(f"Образование записей: {len(user.education or [])}")

        profile_text = ". ".join(parts)

        schema_hint = (
            "Сгенерируй игровой роадмап развития кандидата в формате JSON. "
            "Граф должен содержать вершины (nodes) и ребра (edges), поддерживать ветвления и различные статусы. "
            "Допускай типы узлов: main, branch, optional. Для каждого узла укажи: id (int), title, description, status in ['locked','available','in_progress','completed'], type, xp_reward (int). "
            "Для ребер укажи: from (int), to (int), condition (строка условия, например 'completion_of_<id>' или 'choose_backend_path'). "
            "Учти текущий профиль и предложи 2-3 возможных ветки развития от текущего уровня." 
            "Ответь ТОЛЬКО валидным JSON, без пояснений."
        )

        example = {
            "nodes": [
                {"id": 1, "title": "Start", "description": "Текущая роль и состояние", "status": "completed", "type": "main", "xp_reward": 10},
                {"id": 2, "title": "Усилить алгоритмы и структуры данных", "description": "Практика задач", "status": "available", "type": "branch", "xp_reward": 20},
                {"id": 3, "title": "Путь Backend: продвинутая работа с БД", "description": "Индексы, профилирование", "status": "locked", "type": "branch", "xp_reward": 30}
            ],
            "edges": [
                {"from": 1, "to": 2, "condition": "completion_of_1"},
                {"from": 2, "to": 3, "condition": "completion_of_2"}
            ]
        }

        return (
            f"{schema_hint}\n\nПрофиль:\n{profile_text}\n\nПример формата:\n{json.dumps(example, ensure_ascii=False)}"
        )

    async def _call_llm(self, prompt: str) -> Dict[str, Any]:
        url = f"{settings.scibox_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {settings.scibox_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": settings.scibox_model or "Qwen2.5-72B-Instruct-AWQ",
            "messages": [
                {"role": "system", "content": "Ты карьерный консультант и геймдизайнер прогресс-деревьев."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1200,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]

        # Извлечь чистый JSON
        try:
            return json.loads(text)
        except Exception:
            import re
            m = re.search(r"\{[\s\S]*\}", text)
            if not m:
                raise ValueError("Не удалось распарсить JSON из ответа LLM")
            return json.loads(m.group())


_roadmap_service: Optional[RoadmapService] = None


def get_roadmap_service() -> RoadmapService:
    global _roadmap_service
    if _roadmap_service is None:
        _roadmap_service = RoadmapService()
    return _roadmap_service


