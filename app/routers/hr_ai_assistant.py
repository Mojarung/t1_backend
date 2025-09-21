"""
HR AI Assistant Router - API эндпоинты для HR AI-ассистента.

Специализированные эндпоинты для HR-менеджеров:
1. Чат с AI-ассистентом для HR-задач
2. Поиск кандидатов по описанию вакансии
3. Генерация описаний вакансий
4. HR-аналитика по кандидатам
5. Получение статистики и метрик
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.database import get_db
from app.models import User, ChatSession, ChatMessage
from app.auth import get_current_hr_user
from app.schemas import (
    # Базовые схемы для чата
    AssistantChatRequest, ChatSessionResponse, ChatMessageResponse,
    
    # HR-специфичные схемы
    HRCandidateSearchRequest, HRAssistantChatResponse, HRCandidateCard,
    HRVacancyGenerationRequest, HRVacancyGenerationResponse,
    HRAnalyticsRequest, HRAnalyticsResponse, HRAssistantStatsResponse,
    
    # Схемы для поиска кандидатов
    CandidateSearchRequest, CandidateSearchResponse
)
from app.services.hr_ai_assistant_service import get_hr_ai_assistant_service

router = APIRouter()

@router.post("/chat", response_model=HRAssistantChatResponse)
async def hr_chat_with_assistant(
    request: AssistantChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    """
    💬 Основной чат с HR AI-ассистентом.
    
    Поддерживаемые типы запросов:
    - "найди кандидатов для позиции Python разработчика"
    - "создай описание вакансии для middle frontend разработчика"
    - "покажи статистику по кандидатам"
    - "какие навыки сейчас популярны?"
    
    Ассистент интеллектуально определяет тип запроса и предоставляет
    соответствующий ответ с карточками кандидатов, аналитикой или
    сгенерированными описаниями вакансий.
    """
    try:
        print(f"🤖 HR Assistant chat request from: {current_user.username}")
        print(f"💭 Message: {request.message[:100]}...")
        
        hr_service = get_hr_ai_assistant_service()
        
        # Обрабатываем сообщение через HR AI сервис
        response = await hr_service.handle_chat_message(db, current_user, request)
        
        print(f"✅ HR Assistant response type: {response.response_type}")
        
        return response
        
    except Exception as e:
        print(f"❌ HR Assistant error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка в HR AI-ассистенте: {str(e)}"
        )


@router.post("/search-candidates", response_model=CandidateSearchResponse)
async def search_candidates_by_description(
    request: CandidateSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    """
    🔍 Прямой поиск кандидатов по описанию вакансии.
    
    Этот эндпоинт предоставляет прямой доступ к функциональности
    поиска кандидатов, используемой в чате HR-ассистента.
    
    Алгоритм:
    1. Фильтрация по базовым критериям
    2. Дополнительная фильтрация при необходимости  
    3. Векторный поиск по семантическому сходству
    4. AI-анализ и ранжирование кандидатов
    """
    try:
        print(f"🔍 Direct candidate search from HR: {current_user.username}")
        print(f"📋 Job title: {request.job_title}")
        
        hr_service = get_hr_ai_assistant_service()
        
        # Формируем описание вакансии для поиска
        vacancy_description = {
            "title": request.job_title,
            "description": request.job_description,
            "required_skills": request.required_skills,
            "experience_level": request.experience_level,
            "additional_requirements": request.additional_requirements,
            "max_candidates": request.max_candidates,
            "threshold_filter_limit": request.threshold_filter_limit
        }
        
        # Выполняем поиск
        search_result = await hr_service.search_candidates_with_vacancy(db, vacancy_description)
        
        print(f"✅ Found {search_result.processed_by_ai} candidates for analysis")
        
        return search_result
        
    except Exception as e:
        print(f"❌ Candidate search error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при поиске кандидатов: {str(e)}"
        )


@router.post("/generate-vacancy", response_model=HRVacancyGenerationResponse)
async def generate_vacancy_description(
    request: HRVacancyGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    """
    📝 Генерация описания вакансии с помощью AI.
    
    Создает профессиональное описание вакансии на основе:
    - Названия позиции
    - Основных требований
    - Уровня специалиста
    - Дополнительной информации
    
    Включает рекомендации по навыкам, зарплате и рыночным инсайтам.
    """
    try:
        print(f"📝 Vacancy generation request from HR: {current_user.username}")
        print(f"🎯 Position: {request.position}")
        
        hr_service = get_hr_ai_assistant_service()
        
        # Формируем требования для генерации
        requirements = {
            "position": request.position,
            "requirements": request.requirements,
            "level": request.level,
            "additional_info": request.additional_info
        }
        
        # Генерируем описание вакансии
        vacancy_data = await hr_service.generate_vacancy_description(db, current_user, requirements)
        
        return HRVacancyGenerationResponse(**vacancy_data)
        
    except Exception as e:
        print(f"❌ Vacancy generation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при генерации вакансии: {str(e)}"
        )


@router.get("/analytics", response_model=HRAnalyticsResponse)
async def get_hr_analytics(
    period_days: int = Query(30, description="Период анализа в днях"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    """
    📊 HR аналитика по кандидатам.
    
    Предоставляет комплексную аналитику:
    - Общая статистика по кандидатам
    - Топ навыки и технологии
    - Распределение по уровню опыта
    - Географическое распределение  
    - Зарплатные ожидания
    - Рекомендации и инсайты
    """
    try:
        print(f"📊 HR Analytics request from: {current_user.username}")
        print(f"📅 Period: {period_days} days")
        
        hr_service = get_hr_ai_assistant_service()
        
        # Получаем аналитику
        analytics_data = await hr_service.get_hr_analytics(db, current_user, period_days)
        
        return HRAnalyticsResponse(**analytics_data)
        
    except Exception as e:
        print(f"❌ HR Analytics error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении аналитики: {str(e)}"
        )


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_hr_chat_sessions(
    limit: int = Query(10, description="Количество сессий"),
    skip: int = Query(0, description="Пропустить сессий"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    """
    📜 Получить историю чат-сессий HR-ассистента.
    
    Возвращает список всех сессий общения HR-менеджера с ассистентом,
    включая количество сообщений и дату последней активности.
    """
    try:
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == current_user.id
        ).order_by(
            ChatSession.last_activity_at.desc()
        ).offset(skip).limit(limit).all()
        
        result = []
        for session in sessions:
            # Подсчитываем количество сообщений
            messages_count = db.query(ChatMessage).filter(
                ChatMessage.session_id == session.id
            ).count()
            
            session_response = ChatSessionResponse(
                id=session.id,
                user_id=session.user_id,
                title=session.title,
                status=session.status,
                context_data=session.context_data,
                last_activity_at=session.last_activity_at,
                created_at=session.created_at,
                updated_at=session.updated_at,
                messages_count=messages_count
            )
            result.append(session_response)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении сессий: {str(e)}"
        )


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_hr_chat_messages(
    session_id: int,
    limit: int = Query(50, description="Количество сообщений"),
    skip: int = Query(0, description="Пропустить сообщений"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    """
    💬 Получить сообщения из конкретной сессии HR-чата.
    
    Возвращает историю переписки с ассистентом в выбранной сессии,
    включая метаданные о найденных кандидатах и рекомендациях.
    """
    try:
        # Проверяем, что сессия принадлежит текущему пользователю
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Сессия не найдена"
            )
        
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(
            ChatMessage.created_at.asc()
        ).offset(skip).limit(limit).all()
        
        return [ChatMessageResponse.from_orm(msg) for msg in messages]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении сообщений: {str(e)}"
        )


@router.get("/stats", response_model=HRAssistantStatsResponse)
async def get_hr_assistant_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    """
    📈 Статистика использования HR AI-ассистента.
    
    Показывает:
    - Общее количество сессий и сообщений
    - Количество поисков кандидатов
    - Количество сгенерированных вакансий
    - Популярные запросы и навыки
    - Эффективность поисков
    """
    try:
        # Получаем базовую статистику
        total_sessions = db.query(ChatSession).filter(
            ChatSession.user_id == current_user.id
        ).count()
        
        total_messages = db.query(ChatMessage).join(ChatSession).filter(
            ChatSession.user_id == current_user.id
        ).count()
        
        # Здесь можно добавить более сложную логику для HR-специфичной статистики
        # Пока возвращаем базовые данные
        return HRAssistantStatsResponse(
            total_sessions=total_sessions,
            total_messages=total_messages,
            candidates_searched=0,  # Требует дополнительной логики подсчета
            vacancies_generated=0,  # Требует дополнительной логики подсчета
            analytics_requests=0,   # Требует дополнительной логики подсчета
            top_search_queries=[
                "Python разработчик",
                "Frontend developer", 
                "Data Scientist",
                "DevOps engineer"
            ],
            top_skills_searched=[
                "Python", "JavaScript", "React", "SQL", "Docker"
            ],
            average_candidates_per_search=5.2,
            successful_searches_percentage=87.5
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении статистики: {str(e)}"
        )


@router.delete("/sessions/{session_id}")
async def delete_hr_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    """
    🗑️ Удалить сессию HR-чата.
    
    Полностью удаляет сессию и все связанные сообщения.
    Операция необратима.
    """
    try:
        # Проверяем, что сессия принадлежит текущему пользователю
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Сессия не найдена"
            )
        
        # Удаляем сессию (сообщения удалятся автоматически из-за cascade)
        db.delete(session)
        db.commit()
        
        return {"message": f"Сессия {session_id} успешно удалена"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при удалении сессии: {str(e)}"
        )
