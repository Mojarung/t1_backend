"""
Роутер для AI-интервью с аватаром для дозаполнения резюме пользователя
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from typing import List, Dict, Any, Optional
from datetime import datetime
import aiohttp
import os
import json

from app.database import get_db
from app.models import User, Resume, ResumeAnalysis, Interview, InterviewStatus
from app.schemas import InterviewCreate, InterviewUpdate, InterviewResponse
from app.auth import get_current_user
from app.services.resume_gap_analysis_service import get_resume_gap_analysis_service
from app.services.resume_analysis_service import get_resume_analysis_service
from app.services.resume_completion_service import get_resume_completion_service

router = APIRouter()

@router.post("/start-resume-interview")
async def start_resume_interview(
    resume_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Запускает AI-интервью с аватаром для дозаполнения резюме пользователя
    """
    
    # Проверяем, что резюме принадлежит пользователю
    resume = db.query(Resume).filter(
        Resume.id == resume_id,
        Resume.user_id == current_user.id
    ).first()
    
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Резюме не найдено"
        )
    
    # Получаем анализ резюме
    resume_analysis = db.query(ResumeAnalysis).filter(
        ResumeAnalysis.resume_id == resume_id
    ).first()
    
    # Анализируем пробелы в резюме
    gap_service = get_resume_gap_analysis_service()
    gaps_analysis = await gap_service.analyze_resume_gaps(current_user, resume_analysis)
    
    # Генерируем вопросы для интервью
    interview_questions = await gap_service.generate_interview_questions(gaps_analysis, current_user)
    
    # Создаем интервью в базе данных
    interview = Interview(
        vacancy_id=resume.vacancy_id,  # Используем vacancy_id из резюме
        resume_id=resume_id,
        status=InterviewStatus.NOT_STARTED,
        scheduled_date=datetime.utcnow(),
        notes=f"AI-интервью для дозаполнения резюме. Пробелы: {gaps_analysis.get('missing_required_fields', [])}"
    )
    
    db.add(interview)
    db.commit()
    db.refresh(interview)
    
    # Подготавливаем данные для AI аватара
    interview_context = {
        "interview_type": "resume_completion",
        "user_profile": {
            "id": current_user.id,
            "name": f"{current_user.first_name or ''} {current_user.last_name or ''}".strip(),
            "email": current_user.email
        },
        "resume_data": {
            "id": resume.id,
            "filename": resume.original_filename,
            "analysis": resume_analysis.model_dump() if resume_analysis else None
        },
        "gaps_analysis": gaps_analysis,
        "interview_questions": interview_questions,
        "estimated_duration": gaps_analysis.get("interview_plan", {}).get("estimated_duration_minutes", 15)
    }
    
    try:
        # Запускаем AI аватар сервис
        avatar_response = await start_avatar_interview(interview.id, interview_context)
        
        return {
            "interview_id": interview.id,
            "avatar_room_url": avatar_response["url"],
            "avatar_token": avatar_response["token"],
            "interview_context": interview_context,
            "message": "AI-интервью запущено успешно"
        }
        
    except Exception as e:
        # Если не удалось запустить аватар, обновляем статус интервью
        interview.status = InterviewStatus.COMPLETED
        interview.summary = f"Ошибка запуска AI-интервью: {str(e)}"
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось запустить AI-интервью: {str(e)}"
        )

