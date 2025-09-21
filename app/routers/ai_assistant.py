"""
AI Assistant Router - API эндпоинты для персонального карьерного ассистента

Предоставляет полный набор эндпоинтов для работы с AI-ассистентом:
- Управление сессиями чата
- Отправка сообщений и получение ответов
- Специализированные карьерные советы  
- Рекомендации курсов и вакансий
- Статистика работы ассистента
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func, or_, String
from typing import List, Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.auth import get_current_user
from app.models import (
    User, ChatSession, ChatMessage, Course, AssistantRecommendation, UserRole
)
from app.schemas import (
    # Chat schemas
    ChatSessionCreate, ChatSessionResponse, ChatMessageResponse,
    AssistantChatRequest, AssistantChatResponse,
    # Specialized schemas
    CourseRecommendationRequest, CourseRecommendationResponse,
    CareerGuidanceRequest, CareerGuidanceResponse,
    CourseResponse, AssistantStatsResponse
)
from app.services.ai_assistant_service import get_ai_assistant_service

router = APIRouter()

@router.post("/chat", response_model=AssistantChatResponse)
async def send_message_to_assistant(
    request: AssistantChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    🤖 Основной эндпоинт для общения с AI-ассистентом
    
    Отправляет сообщение ассистенту и получает персонализированный ответ
    с рекомендациями на основе профиля пользователя.
    
    Особенности:
    - Автоматическое создание сессии чата при первом обращении
    - Анализ профиля для персонализации ответов
    - Специальная обработка вопросов о карьерном росте
    - RAG-поиск релевантных вакансий и курсов
    - Рекомендации по заполнению профиля
    """
    try:
        print(f"🤖 AI Assistant chat request from user {current_user.id}")
        
        # Получаем сервис AI-ассистента
        assistant_service = get_ai_assistant_service()
        
        # Обрабатываем сообщение
        response = await assistant_service.process_chat_message(request, current_user, db)
        
        return response
        
    except Exception as e:
        print(f"❌ AI Assistant error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обработке сообщения: {str(e)}"
        )

@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_chat_sessions(
    limit: int = Query(10, ge=1, le=50),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    📝 Получить список сессий чата с ассистентом
    
    Возвращает историю чатов пользователя с основной информацией:
    - Заголовок сессии
    - Время последней активности  
    - Количество сообщений
    - Статус сессии
    """
    try:
        # Получаем сессии пользователя с подсчетом сообщений
        sessions = db.query(
            ChatSession,
            func.count(ChatMessage.id).label('messages_count')
        ).outerjoin(ChatMessage).filter(
            ChatSession.user_id == current_user.id
        ).group_by(ChatSession.id).order_by(
            desc(ChatSession.last_activity_at)
        ).offset(skip).limit(limit).all()
        
        # Формируем ответ
        result = []
        for session, messages_count in sessions:
            session_data = ChatSessionResponse(
                id=session.id,
                user_id=session.user_id,
                title=session.title,
                status=session.status,
                context_data=session.context_data,
                last_activity_at=session.last_activity_at,
                created_at=session.created_at,
                updated_at=session.updated_at,
                messages_count=messages_count or 0
            )
            result.append(session_data)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении сессий: {str(e)}"
        )

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_chat_messages(
    session_id: int,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    💬 Получить историю сообщений в конкретной сессии чата
    
    Возвращает все сообщения в хронологическом порядке:
    - Сообщения пользователя
    - Ответы ассистента  
    - Системные сообщения
    - Метаданные с рекомендациями
    """
    try:
        # Проверяем, что сессия принадлежит пользователю
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Сессия чата не найдена"
            )
        
        # Получаем сообщения
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at).offset(skip).limit(limit).all()
        
        return messages
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении сообщений: {str(e)}"
        )

