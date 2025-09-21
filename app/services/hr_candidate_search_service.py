"""
Сервис для HR-поиска кандидатов с использованием AI и векторного поиска
Реализует алгоритм умной фильтрации и RAG-модель для персонализированного поиска
"""

import json
import re
import httpx
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, String

from app.config import settings
from app.models import User, Vec_profile, UserRole
from app.schemas import CandidateSearchRequest, CandidateSearchResponse, CandidateMatch

# Импорты для работы с векторами и LangChain
import numpy as np
from pgvector.sqlalchemy import Vector


class HRCandidateSearchService:
    """
    Основной сервис для поиска кандидатов через AI-ассистента.
    
    Алгоритм работы:
    1. Применяет базовые фильтры по навыкам и опыту
    2. Если кандидатов слишком много - добавляет дополнительные фильтры
    3. Генерирует векторное представление вакансии
    4. Выполняет векторный поиск по профилям пользователей
    5. LLM анализирует каждого кандидата и генерирует саммари
    6. Возвращает ранжированный список с оценками соответствия
    """

    def __init__(self):
        # Конфигурация LLM провайдера (по умолчанию Scibox)
        self.provider = "scibox"
        self.embedding_dimension = 1024  # Размерность векторов bge-m3

    def _build_llm_request(self, prompt: str, is_embedding: bool = False) -> tuple[str, Dict[str, str], Dict[str, Any]]:
        """
        Создает запрос к LLM API (Scibox).
        Поддерживает как chat completion, так и embeddings endpoints.
        """
        system_prompt = (
            "Ты профессиональный HR-эксперт с опытом подбора IT-персонала. "
            "Анализируй профили кандидатов максимально объективно, учитывая "
            "их навыки, опыт работы, образование и потенциал для развития."
        )

        # Конфигурация для Scibox API
        base_url = getattr(settings, 'scibox_embeddings_base_url', 'https://llm.t1v.scibox.tech/v1')
        api_key = getattr(settings, 'scibox_embeddings_api_key', 'sk-your-api-key-here')
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        if is_embedding:
            # Запрос для получения эмбеддингов
            url = f"{base_url.rstrip('/')}/embeddings"
            payload = {
                "model": "bge-m3",  # Embedding модель
                "input": prompt
            }
        else:
            # Запрос для chat completion
            url = f"{settings.scibox_base_url.rstrip('/')}/chat/completions"
            payload = {
                "model": getattr(settings, 'scibox_model', 'Qwen2.5-72B-Instruct-AWQ'),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 1000,
                "temperature": 0.3,  # Низкая температура для более консистентных результатов
                "top_p": 0.9,
            }
        
        return url, headers, payload

    async def _call_llm(self, prompt: str, is_embedding: bool = False) -> Any:
        """
        Выполняет запрос к LLM API
        """
        url, headers, payload = self._build_llm_request(prompt, is_embedding)

        print(f"🤖 LLM Request: {self.provider}")
        print(f"📍 URL: {url}")
        print(f"📊 Type: {'Embedding' if is_embedding else 'Chat Completion'}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                
                if is_embedding:
                    # Возвращаем вектор эмбеддинга
                    return data["data"][0]["embedding"]
                else:
                    # Возвращаем текст ответа
                    return data["choices"][0]["message"]["content"]
                    
            except httpx.HTTPStatusError as e:
                print(f"❌ HTTP Error: {e.response.status_code} - {e.response.text}")
                raise Exception(f"LLM API Error: {e.response.status_code}")
            except Exception as e:
                print(f"❌ Request Error: {e}")
                raise Exception(f"LLM Request Failed: {str(e)}")

    async def _generate_job_embedding(self, job_description: str, job_title: str) -> List[float]:
        """
        Генерирует векторное представление вакансии для семантического поиска
        """
        # Объединяем название и описание для создания полного контекста
        full_job_context = f"Вакансия: {job_title}\n\nОписание: {job_description}"
        
        try:
            embedding = await self._call_llm(full_job_context, is_embedding=True)
            return embedding
        except Exception as e:
            print(f"❌ Failed to generate job embedding: {e}")
            # Возвращаем нулевой вектор в случае ошибки
            return [0.0] * self.embedding_dimension

    def _apply_basic_filters(self, db: Session, required_skills: List[str], experience_level: Optional[str]) -> Any:
        """
        Применяет базовые фильтры по навыкам и опыту работы.
        Возвращает QuerySet пользователей, соответствующих критериям.
        """
        query = db.query(User).filter(
            User.role == UserRole.USER,  # Только обычные пользователи (не HR)
            User.is_active == True
        )

        # Фильтр по навыкам программирования
        if required_skills and len(required_skills) > 0:
            skill_conditions = []
            for skill in required_skills:
                skill = skill.strip()
                if skill:  # Проверяем, что навык не пустой
                    # Ищем в языках программирования (JSON -> текст)
                    skill_conditions.append(
                        User.programming_languages.cast(String).ilike(f'%{skill}%')
                    )
                    # Ищем в прочих компетенциях (JSON -> текст)  
                    skill_conditions.append(
                        User.other_competencies.cast(String).ilike(f'%{skill}%')
                    )
                    # Ищем в описании "о себе" (обычный текст)
                    skill_conditions.append(
                        User.about.ilike(f'%{skill}%')
                    )
            
            if skill_conditions:
                # Хотя бы один навык должен совпадать
                query = query.filter(or_(*skill_conditions))

        # Фильтр по уровню опыта (опционально)
        if experience_level and experience_level.lower() in ['junior', 'middle', 'senior']:
            # Ищем упоминания уровня в опыте работы или описании
            experience_conditions = []
            exp_level = experience_level.lower()
            
            # Ищем в JSON опыта работы (приводим к тексту)
            experience_conditions.append(
                User.work_experience.cast(String).ilike(f'%{exp_level}%')
            )
            # Ищем в описании "о себе" (обычный текст)
            experience_conditions.append(
                User.about.ilike(f'%{exp_level}%')
            )
            # Ищем конкретные термины по уровню
            if exp_level == 'senior':
                experience_conditions.extend([
                    User.about.ilike('%senior%'),
                    User.about.ilike('%lead%'),
                    User.about.ilike('%архитектор%'),
                    User.work_experience.cast(String).ilike('%senior%'),
                    User.work_experience.cast(String).ilike('%lead%')
                ])
            elif exp_level == 'middle':
                experience_conditions.extend([
                    User.about.ilike('%middle%'),
                    User.about.ilike('%средний%'),
                    User.work_experience.cast(String).ilike('%middle%')
                ])
            elif exp_level == 'junior':
                experience_conditions.extend([
                    User.about.ilike('%junior%'),
                    User.about.ilike('%начинающий%'),
                    User.work_experience.cast(String).ilike('%junior%')
                ])
            
            if experience_conditions:
                query = query.filter(or_(*experience_conditions))

        return query

    def _apply_additional_filters(self, query: Any, additional_keywords: List[str]) -> Any:
        """
        Применяет дополнительные фильтры, если кандидатов слишком много.
        Фильтрует по ключевым словам в описании опыта работы и образовании.
        """
        if additional_keywords and len(additional_keywords) > 0:
            additional_conditions = []
            for keyword in additional_keywords:
                keyword = keyword.strip()
                if keyword:  # Проверяем, что ключевое слово не пустое
                    # Ищем в опыте работы (JSON поле -> текст)
                    additional_conditions.append(
                        User.work_experience.cast(String).ilike(f'%{keyword}%')
                    )
                    # Ищем в образовании (JSON поле -> текст)
                    additional_conditions.append(
                        User.education.cast(String).ilike(f'%{keyword}%')
                    )
                    # Ищем в описании "о себе" (обычный текст)
                    additional_conditions.append(
                        User.about.ilike(f'%{keyword}%')
                    )
                    # Ищем в прочих компетенциях (JSON поле -> текст)
                    additional_conditions.append(
                        User.other_competencies.cast(String).ilike(f'%{keyword}%')
                    )
            
            if additional_conditions:
                # Хотя бы одно дополнительное условие должно выполняться
                query = query.filter(or_(*additional_conditions))

        return query

    async def _perform_vector_search(self, db: Session, job_embedding: List[float], 
                                   filtered_users: List[User], limit: int = 20) -> List[Tuple[User, float]]:
        """
        Выполняет векторный поиск среди отфильтрованных пользователей.
        Если векторные профили отсутствуют, создает их на лету.
        Возвращает список кандидатов с их similarity scores.
        """
        user_ids = [user.id for user in filtered_users]
        
        # Запрос к векторной базе для поиска наиболее похожих профилей
        vector_results = db.query(Vec_profile, User).join(User).filter(
            Vec_profile.user_id.in_(user_ids)
        ).all()

        print(f"🔍 Found {len(vector_results)} users with existing vector profiles")
        
        candidates_with_similarity = []
        users_with_vectors = set()
        
        # Обрабатываем пользователей с существующими векторными профилями
        for vec_profile, user in vector_results:
            similarity = self._cosine_similarity(job_embedding, vec_profile.vector)
            candidates_with_similarity.append((user, similarity))
            users_with_vectors.add(user.id)
            print(f"📊 User {user.id} ({user.full_name or user.username}): similarity = {similarity:.3f}")

        # Для пользователей без векторных профилей создаем профили на лету
        users_without_vectors = [user for user in filtered_users if user.id not in users_with_vectors]
        
        if users_without_vectors:
            print(f"🔄 Creating vector profiles for {len(users_without_vectors)} users...")
            for user in users_without_vectors:
                try:
                    # Создаем векторный профиль на лету
                    user_profile_text = self._create_user_profile_text(user)
                    user_embedding = await self._call_llm(user_profile_text, is_embedding=True)
                    
                    # Сохраняем векторный профиль в базу
                    vec_profile = Vec_profile(
                        user_id=user.id,
                        vector=user_embedding
                    )
                    db.add(vec_profile)
                    
                    # Вычисляем similarity
                    similarity = self._cosine_similarity(job_embedding, user_embedding)
                    candidates_with_similarity.append((user, similarity))
                    print(f"✅ Created vector profile for user {user.id}: similarity = {similarity:.3f}")
                    
                except Exception as e:
                    print(f"❌ Failed to create vector profile for user {user.id}: {e}")
                    # Добавляем с базовой оценкой
                    candidates_with_similarity.append((user, 0.5))
            
            # Сохраняем изменения в базе данных
            try:
                db.commit()
                print(f"✅ Saved {len(users_without_vectors)} new vector profiles")
            except Exception as e:
                db.rollback()
                print(f"❌ Failed to save vector profiles: {e}")

        # Сортируем по убыванию сходства и ограничиваем количество
        candidates_with_similarity.sort(key=lambda x: x[1], reverse=True)
        return candidates_with_similarity[:limit]

    def _create_user_profile_text(self, user: User) -> str:
        """
        Создает текстовое представление профиля пользователя для векторизации
        """
        profile_parts = []
        
        # Основная информация
        if user.full_name:
            profile_parts.append(f"Имя: {user.full_name}")
        
        # О себе
        if user.about:
            profile_parts.append(f"О себе: {user.about}")
        
        # Языки программирования
        if user.programming_languages:
            languages = ', '.join(user.programming_languages) if isinstance(user.programming_languages, list) else str(user.programming_languages)
            profile_parts.append(f"Языки программирования: {languages}")
        
        # Прочие компетенции
        if user.other_competencies:
            competencies = ', '.join(user.other_competencies) if isinstance(user.other_competencies, list) else str(user.other_competencies)
            profile_parts.append(f"Навыки и компетенции: {competencies}")
        
        # Опыт работы
        if user.work_experience and isinstance(user.work_experience, list):
            for i, exp in enumerate(user.work_experience[:3], 1):  # Берем первые 3 позиции
                if isinstance(exp, dict):
                    role = exp.get('role') or exp.get('position', '')
                    company = exp.get('company', '')
                    responsibilities = exp.get('responsibilities', '')
                    
                    exp_text = f"Опыт работы {i}: {role}"
                    if company:
                        exp_text += f" в {company}"
                    if responsibilities:
                        exp_text += f". Обязанности: {responsibilities[:200]}..."  # Обрезаем для краткости
                    
                    profile_parts.append(exp_text)
        
        # Образование
        if user.education and isinstance(user.education, list):
            for i, edu in enumerate(user.education[:2], 1):  # Берем первые 2 записи об образовании
                if isinstance(edu, dict):
                    institution = edu.get('institution', '')
                    degree = edu.get('degree', '')
                    field = edu.get('field_of_study', '') or edu.get('specialty', '')
                    
                    edu_text = f"Образование {i}:"
                    if degree:
                        edu_text += f" {degree}"
                    if field:
                        edu_text += f" по специальности {field}"
                    if institution:
                        edu_text += f", {institution}"
                    
                    profile_parts.append(edu_text)
        
        # Локация
        if user.location:
            profile_parts.append(f"Местоположение: {user.location}")
        
        # Готовность к переезду
        if user.ready_to_relocate:
            profile_parts.append("Готов к переезду")
        
        # Тип занятости
        if user.employment_type:
            profile_parts.append(f"Предпочитаемый тип занятости: {user.employment_type.value}")
        
        # Желаемая зарплата
        if user.desired_salary:
            profile_parts.append(f"Желаемая зарплата: {user.desired_salary}")
        
        # Иностранные языки
        if user.foreign_languages and isinstance(user.foreign_languages, list):
            languages = []
            for lang in user.foreign_languages:
                if isinstance(lang, dict):
                    lang_name = lang.get('language', '')
                    level = lang.get('level', '')
                    if lang_name:
                        lang_text = lang_name
                        if level:
                            lang_text += f" ({level})"
                        languages.append(lang_text)
            
            if languages:
                profile_parts.append(f"Иностранные языки: {', '.join(languages)}")
        
        # Собираем все части в единый текст
        profile_text = '. '.join(filter(None, profile_parts))
        
        # Если профиль пустой, создаем минимальное описание
        if not profile_text.strip():
            profile_text = f"Пользователь {user.username or user.email}, профиль не заполнен"
        
        return profile_text

    def _cosine_similarity(self, vec1: List[float], vec2) -> float:
        """
        Вычисляет косинусное сходство между двумя векторами
        """
        try:
            # Преобразуем в numpy arrays для вычислений
            a = np.array(vec1)
            b = np.array(vec2)
            
            # Косинусное сходство = dot(a,b) / (||a|| * ||b||)
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            similarity = dot_product / (norm_a * norm_b)
            return float(similarity)
        except Exception as e:
            print(f"❌ Similarity calculation error: {e}")
            return 0.0

    async def _analyze_candidate_with_ai(self, user: User, job_description: str, 
                                       job_title: str, similarity_score: float) -> CandidateMatch:
        """
        Анализирует отдельного кандидата с помощью LLM.
        Генерирует детальную оценку соответствия и саммари.
        """
        # Формируем описание кандидата для анализа
        candidate_info = f"""
КАНДИДАТ:
Имя: {user.full_name or f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username}
Email: {user.email}
Локация: {user.location or 'Не указана'}
О себе: {user.about or 'Не указано'}
Желаемая зарплата: {user.desired_salary or 'Не указана'}
Языки программирования: {', '.join(user.programming_languages or []) or 'Не указаны'}
Прочие навыки: {', '.join(user.other_competencies or []) or 'Не указаны'}
Опыт работы: {len(user.work_experience or []) if user.work_experience else 0} позиций
Образование: {len(user.education or []) if user.education else 0} записей
Векторная схожесть с вакансией: {similarity_score:.2f}
        """.strip()

        prompt = f"""
Проанализируй соответствие кандидата требованиям вакансии.

ВАКАНСИЯ:
Название: {job_title}
Описание: {job_description}

{candidate_info}

ЗАДАЧИ:
1. Оцени соответствие кандидата от 0.0 до 1.0 (где 1.0 - идеальное соответствие)
2. Выдели 2-3 основные сильные стороны кандидата
3. Укажи 1-2 области для развития или недостающие навыки
4. Напиши краткое заключение (2-3 предложения)

ОТВЕТ В ФОРМАТЕ JSON:
{{
    "match_score": 0.85,
    "strengths": ["Сильная сторона 1", "Сильная сторона 2"],
    "growth_areas": ["Область для развития 1", "Область для развития 2"],
    "summary": "Краткое заключение об этом кандидате и его соответствии вакансии"
}}

ВАЖНО: Отвечай ТОЛЬКО JSON без дополнительного текста!
        """

        try:
            ai_response = await self._call_llm(prompt)
            
            # Извлекаем JSON из ответа
            json_match = re.search(r'\{[\s\S]*\}', ai_response)
            if json_match:
                analysis_data = json.loads(json_match.group())
            else:
                analysis_data = json.loads(ai_response)

            # Создаем объект CandidateMatch
            return CandidateMatch(
                user_id=user.id,
                full_name=user.full_name or f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                email=user.email,
                current_position=self._extract_current_position(user),
                experience_years=self._calculate_experience_years(user),
                key_skills=user.other_competencies or [],
                programming_languages=user.programming_languages or [],
                match_score=analysis_data.get("match_score", 0.5),
                ai_summary=analysis_data.get("summary", "Анализ недоступен"),
                strengths=analysis_data.get("strengths", []),
                growth_areas=analysis_data.get("growth_areas", []),
                similarity_score=similarity_score
            )

        except Exception as e:
            print(f"❌ AI analysis error for user {user.id}: {e}")
            # Возвращаем базовую оценку в случае ошибки
            return self._create_fallback_candidate_match(user, similarity_score)

    def _extract_current_position(self, user: User) -> Optional[str]:
        """Извлекает текущую позицию из опыта работы"""
        if not user.work_experience:
            return None
        
        # Ищем текущую работу (is_current: true или нет end_date)
        for experience in user.work_experience:
            if isinstance(experience, dict):
                if experience.get('is_current') or not experience.get('period_end'):
                    return experience.get('role') or experience.get('position')
        
        # Если текущая работа не найдена, возвращаем последнюю
        if user.work_experience:
            last_exp = user.work_experience[0] if isinstance(user.work_experience[0], dict) else None
            if last_exp:
                return last_exp.get('role') or last_exp.get('position')
        
        return None

    def _calculate_experience_years(self, user: User) -> Optional[str]:
        """Вычисляет общий опыт работы в годах"""
        if not user.work_experience:
            return None
        
        total_months = 0
        for experience in user.work_experience:
            if isinstance(experience, dict):
                start_date = experience.get('period_start')
                end_date = experience.get('period_end') 
                
                # Простая оценка: если есть даты, считаем разность
                if start_date and end_date:
                    try:
                        # Примерная логика подсчета (можно улучшить)
                        total_months += 12  # Заглушка: считаем год за каждую позицию
                    except:
                        pass
        
        if total_months > 0:
            years = total_months // 12
            return f"{years} лет" if years > 1 else f"{total_months} мес."
        
        return "Опыт не указан"

    def _create_fallback_candidate_match(self, user: User, similarity_score: float) -> CandidateMatch:
        """Создает базовую оценку кандидата при ошибке AI"""
        base_score = min(0.8, similarity_score + 0.2) if similarity_score > 0.5 else similarity_score
        
        return CandidateMatch(
            user_id=user.id,
            full_name=user.full_name or f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
            email=user.email,
            current_position=self._extract_current_position(user),
            experience_years=self._calculate_experience_years(user),
            key_skills=user.other_competencies or [],
            programming_languages=user.programming_languages or [],
            match_score=round(base_score, 2),
            ai_summary="Базовая оценка на основе векторного сходства профиля",
            strengths=["Есть релевантный опыт"] if similarity_score > 0.6 else [],
            growth_areas=["Требует дополнительного анализа"],
            similarity_score=similarity_score
        )

    async def search_candidates(self, db: Session, request: CandidateSearchRequest) -> CandidateSearchResponse:
        """
        Основная функция поиска кандидатов.
        Реализует полный цикл: фильтрация -> векторный поиск -> AI анализ
        """
        start_time = time.time()
        applied_filters = []

        print(f"🔍 Starting candidate search for: {request.job_title}")
        
        # Шаг 1: Применяем базовые фильтры
        print("📋 Applying basic filters...")
        base_query = self._apply_basic_filters(db, request.required_skills, request.experience_level)
        base_candidates = base_query.all()
        
        if request.required_skills:
            applied_filters.append(f"Skills: {', '.join(request.required_skills)}")
        if request.experience_level:
            applied_filters.append(f"Experience: {request.experience_level}")
        
        print(f"📊 Found {len(base_candidates)} candidates after basic filtering")

        # Шаг 2: Дополнительная фильтрация, если слишком много кандидатов
        filtered_candidates = base_candidates
        if len(base_candidates) > request.threshold_filter_limit:
            print(f"⚡ Too many candidates ({len(base_candidates)}), applying additional filters...")
            
            # Извлекаем дополнительные ключевые слова из описания вакансии
            additional_keywords = self._extract_key_terms(request.job_description)
            additional_query = self._apply_additional_filters(base_query, additional_keywords)
            filtered_candidates = additional_query.all()
            
            applied_filters.append(f"Additional keywords: {', '.join(additional_keywords[:3])}")
            print(f"📊 After additional filtering: {len(filtered_candidates)} candidates")

        # Шаг 3: Генерируем векторное представление вакансии
        print("🧠 Generating job embedding...")
        job_embedding = await self._generate_job_embedding(request.job_description, request.job_title)

        # Шаг 4: Векторный поиск среди отфильтрованных кандидатов  
        print("🔎 Performing vector similarity search...")
        candidates_with_similarity = await self._perform_vector_search(
            db, job_embedding, filtered_candidates, request.max_candidates
        )

        # Шаг 5: AI-анализ каждого кандидата
        print(f"🤖 Analyzing {len(candidates_with_similarity)} candidates with AI...")
        analyzed_candidates = []
        
        for user, similarity in candidates_with_similarity:
            try:
                candidate_match = await self._analyze_candidate_with_ai(
                    user, request.job_description, request.job_title, similarity
                )
                analyzed_candidates.append(candidate_match)
            except Exception as e:
                print(f"❌ Failed to analyze candidate {user.id}: {e}")
                # Добавляем базовую оценку
                fallback_match = self._create_fallback_candidate_match(user, similarity)
                analyzed_candidates.append(fallback_match)

        # Шаг 6: Сортируем по финальной оценке AI
        analyzed_candidates.sort(key=lambda x: x.match_score, reverse=True)

        processing_time = time.time() - start_time
        print(f"✅ Search completed in {processing_time:.2f}s")

        return CandidateSearchResponse(
            job_title=request.job_title,
            total_profiles_found=len(filtered_candidates),
            processed_by_ai=len(analyzed_candidates),
            filters_applied=applied_filters,
            candidates=analyzed_candidates,
            processing_time_seconds=round(processing_time, 2)
        )

    def _extract_key_terms(self, text: str) -> List[str]:
        """
        Извлекает ключевые термины из описания вакансии для дополнительной фильтрации
        """
        # Простая эвристика для извлечения ключевых слов
        key_terms = []
        
        # Общие IT термины
        it_terms = [
            'backend', 'frontend', 'fullstack', 'devops', 'qa', 'analyst', 'manager',
            'mobile', 'web', 'api', 'database', 'cloud', 'docker', 'kubernetes',
            'agile', 'scrum', 'team lead', 'architect', 'senior', 'middle', 'junior'
        ]
        
        text_lower = text.lower()
        for term in it_terms:
            if term in text_lower:
                key_terms.append(term)
        
        return key_terms[:5]  # Ограничиваем количество дополнительных терминов


# Глобальный экземпляр сервиса
_hr_search_service = None

def get_hr_candidate_search_service() -> HRCandidateSearchService:
    """Получить экземпляр сервиса поиска кандидатов"""
    global _hr_search_service
    if _hr_search_service is None:
        _hr_search_service = HRCandidateSearchService()
    return _hr_search_service
