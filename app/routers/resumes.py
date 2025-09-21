import os
import shutil
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Resume, Vacancy, User, ResumeAnalysis
from app.schemas import ResumeResponse, ResumeAnalysisResponse
from app.auth import get_current_user, get_current_hr_user
from app.config import settings
from app.services.resume_processor import process_resume
from app.services.storage_s3 import get_s3_storage
from app.services.resume_gap_analysis_service import get_resume_gap_analysis_service

router = APIRouter()

@router.post("/upload-by-hr/{vacancy_id}", response_model=List[ResumeResponse])
async def upload_resumes_by_hr(
    vacancy_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )
    
    use_s3 = bool(settings.s3_bucket)
    if not use_s3:
        vacancy_dir = os.path.join(settings.upload_dir, f"vacancy_{vacancy_id}")
        os.makedirs(vacancy_dir, exist_ok=True)
    
    uploaded_resumes = []
    
    for file in files:
        if not file.filename.lower().endswith('.txt'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File {file.filename} has unsupported format. Only TXT files are supported"
            )
        
        if use_s3:
            s3 = get_s3_storage()
            key = f"resumes/vacancy_{vacancy_id}/{file.filename}"
            file.file.seek(0)
            file_path = s3.upload_fileobj(file.file, key, content_type="text/plain")
        else:
            file_path = os.path.join(vacancy_dir, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        
        db_resume = Resume(
            vacancy_id=vacancy_id,
            file_path=file_path,
            original_filename=file.filename,
            uploaded_by_hr=True
        )
        db.add(db_resume)
        db.commit()
        db.refresh(db_resume)
        
        await process_resume(db_resume.id, db)
        uploaded_resumes.append(db_resume)
    
    return uploaded_resumes

@router.post("/upload/{vacancy_id}", response_model=ResumeResponse)
async def upload_resume_by_user(
    vacancy_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )
    
    existing_resume = db.query(Resume).filter(
        Resume.vacancy_id == vacancy_id,
        Resume.user_id == current_user.id
    ).first()
    if existing_resume:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already uploaded a resume for this vacancy"
        )
    
    if not file.filename.lower().endswith('.txt'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Only TXT files are supported"
        )
    
    use_s3 = bool(settings.s3_bucket)
    if use_s3:
        s3 = get_s3_storage()
        key = f"resumes/vacancy_{vacancy_id}/user_{current_user.id}_{file.filename}"
        file.file.seek(0)
        file_path = s3.upload_fileobj(file.file, key, content_type="text/plain")
    else:
        vacancy_dir = os.path.join(settings.upload_dir, f"vacancy_{vacancy_id}")
        os.makedirs(vacancy_dir, exist_ok=True)
        file_path = os.path.join(vacancy_dir, f"user_{current_user.id}_{file.filename}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    
    db_resume = Resume(
        user_id=current_user.id,
        vacancy_id=vacancy_id,
        file_path=file_path,
        original_filename=file.filename,
        uploaded_by_hr=False
    )
    db.add(db_resume)
    db.commit()
    db.refresh(db_resume)
    
    await process_resume(db_resume.id, db)
    
    return db_resume

@router.get("/", response_model=List[ResumeResponse])
def get_user_resumes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получение заявок текущего пользователя"""
    return db.query(Resume).join(Vacancy).filter(Resume.user_id == current_user.id).all()

@router.get("/candidates", response_model=List[ResumeResponse])
def get_all_candidates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    """Получение всех кандидатов для HR"""
    return db.query(Resume).join(User).filter(Resume.user_id.isnot(None)).all()

@router.get("/vacancy/{vacancy_id}", response_model=List[ResumeResponse])
def get_resumes_by_vacancy(
    vacancy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )
    
    return db.query(Resume).filter(Resume.vacancy_id == vacancy_id).all()

@router.get("/{resume_id}/analysis", response_model=ResumeAnalysisResponse)
def get_resume_analysis(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    
    if current_user.role.value != "hr" and resume.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    analysis = db.query(ResumeAnalysis).filter(ResumeAnalysis.resume_id == resume_id).first()
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume analysis not found"
        )
    
    return analysis

@router.get("/{resume_id}/download")
def download_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    
    if current_user.role.value != "hr" and resume.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Если файл хранится в S3, генерируем presigned URL и редиректим
    if resume.file_path.startswith("s3://"):
        s3 = get_s3_storage()
        # извлечем ключ из URI
        _, key = s3.parse_s3_uri(resume.file_path)
        url = s3.generate_presigned_url(key, filename=resume.original_filename, expires_in=3600)
        return RedirectResponse(url=url, status_code=302)

    # Иначе локальная файловая система
    if not os.path.exists(resume.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    return FileResponse(
        path=resume.file_path,
        filename=resume.original_filename,
        media_type='application/octet-stream'
    )

@router.post("/{resume_id}/start-ai-interview")
async def start_ai_interview_for_profile(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Запускает AI-интервью для дозаполнения профиля пользователя на основе данных из БД
    """
    # Работаем ТОЛЬКО с данными профиля из базы данных
    # resume_id игнорируется, все данные берутся из current_user

    # Анализируем пробелы в профиле пользователя
    gap_service = get_resume_gap_analysis_service()
    gaps_analysis = await gap_service.analyze_resume_gaps(current_user, None)  # Без анализа резюме

    # Проверяем, есть ли пробелы для заполнения
    missing_required_fields = gaps_analysis.get('missing_required_fields', [])
    if not missing_required_fields and not any(
        gaps_analysis.get('gaps_analysis', {}).get(category, {}).get('missing_fields') or
        gaps_analysis.get('gaps_analysis', {}).get(category, {}).get('incomplete_fields')
        for category in ['personal_info', 'professional_experience', 'skills', 'education']
    ):
        return {
            "message": "Профиль уже содержит достаточно информации",
            "suggested_actions": ["Просмотрите и отредактируйте профиль вручную", "Подайте заявку на вакансию"],
            "gaps_analysis": gaps_analysis
        }

    # Генерируем вопросы для интервью
    interview_questions = await gap_service.generate_interview_questions(gaps_analysis, current_user)

    # Создаем интервью в базе данных
    from app.models import Interview, InterviewStatus
    from datetime import datetime

    interview = Interview(
        vacancy_id=None,  # Интервью не привязано к вакансии
        resume_id=None,   # Интервью не привязано к резюме
        status=InterviewStatus.NOT_STARTED,
        scheduled_date=datetime.utcnow(),
        notes=f"AI-интервью для дозаполнения профиля. Пробелы: {missing_required_fields}"
    )

    db.add(interview)
    db.commit()
    db.refresh(interview)

    # Подготавливаем данные для AI аватара ТОЛЬКО из профиля пользователя
    interview_context = {
        "interview_type": "resume_completion",
        "user_profile": {
            "id": current_user.id,
            "name": f"{current_user.first_name or ''} {current_user.last_name or ''}".strip(),
            "email": current_user.email,
            "phone": current_user.phone,
            "location": current_user.location,
            "about": current_user.about,
            "desired_salary": current_user.desired_salary,
            "ready_to_relocate": current_user.ready_to_relocate,
            "employment_type": current_user.employment_type.value if current_user.employment_type else None,
            "education": current_user.education,
            "work_experience": current_user.work_experience,
            "programming_languages": current_user.programming_languages,
            "foreign_languages": current_user.foreign_languages,
            "other_competencies": current_user.other_competencies
        },
        "resume_data": None,  # Не используем данные резюме
        "gaps_analysis": gaps_analysis,
        "interview_questions": interview_questions,
        "estimated_duration": gaps_analysis.get("interview_plan", {}).get("estimated_duration_minutes", 15)
    }

    try:
        # Запускаем AI аватар сервис
        from app.routers.ai_resume_interview import start_avatar_interview
        avatar_response = await start_avatar_interview(interview.id, interview_context)

        return {
            "interview_id": interview.id,
            "avatar_room_url": avatar_response["url"],
            "avatar_token": avatar_response["token"],
            "interview_context": interview_context,
            "message": "AI-интервью запущено успешно",
            "gaps_analysis": gaps_analysis,
            "missing_required_fields": missing_required_fields
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

@router.get("/{resume_id}/gaps-analysis")
async def get_resume_gaps_analysis(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получает анализ пробелов в резюме пользователя
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
    
    return {
        "resume_id": resume_id,
        "gaps_analysis": gaps_analysis,
        "recommendations": {
            "needs_interview": bool(gaps_analysis.get('missing_required_fields', [])),
            "priority_areas": gaps_analysis.get('interview_plan', {}).get('focus_areas', []),
            "estimated_duration": gaps_analysis.get('interview_plan', {}).get('estimated_duration_minutes', 15)
        }
    }