@router.post("/career-guidance", response_model=CareerGuidanceResponse) 
async def get_career_guidance(
    request: CareerGuidanceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    🚀 Специализированный эндпоинт для карьерных советов
    
    Предоставляет детальные рекомендации по карьерному развитию:
    - Анализ текущего профиля и навыков
    - Пошаговый план развития  
    - Рекомендации конкретных курсов
    - Оценка готовности к следующему уровню
    - Советы по заполнению профиля
    """
    try:
        assistant_service = get_ai_assistant_service()
        
        # Анализируем профиль пользователя
        profile_analysis = assistant_service._analyze_user_profile(current_user)
        
        # Получаем рекомендуемые курсы
        recommended_courses = await assistant_service._recommend_courses(
            current_user, db, goal=request.target_position
        )
        
        # Формируем детальный совет
        if not profile_analysis["completeness"]["is_complete"]:
            # Профиль не заполнен - советуем дозаполнить
            advice = f"""Для достижения позиции "{request.target_position or 'желаемой должности'}" необходимо сначала полностью заполнить профиль.
            
Ваш профиль заполнен на {profile_analysis['completeness']['percentage']}%. Это недостаточно для качественных рекомендаций."""

            action_plan = [
                "Заполните недостающие поля в профиле",
                "Добавьте все ваши навыки и технологии",
                "Опишите опыт работы и образование", 
                "Вернитесь за персональными рекомендациями"
            ]
            
            missing_fields_ru = {
                "first_name": "Имя",
                "last_name": "Фамилия",
                "about": "О себе", 
                "location": "Местоположение",
                "programming_languages": "Языки программирования",
                "other_competencies": "Навыки",
                "work_experience": "Опыт работы",
                "education": "Образование"
            }
            
            missing_profile_fields = [
                missing_fields_ru.get(field, field) 
                for field in profile_analysis["completeness"]["missing_fields"]
            ]
            
        else:
            # Профиль заполнен - даем конкретные советы
            current_skills = profile_analysis["skills"]["programming_languages"] + profile_analysis["skills"]["other_competencies"]
            
            advice = f"""Отлично! Ваш профиль заполнен на {profile_analysis['completeness']['percentage']}%.
            
На основе анализа ваших навыков ({', '.join(current_skills[:5])}) рекомендую следующий план развития для достижения позиции "{request.target_position or 'следующего уровня'}"."""

            action_plan = [
                "Изучите рекомендованные курсы ниже",
                "Обновите профиль новыми навыками после изучения",
                "Откликайтесь на внутренние вакансии",
                "Получите обратную связь от текущего руководителя",
                "Участвуйте в проектах с новыми технологиями"
            ]
            
            missing_profile_fields = []

        return CareerGuidanceResponse(
            advice=advice,
            action_plan=action_plan,
            courses=[CourseResponse(
                id=course.id,
                title=course.title,
                category=course.category,
                description=course.description,
                skills=course.skills,
                technologies=course.technologies,
                level=course.level,
                duration_hours=course.duration_hours,
                search_keywords=course.search_keywords
            ) for course in recommended_courses],
            profile_completeness=profile_analysis["completeness"]["percentage"],
            missing_profile_fields=missing_profile_fields
        )
        
    except Exception as e:
        print(f"❌ Career guidance error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении карьерных советов: {str(e)}"
        )

@router.post("/course-recommendations", response_model=CourseRecommendationResponse)
async def get_course_recommendations(
    request: CourseRecommendationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    📚 Получить персонализированные рекомендации курсов
    
    Анализирует профиль пользователя и цели развития,
    возвращает наиболее подходящие курсы с объяснением выбора.
    
    Алгоритм:
    - Анализирует текущие навыки пользователя
    - Определяет пробелы в знаниях для достижения цели
    - Подбирает курсы для заполнения этих пробелов
    - Формирует оптимальный порядок изучения
    """
    try:
        assistant_service = get_ai_assistant_service()
        
        # Получаем рекомендации курсов
        recommended_courses = await assistant_service._recommend_courses(
            current_user, db, 
            goal=request.goal,
            limit=request.max_recommendations
        )
        
        # Анализируем профиль для объяснения
        profile_analysis = assistant_service._analyze_user_profile(current_user)
        current_skills = profile_analysis["skills"]["programming_languages"] + profile_analysis["skills"]["other_competencies"]
        
        # Генерируем объяснение выбора
        if recommended_courses:
            explanation = f"""На основе ваших текущих навыков ({', '.join(current_skills[:3]) if current_skills else 'навыки не указаны'}) и цели "{request.goal or 'общее развитие'}", рекомендую следующие курсы.

Они помогут вам освоить недостающие компетенции и достичь поставленной цели."""
        else:
            explanation = "К сожалению, подходящие курсы не найдены. Рекомендуем заполнить профиль более подробно."
        
        # Формируем путь обучения
        learning_path = [course.title for course in recommended_courses[:3]]
        
        # Оцениваем время изучения
        total_hours = sum(course.duration_hours or 40 for course in recommended_courses)
        estimated_time = f"Примерно {total_hours} часов ({total_hours//20} недель по 20 часов в неделю)"
        
        return CourseRecommendationResponse(
            courses=[CourseResponse(
                id=course.id,
                title=course.title,
                category=course.category,
                description=course.description,
                skills=course.skills,
                technologies=course.technologies,
                level=course.level,
                duration_hours=course.duration_hours,
                search_keywords=course.search_keywords
            ) for course in recommended_courses],
            explanation=explanation,
            learning_path=learning_path,
            estimated_time=estimated_time
        )
        
    except Exception as e:
        print(f"❌ Course recommendations error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении рекомендаций курсов: {str(e)}"
        )

@router.get("/courses", response_model=List[CourseResponse])
async def get_available_courses(
    category: Optional[str] = Query(None, description="Фильтр по категории курса"),
    level: Optional[str] = Query(None, description="Фильтр по уровню (junior, middle, senior)"),
    search: Optional[str] = Query(None, description="Поиск по названию и ключевым словам"),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    📖 Получить список доступных курсов с фильтрацией
    
    Поддерживаемые фильтры:
    - По категории (Backend Development, Frontend Development, etc.)
    - По уровню (junior, middle, senior)
    - Текстовый поиск по названию и ключевым словам
    """
    try:
        query = db.query(Course).filter(Course.is_active == True)
        
        # Применяем фильтры
        if category:
            query = query.filter(Course.category == category)
        
        if level:
            query = query.filter(Course.level == level)
        
        if search:
            # Поиск по названию и ключевым словам
            search_filter = or_(
                Course.title.ilike(f"%{search}%"),
                Course.description.ilike(f"%{search}%"),
                Course.search_keywords.cast(String).ilike(f"%{search}%")
            )
            query = query.filter(search_filter)
        
        courses = query.offset(skip).limit(limit).all()
        
        return courses
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении курсов: {str(e)}"
        )

@router.get("/stats", response_model=AssistantStatsResponse)
async def get_assistant_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    📊 Статистика использования AI-ассистента
    
    Показывает персональную статистику взаимодействия с ассистентом:
    - Количество сессий и сообщений
    - Выданные и выполненные рекомендации
    - Самые популярные темы вопросов
    """
    try:
        # Подсчитываем статистику
        total_sessions = db.query(ChatSession).filter(
            ChatSession.user_id == current_user.id
        ).count()
        
        total_messages = db.query(ChatMessage).join(ChatSession).filter(
            ChatSession.user_id == current_user.id,
            ChatMessage.role == "user"  # Только сообщения пользователя
        ).count()
        
        recommendations_given = db.query(AssistantRecommendation).filter(
            AssistantRecommendation.user_id == current_user.id
        ).count()
        
        recommendations_completed = db.query(AssistantRecommendation).filter(
            AssistantRecommendation.user_id == current_user.id,
            AssistantRecommendation.status == "completed"
        ).count()
        
        # TODO: В будущем можно добавить анализ тем вопросов
        favorite_topics = ["Карьерное развитие", "Технические навыки", "Курсы"]
        
        return AssistantStatsResponse(
            total_sessions=total_sessions,
            total_messages=total_messages,
            recommendations_given=recommendations_given,
            recommendations_completed=recommendations_completed,
            favorite_topics=favorite_topics
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении статистики: {str(e)}"
        )

@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    🗑️ Удалить сессию чата с ассистентом
    
    Удаляет сессию чата и все связанные сообщения.
    Операция необратима.
    """
    try:
        # Проверяем, что сессия принадлежит пользователю
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Сессия чата не найдена"
            )
        
        # Удаляем сессию (сообщения удалятся автоматически благодаря cascade)
        db.delete(session)
        db.commit()
        
        return {"message": "Сессия чата успешно удалена"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при удалении сессии: {str(e)}"
        )

@router.get("/courses/categories")
async def get_course_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    📂 Получить список доступных категорий курсов
    
    Возвращает уникальные категории курсов для фильтрации.
    """
    try:
        categories = db.query(Course.category).filter(
            Course.is_active == True
        ).distinct().all()
        
        return {"categories": [category[0] for category in categories]}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении категорий: {str(e)}"
        )
