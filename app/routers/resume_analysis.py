"""
Роутер для анализа резюме
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import ResumeAnalyzeRequest, ResumeAnalyzeResponse
from app.services.resume_analysis_service import get_resume_analysis_service
from app.services.async_resume_processor import async_resume_processor
from app.auth import get_current_user
from app.models import User, Resume, ProcessingStatus

router = APIRouter()

@router.get("/")
async def root():
    return {"message": "Resume Analyzer API is running"}

@router.post("/analyze_resume", response_model=ResumeAnalyzeResponse)
async def analyze_resume(
    request: ResumeAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Анализирует резюме относительно вакансии (синхронный анализ)
    """
    
    # Проверяем входные данные
    if not request.job_description.strip():
        raise HTTPException(status_code=400, detail="job_description не может быть пустым")
    
    if not request.resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text не может быть пустым")
    
    try:
        # Анализируем резюме
        service = get_resume_analysis_service()
        analysis_result = await service.analyze_resume(
            request.job_description, 
            request.resume_text
        )
        
        return ResumeAnalyzeResponse(**analysis_result)
        
    except Exception as e:
        import traceback
        print(f"Ошибка в analyze_resume: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Ошибка анализа резюме: {str(e)}")


@router.post("/analyze_resume_async")
async def analyze_resume_async(
    request: ResumeAnalyzeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Запускает асинхронный анализ резюме (возвращает сразу, обработка в фоне)
    """
    
    # Проверяем входные данные
    if not request.job_description.strip():
        raise HTTPException(status_code=400, detail="job_description не может быть пустым")
    
    if not request.resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text не может быть пустым")
    
    try:
        # Создаем временное резюме для обработки
        from app.models import Vacancy
        from datetime import datetime
        
        # Создаем временную вакансию с описанием
        temp_vacancy = Vacancy(
            title="Временная вакансия для анализа",
            description=request.job_description,
            creator_id=current_user.id
        )
        db.add(temp_vacancy)
        db.flush()  # Получаем ID вакансии
        
        # Создаем временное резюме
        temp_resume = Resume(
            user_id=current_user.id,
            vacancy_id=temp_vacancy.id,
            file_path="",  # Путь не нужен для текстового анализа
            original_filename="text_analysis.txt",
            processing_status=ProcessingStatus.PENDING
        )
        db.add(temp_resume)
        db.commit()
        db.refresh(temp_resume)
        
        # Запускаем асинхронную обработку
        background_tasks.add_task(
            async_resume_processor.process_resume_async, 
            temp_resume.id
        )
        
        return {
            "message": "Анализ резюме запущен в фоновом режиме",
            "resume_id": temp_resume.id,
            "status": "processing",
            "estimated_time": "2-3 минуты"
        }
        
    except Exception as e:
        import traceback
        print(f"Ошибка в analyze_resume_async: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Ошибка запуска анализа: {str(e)}")


@router.get("/status/{resume_id}")
async def get_analysis_status(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Проверяет статус обработки резюме
    """
    try:
        resume = db.query(Resume).filter(
            Resume.id == resume_id,
            Resume.user_id == current_user.id
        ).first()
        
        if not resume:
            raise HTTPException(status_code=404, detail="Резюме не найдено")
        
        result = {
            "resume_id": resume_id,
            "processing_status": resume.processing_status.value,
            "processed": resume.processed,
            "uploaded_at": resume.uploaded_at.isoformat() if resume.uploaded_at else None
        }
        
        # Если обработка завершена, добавляем результат анализа
        if resume.processed and resume.analysis:
            analysis = resume.analysis
            result["analysis"] = {
                "name": analysis.name,
                "position": analysis.position,
                "experience": analysis.experience,
                "education": analysis.education,
                "match_score": analysis.match_score,
                "key_skills": analysis.key_skills,
                "recommendation": analysis.recommendation,
                "projects": analysis.projects,
                "work_experience": analysis.work_experience,
                "technologies": analysis.technologies,
                "achievements": analysis.achievements,
                "structured": analysis.structured,
                "effort_level": analysis.effort_level,
                "suspicious_phrases_found": analysis.suspicious_phrases_found,
                "suspicious_examples": analysis.suspicious_examples
            }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Ошибка в get_analysis_status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения статуса: {str(e)}")