async def start_avatar_interview(interview_id: int, interview_context: Dict[str, Any]) -> Dict[str, str]:
    """
    Запускает AI аватар сервис для проведения интервью
    """
    # URL AI аватар сервиса
    avatar_service_url = os.getenv("AI_AVATAR_SERVICE_URL", "http://localhost:7860")
    
    # Подготавливаем данные для аватара
    avatar_request_data = {
        "interview_id": interview_id,
        "context": interview_context
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            # Отправляем запрос на запуск аватара для дозаполнения резюме
            async with session.post(
                f"{avatar_service_url}/resume-completion-interview/{interview_id}",
                json=avatar_request_data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    return {
                        "url": result["url"],
                        "token": result["token"]
                    }
                else:
                    error_text = await response.text()
                    raise Exception(f"Avatar service error: {response.status} - {error_text}")
                    
        except aiohttp.ClientError as e:
            raise Exception(f"Failed to connect to avatar service: {str(e)}")

@router.get("/current-interview")
async def get_current_interview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получает текущее активное AI-интервью пользователя
    """
    
    # Ищем активное интервью пользователя
    interview = db.query(Interview).options(
        joinedload(Interview.resume).joinedload(Resume.user),
        joinedload(Interview.vacancy)
    ).filter(
        Interview.resume.has(user_id=current_user.id),
        Interview.status.in_([InterviewStatus.NOT_STARTED, InterviewStatus.IN_PROGRESS])
    ).order_by(Interview.created_at.desc()).first()
    
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Активное AI-интервью не найдено"
        )
    
    return interview

@router.post("/complete-interview/{interview_id}")
async def complete_interview(
    interview_id: int,
    interview_results: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Завершает AI-интервью и обновляет профиль пользователя на основе результатов
    """
    
    # Проверяем, что интервью принадлежит пользователю
    interview = db.query(Interview).filter(
        Interview.id == interview_id,
        Interview.resume.has(user_id=current_user.id)
    ).first()
    
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Интервью не найдено"
        )
    
    try:
        # Получаем диалог интервью
        dialogue = interview_results.get("dialogue", [])
        
        # Получаем анализ пробелов из контекста интервью (если есть)
        gaps_analysis = {}
        if hasattr(interview, 'notes') and interview.notes:
            # Пытаемся извлечь gaps_analysis из заметок или контекста
            pass
        
        # Обрабатываем результаты интервью с помощью AI
        completion_service = get_resume_completion_service()
        extracted_data = await completion_service.process_interview_results(dialogue, gaps_analysis)
        
        # Обновляем профиль пользователя
        profile_updates = extracted_data.get("profile_updates", {})
        update_result = await completion_service.update_user_profile(current_user, profile_updates, db)
        
        # Генерируем резюме интервью
        summary = await completion_service.generate_interview_summary(dialogue, profile_updates, gaps_analysis)
        
        # Обновляем интервью
        interview.status = InterviewStatus.COMPLETED
        interview.end_date = datetime.utcnow()
        interview.dialogue = {"dialogue": dialogue}
        interview.summary = summary
        
        if update_result["success"]:
            interview.notes = f"Профиль обновлен: {', '.join(update_result['updated_fields'])}"
        else:
            interview.notes = f"Ошибка обновления профиля: {update_result['message']}"
        
        db.commit()
        db.refresh(interview)
        
        return {
            "message": "AI-интервью завершено успешно",
            "profile_updated": update_result["success"],
            "updated_fields": update_result["updated_fields"],
            "extracted_data": extracted_data,
            "summary": summary
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка завершения интервью: {str(e)}"
        )

@router.get("/interview-history")
async def get_interview_history(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получает историю AI-интервью пользователя
    """
    
    interviews = db.query(Interview).options(
        joinedload(Interview.resume).joinedload(Resume.user),
        joinedload(Interview.vacancy)
    ).filter(
        Interview.resume.has(user_id=current_user.id)
    ).order_by(Interview.created_at.desc()).offset(skip).limit(limit).all()
    
    return interviews

async def apply_profile_updates_from_interview(user: User, updates: Dict[str, Any], db: Session):
    """
    Применяет обновления профиля на основе результатов AI-интервью
    """
    try:
        for field, value in updates.items():
            if hasattr(user, field) and value is not None:
                # Специальная обработка для разных типов полей
                if field == "birth_date" and isinstance(value, str):
                    try:
                        from datetime import datetime
                        parsed_date = datetime.fromisoformat(value.replace('Z', '+00:00')).date()
                        setattr(user, field, parsed_date)
                    except ValueError:
                        print(f"Неверный формат даты: {value}")
                        continue
                elif field in ["programming_languages", "other_competencies"] and isinstance(value, list):
                    # Объединяем с существующими значениями
                    current_values = getattr(user, field, []) or []
                    new_values = list(set(current_values + value))
                    setattr(user, field, new_values)
                elif field == "foreign_languages" and isinstance(value, list):
                    # Обрабатываем иностранные языки
                    current_langs = getattr(user, field, []) or []
                    for lang_data in value:
                        if isinstance(lang_data, dict) and lang_data not in current_langs:
                            current_langs.append(lang_data)
                    setattr(user, field, current_langs)
                elif field == "work_experience" and isinstance(value, list):
                    # Объединяем опыт работы
                    current_exp = getattr(user, field, []) or []
                    for exp_data in value:
                        if isinstance(exp_data, dict) and exp_data not in current_exp:
                            current_exp.append(exp_data)
                    setattr(user, field, current_exp)
                elif field == "education" and isinstance(value, list):
                    # Объединяем образование
                    current_edu = getattr(user, field, []) or []
                    for edu_data in value:
                        if isinstance(edu_data, dict) and edu_data not in current_edu:
                            current_edu.append(edu_data)
                    setattr(user, field, current_edu)
                else:
                    # Обычные поля
                    setattr(user, field, value)
        
        db.commit()
        print(f"✅ Профиль пользователя {user.id} обновлен после AI-интервью: {list(updates.keys())}")
        
    except Exception as e:
        print(f"❌ Ошибка обновления профиля после AI-интервью: {e}")
        db.rollback()
        raise
