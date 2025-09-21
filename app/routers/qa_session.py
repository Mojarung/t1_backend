"""
Роутер для QA-сессий с пользователями
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models import User, QASession
from app.auth import get_current_user
from app.schemas import QASessionCreate, QASessionResponse, QASessionUpdate, QAQuestion, QAAnswer
from app.services.qa_service import get_qa_service

router = APIRouter()

@router.post("/start", response_model=QASessionResponse)
async def start_qa_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Начинает новую QA-сессию для пользователя"""
    
    # Проверяем, есть ли уже активная сессия
    existing_session = db.query(QASession).filter(
        QASession.user_id == current_user.id,
        QASession.status == "active"
    ).first()
    
    if existing_session:
        return existing_session
    
    # Получаем данные из резюме (если есть)
    resume_data = {}  # Здесь можно добавить логику получения данных из резюме
    
    # Генерируем вопросы
    qa_service = get_qa_service()
    questions = await qa_service.generate_questions(current_user, resume_data)
    
    # Создаем новую сессию
    qa_session = QASession(
        user_id=current_user.id,
        status="active",
        current_question_index=0,
        questions=questions,
        answers=[],
        profile_updates={}
    )
    
    db.add(qa_session)
    db.commit()
    db.refresh(qa_session)
    
    return qa_session

@router.get("/current", response_model=QASessionResponse)
async def get_current_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получает текущую активную QA-сессию"""
    
    session = db.query(QASession).filter(
        QASession.user_id == current_user.id,
        QASession.status == "active"
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Активная QA-сессия не найдена"
        )
    
    return session

@router.get("/current/question")
async def get_current_question(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получает текущий вопрос QA-сессии"""
    
    session = db.query(QASession).filter(
        QASession.user_id == current_user.id,
        QASession.status == "active"
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Активная QA-сессия не найдена"
        )
    
    questions = session.questions or []
    current_index = session.current_question_index
    
    if current_index >= len(questions):
        # Все вопросы пройдены
        session.status = "completed"
        db.commit()
        return {"status": "completed", "message": "Все вопросы пройдены!"}
    
    current_question = questions[current_index]
    
    return {
        "question": current_question,
        "progress": {
            "current": current_index + 1,
            "total": len(questions)
        }
    }

@router.post("/answer")
async def submit_answer(
    answer_data: QASessionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Отправляет ответ на текущий вопрос"""
    
    session = db.query(QASession).filter(
        QASession.user_id == current_user.id,
        QASession.status == "active"
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Активная QA-сессия не найдена"
        )
    
    questions = session.questions or []
    current_index = session.current_question_index
    
    if current_index >= len(questions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Все вопросы уже пройдены"
        )
    
    current_question = questions[current_index]
    
    if answer_data.skip:
        # Пользователь пропускает вопрос
        current_question["current_attempt"] = current_question["max_attempts"]
        session.current_question_index += 1
        session.updated_at = datetime.utcnow()
        db.commit()
        
        return {"message": "Вопрос пропущен", "next_question": True}
    
    # Анализируем ответ
    qa_service = get_qa_service()
    analysis = await qa_service.analyze_answer(current_question, answer_data.answer, current_user)
    
    # Сохраняем ответ
    answer = {
        "question_id": current_question["id"],
        "answer": answer_data.answer,
        "attempt": current_question["current_attempt"] + 1,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if not session.answers:
        session.answers = []
    
    session.answers.append(answer)
    
    if analysis["is_informative"]:
        # Ответ информативный, обновляем профиль
        profile_updates = analysis.get("profile_update", {})
        if profile_updates:
            if not session.profile_updates:
                session.profile_updates = {}
            session.profile_updates.update(profile_updates)
            
            # Применяем обновления к профилю пользователя
            await apply_profile_updates(current_user, profile_updates, db)
        
        # Переходим к следующему вопросу
        session.current_question_index += 1
        session.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "message": "Ответ принят",
            "profile_updated": bool(profile_updates),
            "next_question": True
        }
    else:
        # Ответ неинформативный, увеличиваем счетчик попыток
        current_question["current_attempt"] += 1
        
        if current_question["current_attempt"] >= current_question["max_attempts"]:
            # Превышено количество попыток, переходим к следующему вопросу
            session.current_question_index += 1
            session.updated_at = datetime.utcnow()
            db.commit()
            
            return {
                "message": "Превышено количество попыток, переходим к следующему вопросу",
                "next_question": True
            }
        else:
            # Переспрашиваем
            session.updated_at = datetime.utcnow()
            db.commit()
            
            return {
                "message": "Пожалуйста, дайте более подробный ответ",
                "suggestion": analysis.get("suggestion", ""),
                "next_question": False,
                "attempts_left": current_question["max_attempts"] - current_question["current_attempt"]
            }

@router.post("/skip")
async def skip_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Пропускает всю QA-сессию"""
    
    session = db.query(QASession).filter(
        QASession.user_id == current_user.id,
        QASession.status == "active"
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Активная QA-сессия не найдена"
        )
    
    session.status = "skipped"
    session.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "QA-сессия пропущена"}

@router.get("/history")
async def get_qa_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получает историю QA-сессий пользователя"""
    
    sessions = db.query(QASession).filter(
        QASession.user_id == current_user.id
    ).order_by(QASession.created_at.desc()).all()
    
    return sessions

async def apply_profile_updates(user: User, updates: dict, db: Session):
    """Применяет обновления к профилю пользователя"""
    try:
        for field, value in updates.items():
            if hasattr(user, field) and value is not None:
                # Специальная обработка для enum полей
                if field == "employment_type" and isinstance(value, str):
                    from app.models import EmploymentType
                    try:
                        setattr(user, field, EmploymentType(value))
                    except ValueError:
                        print(f"Неверное значение employment_type: {value}")
                        continue
                elif field == "birth_date" and isinstance(value, str):
                    try:
                        from datetime import datetime
                        parsed_date = datetime.fromisoformat(value.replace('Z', '+00:00')).date()
                        setattr(user, field, parsed_date)
                    except ValueError:
                        print(f"Неверный формат даты: {value}")
                        continue
                else:
                    setattr(user, field, value)
        
        db.commit()
        print(f"✅ Профиль пользователя {user.id} обновлен: {updates}")
        
    except Exception as e:
        print(f"❌ Ошибка обновления профиля: {e}")
        db.rollback()
