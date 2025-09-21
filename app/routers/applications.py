from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.database import get_db
from app.models import Interview, User, Vacancy, Resume, ApplicationStatus, ProcessingStatus
from app.auth import get_current_user, get_current_hr_user
from app.schemas import ResumeResponse, ApplicationCreate
from app.services.async_resume_processor import async_resume_processor
from datetime import datetime
import os
import shutil
import httpx
import asyncio

router = APIRouter()

@router.post("/apply/{vacancy_id}", response_model=ResumeResponse)
async def apply_for_vacancy(
    vacancy_id: int,
    application_data: ApplicationCreate,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Подача заявки на вакансию с использованием данных из профиля"""
    
    # Проверяем, что вакансия существует и открыта
    vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Вакансия не найдена"
        )
    
    if vacancy.status.value != "open":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вакансия закрыта для подачи заявок"
        )
    
    # Проверяем, что пользователь еще не подавал заявку на эту вакансию
    existing_application = db.query(Resume).filter(
        Resume.user_id == current_user.id,
        Resume.vacancy_id == vacancy_id
    ).first()
    
    if existing_application:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже подавали заявку на эту вакансию"
        )
    
    # Создаем запись в базе данных без файла
    db_resume = Resume(
        user_id=current_user.id,
        vacancy_id=vacancy_id,
        file_path="",  # Пустой путь, так как файл не загружается
        original_filename="profile_data",  # Указываем, что данные из профиля
        status=ApplicationStatus.PENDING,
        notes=application_data.cover_letter,
        processing_status=ProcessingStatus.PENDING,
        processed=True  # Сразу помечаем как обработанное, так как данные уже есть
    )
    
    db.add(db_resume)
    db.commit()
    db.refresh(db_resume)
    
    # Запускаем асинхронную обработку профиля для создания анализа
    background_tasks.add_task(
        process_profile_for_application, 
        db_resume.id,
        current_user.id,
        vacancy_id
    )
    
    return db_resume

@router.get("/my-applications", response_model=List[ResumeResponse])
def get_my_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получение заявок текущего пользователя"""
    return db.query(Resume).join(Vacancy).filter(
        Resume.user_id == current_user.id
    ).order_by(Resume.uploaded_at.desc()).all()


@router.get("/interview/{resume_id}")
def get_application_interview(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение interview_id для заявки"""
    from app.models import Interview
    
    # Проверяем, что заявка принадлежит текущему пользователю
    resume = db.query(Resume).filter(
        Resume.id == resume_id,
    ).first()
    
    if not resume:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    
    # Ищем интервью для этой заявки
    interview = db.query(Interview).filter(
        Interview.resume_id == resume_id
    ).first()
    
    if not interview:
        raise HTTPException(status_code=404, detail="Интервью не найдено для этой заявки")
    
    return {"interview_id": interview.id}

@router.get("/status/{resume_id}")
async def get_application_status(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Проверяет статус обработки заявки
    """
    try:
        resume = db.query(Resume).filter(
            Resume.id == resume_id,
            Resume.user_id == current_user.id
        ).first()
        
        if not resume:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        
        result = {
            "resume_id": resume_id,
            "processing_status": resume.processing_status.value,
            "processed": resume.processed,
            "application_status": resume.status.value,
            "uploaded_at": resume.uploaded_at.isoformat() if resume.uploaded_at else None,
            "vacancy_title": resume.vacancy.title if resume.vacancy else None
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
        print(f"Ошибка в get_application_status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения статуса: {str(e)}")

@router.get("/all", response_model=List[ResumeResponse])
def get_all_applications(
    status_filter: Optional[str] = None,
    vacancy_id: Optional[int] = None,
    processed: Optional[bool] = True,  # По умолчанию только обработанные
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    """Получение всех заявок для HR с расширенной фильтрацией и загрузкой связей"""
    query = db.query(Resume).options(
        joinedload(Resume.user),      # Загрузка пользователя
        joinedload(Resume.vacancy),   # Загрузка вакансии
        joinedload(Resume.analysis)   # Загрузка анализа
    )
    
    # Фильтр по статусу обработки
    if processed is not None:
        query = query.filter(Resume.processed == processed)
    
    # Фильтр по статусу заявки
    if status_filter:
        try:
            status_enum = ApplicationStatus(status_filter)
            query = query.filter(Resume.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный статус заявки"
            )
    
    # Фильтр по вакансии
    if vacancy_id:
        query = query.filter(Resume.vacancy_id == vacancy_id)
    
    # Скрываем soft-deleted для HR
    query = query.filter(Resume.hidden_for_hr == False)

    # Сортировка по дате загрузки (последние сверху)
    query = query.order_by(Resume.uploaded_at.desc())
    
    return query.all()

@router.get("/{application_id}", response_model=ResumeResponse)
def get_application_details(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получение деталей заявки"""
    application = db.query(Resume).filter(Resume.id == application_id).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заявка не найдена"
        )
    
    # Проверяем права доступа
    if current_user.role.value == "user" and application.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этой заявке"
        )
    
    return application

@router.put("/{application_id}/status")
def update_application_status(
    application_id: int,
    new_status: str,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    """Обновление статуса заявки (только для HR)"""
    print(f"🔄 Backend: Updating application {application_id} to status {new_status}")
    
    application = db.query(Resume).filter(Resume.id == application_id).first()
    
    if not application:
        print(f"❌ Backend: Application {application_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заявка не найдена"
        )
    
    try:
        status_enum = ApplicationStatus(new_status)
        if status_enum == ApplicationStatus.INTERVIEW_SCHEDULED:
            # Создаем интервью только если его еще нет для этой заявки
            existing_interview = db.query(Interview).filter(
                Interview.resume_id == application.id
            ).first()
            if not existing_interview:
                interview = Interview(
                    resume_id=application.id,
                    vacancy_id=application.vacancy_id
                )
                db.add(interview)
                db.commit()
        print(f"✅ Backend: Status enum created: {status_enum}")
    except ValueError as e:
        print(f"❌ Backend: Invalid status {new_status}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный статус заявки"
        )
    
    application.status = status_enum
    application.updated_at = datetime.utcnow()
    
    if notes:
        application.notes = notes
    
    db.commit()
    print(f"✅ Backend: Application {application_id} status updated to {new_status}")
    
    return {"message": "Статус заявки обновлен", "new_status": new_status}

@router.delete("/{application_id}")
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Удаление заявки

    Для HR выполняется мягкое удаление: заявка скрывается из их списка,
    но остаётся в базе, чтобы кандидат не мог подать повторно.
    Для владельца-кандидата — прежнее поведение с физическим удалением.
    """
    application = db.query(Resume).filter(Resume.id == application_id).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заявка не найдена"
        )
    
    # Для HR: soft delete
    if current_user.role.value == "hr":
        application.hidden_for_hr = True
        db.commit()
        return {"message": "Заявка скрыта для HR"}

    # Для кандидата: только свою заявку и полное удаление
    if current_user.role.value == "user" and application.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этой заявке"
        )

    # Удаляем файл и запись
    try:
        if os.path.exists(application.file_path):
            os.remove(application.file_path)
    except Exception as e:
        print(f"Ошибка при удалении файла: {e}")

    db.delete(application)
    db.commit()

    return {"message": "Заявка удалена"}

@router.get("/stats/summary")
def get_application_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    """Получение статистики заявок для HR"""
    total_applications = db.query(Resume).count()
    pending_applications = db.query(Resume).filter(
        Resume.status == ApplicationStatus.PENDING
    ).count()
    reviewed_applications = total_applications - pending_applications
    accepted_applications = db.query(Resume).filter(
        Resume.status == ApplicationStatus.ACCEPTED
    ).count()
    rejected_applications = db.query(Resume).filter(
        Resume.status == ApplicationStatus.REJECTED
    ).count()
    
    return {
        "total": total_applications,
        "pending": pending_applications,
        "reviewed": reviewed_applications,
        "accepted": accepted_applications,
        "rejected": rejected_applications
    }

async def process_resume_with_ocr(resume_id: int, file_path: str, job_description: str):
    """Обработка резюме через OCR и нейронку"""
    try:
        print(f"🔄 Начинаем обработку резюме {resume_id}")
        
        # 1. Отправляем файл в OCR сервис
        ocr_text = await extract_text_with_ocr(file_path)
        if not ocr_text:
            print(f"❌ OCR не смог извлечь текст из файла {file_path}")
            return
        
        print(f"✅ OCR извлек текст: {len(ocr_text)} символов")
        
        # 2. Отправляем в нейронку для анализа
        ai_recommendation = await analyze_resume_with_ai(ocr_text, job_description)
        if not ai_recommendation:
            print(f"❌ Нейронка не смогла проанализировать резюме {resume_id}")
            return
        
        print(f"✅ Нейронка проанализировала резюме: {ai_recommendation}")
        
        # 3. Обновляем статус заявки на "обработано"
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            resume = db.query(Resume).filter(Resume.id == resume_id).first()
            if resume:
                resume.status = ApplicationStatus.PENDING
                resume.notes = f"{resume.notes or ''}\n\n🤖 Рекомендация ИИ: {ai_recommendation}".strip()
                db.commit()
                print(f"✅ Заявка {resume_id} обновлена и готова для HR")
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Ошибка при обработке резюме {resume_id}: {e}")

async def extract_text_with_ocr(file_path: str) -> Optional[str]:
    """Извлечение текста из файла через OCR сервис"""
    try:
        ocr_url = os.getenv("OCR_URL", "https://moretech-ocr-b2f79abb7082.herokuapp.com/")
        
        with open(file_path, "rb") as file:
            files = {"file": (os.path.basename(file_path), file, "application/octet-stream")}
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(ocr_url, files=files)
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("text", "")
                else:
                    print(f"❌ OCR сервис вернул ошибку: {response.status_code} - {response.text}")
                    return None
                    
    except Exception as e:
        print(f"❌ Ошибка при обращении к OCR сервису: {e}")
        return None

async def process_profile_for_application(resume_id: int, user_id: int, vacancy_id: int):
    """Обработка профиля пользователя для создания анализа заявки"""
    try:
        from app.database import SessionLocal
        from app.models import ResumeAnalysis, Vacancy
        
        db = SessionLocal()
        try:
            # Получаем пользователя и вакансию
            user = db.query(User).filter(User.id == user_id).first()
            vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
            
            if not user or not vacancy:
                print(f"❌ Пользователь {user_id} или вакансия {vacancy_id} не найдены")
                return
            
            # Формируем текст профиля для анализа
            profile_text = format_user_profile_for_analysis(user)
            
            # Анализируем профиль через AI
            analysis_result = await analyze_profile_with_ai(profile_text, vacancy.description)
            
            if analysis_result:
                # Создаем запись анализа
                resume_analysis = ResumeAnalysis(
                    resume_id=resume_id,
                    name=f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                    position=extract_position_from_profile(user),
                    experience=extract_experience_from_profile(user),
                    education=extract_education_from_profile(user),
                    upload_date=datetime.now().strftime("%Y-%m-%d"),
                    match_score=analysis_result.get("basic_info", {}).get("match_score", "0%"),
                    key_skills=analysis_result.get("basic_info", {}).get("key_skills", []),
                    recommendation=analysis_result.get("basic_info", {}).get("recommendation", "Требует дополнительного анализа"),
                    projects=analysis_result.get("extended_info", {}).get("projects", []),
                    work_experience=analysis_result.get("extended_info", {}).get("work_experience", []),
                    technologies=analysis_result.get("extended_info", {}).get("technologies", []),
                    achievements=analysis_result.get("extended_info", {}).get("achievements", []),
                    strengths=analysis_result.get("detailed_analysis", {}).get("strengths", []),
                    weaknesses=analysis_result.get("detailed_analysis", {}).get("weaknesses", []),
                    missing_skills=analysis_result.get("detailed_analysis", {}).get("missing_skills", []),
                    brief_reason=analysis_result.get("detailed_analysis", {}).get("analysis_text", ""),
                    structured=analysis_result.get("resume_quality", {}).get("structured", True),
                    effort_level=analysis_result.get("resume_quality", {}).get("effort_level", "high"),
                    suspicious_phrases_found=analysis_result.get("anti_manipulation", {}).get("suspicious_phrases_found", False),
                    suspicious_examples=analysis_result.get("anti_manipulation", {}).get("examples", [])
                )
                
                db.add(resume_analysis)
                db.commit()
                
                print(f"✅ Анализ профиля для заявки {resume_id} создан")
            else:
                print(f"❌ Не удалось создать анализ для заявки {resume_id}")
                
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Ошибка при обработке профиля для заявки {resume_id}: {e}")

def format_user_profile_for_analysis(user: User) -> str:
    """Форматирование профиля пользователя в текст для анализа"""
    profile_parts = []
    
    # Основная информация
    profile_parts.append("=== ЛИЧНАЯ ИНФОРМАЦИЯ ===")
    profile_parts.append(f"Имя: {user.first_name or 'Не указано'}")
    profile_parts.append(f"Фамилия: {user.last_name or 'Не указано'}")
    profile_parts.append(f"Телефон: {user.phone or 'Не указан'}")
    profile_parts.append(f"Местоположение: {user.location or 'Не указано'}")
    profile_parts.append(f"О себе: {user.about or 'Не указано'}")
    
    # Профессиональная информация
    profile_parts.append("\n=== ПРОФЕССИОНАЛЬНАЯ ИНФОРМАЦИЯ ===")
    profile_parts.append(f"Желаемая зарплата: {user.desired_salary or 'Не указана'}")
    profile_parts.append(f"Тип занятости: {user.employment_type.value if user.employment_type else 'Не указан'}")
    profile_parts.append(f"Готов к переезду: {'Да' if user.ready_to_relocate else 'Нет'}")
    
    # Навыки
    if user.skills:
        profile_parts.append(f"\n=== НАВЫКИ ===")
        for skill in user.skills:
            profile_parts.append(f"• {skill}")
    
    if user.programming_languages:
        profile_parts.append(f"\n=== ЯЗЫКИ ПРОГРАММИРОВАНИЯ ===")
        for lang in user.programming_languages:
            profile_parts.append(f"• {lang}")
    
    if user.foreign_languages:
        profile_parts.append(f"\n=== ИНОСТРАННЫЕ ЯЗЫКИ ===")
        for lang in user.foreign_languages:
            if isinstance(lang, dict):
                profile_parts.append(f"• {lang.get('language', '')} - {lang.get('level', '')}")
            else:
                profile_parts.append(f"• {lang}")
    
    if user.other_competencies:
        profile_parts.append(f"\n=== ДРУГИЕ КОМПЕТЕНЦИИ ===")
        for comp in user.other_competencies:
            profile_parts.append(f"• {comp}")
    
    # Опыт работы
    if user.work_experience:
        profile_parts.append(f"\n=== ОПЫТ РАБОТЫ ===")
        for exp in user.work_experience:
            if isinstance(exp, dict):
                profile_parts.append(f"• {exp.get('position', '')} в {exp.get('company', '')} ({exp.get('period', '')})")
                if exp.get('description'):
                    profile_parts.append(f"  {exp.get('description', '')}")
            else:
                profile_parts.append(f"• {exp}")
    
    # Образование
    if user.education:
        profile_parts.append(f"\n=== ОБРАЗОВАНИЕ ===")
        for edu in user.education:
            if isinstance(edu, dict):
                profile_parts.append(f"• {edu.get('degree', '')} по специальности {edu.get('field', '')} в {edu.get('institution', '')} ({edu.get('period', '')})")
            else:
                profile_parts.append(f"• {edu}")
    
    return "\n".join(profile_parts)

def extract_position_from_profile(user: User) -> str:
    """Извлечение позиции из профиля пользователя"""
    if user.work_experience and len(user.work_experience) > 0:
        latest_exp = user.work_experience[0]  # Предполагаем, что первый элемент - последняя работа
        if isinstance(latest_exp, dict):
            return latest_exp.get('position', 'Не указана')
    return 'Не указана'

def extract_experience_from_profile(user: User) -> str:
    """Извлечение опыта работы из профиля пользователя"""
    if user.work_experience:
        return f"{len(user.work_experience)} позиций"
    return 'Нет опыта'

def extract_education_from_profile(user: User) -> str:
    """Извлечение образования из профиля пользователя"""
    if user.education and len(user.education) > 0:
        latest_edu = user.education[0]
        if isinstance(latest_edu, dict):
            return f"{latest_edu.get('degree', '')} - {latest_edu.get('institution', '')}"
    return 'Не указано'

async def analyze_profile_with_ai(profile_text: str, job_description: str) -> Optional[dict]:
    """Анализ профиля через AI"""
    try:
        # Импортируем сервис анализа резюме
        from app.services.resume_analysis_service import get_resume_analysis_service
        
        # Получаем экземпляр сервиса
        service = get_resume_analysis_service()
        
        # Вызываем функцию анализа
        analysis_result = await service.analyze_resume(job_description, profile_text)
        
        return analysis_result
            
    except Exception as e:
        print(f"❌ Ошибка при анализе профиля AI: {e}")
        return None

async def analyze_resume_with_ai(resume_text: str, job_description: str) -> Optional[str]:
    """Анализ резюме через нейронку"""
    try:
        # Импортируем сервис анализа резюме
        from app.services.resume_analysis_service import get_resume_analysis_service
        
        # Получаем экземпляр сервиса
        service = get_resume_analysis_service()
        
        # Вызываем функцию анализа (параметры в правильном порядке)
        analysis_result = await service.analyze_resume(job_description, resume_text)
        
        if analysis_result and "basic_info" in analysis_result:
            # Формируем подробный текст анализа
            basic_info = analysis_result["basic_info"]
            detailed_analysis = analysis_result.get("detailed_analysis", {})
            
            analysis_text = f"""
🤖 АНАЛИЗ ИИ:

📊 ОСНОВНАЯ ИНФОРМАЦИЯ:
• Имя: {basic_info.get('name', 'Не указано')}
• Позиция: {basic_info.get('position', 'Не определена')}
• Опыт: {basic_info.get('experience', 'Не указан')}
• Образование: {basic_info.get('education', 'Не указано')}
• Соответствие: {basic_info.get('match_score', '0%')}

🎯 РЕКОМЕНДАЦИЯ: {basic_info.get('recommendation', 'Требует дополнительного анализа')}

📝 ПОДРОБНЫЙ АНАЛИЗ:
{detailed_analysis.get('analysis_text', 'Подробный анализ не проведен')}

✅ СИЛЬНЫЕ СТОРОНЫ:
{chr(10).join([f"• {strength}" for strength in detailed_analysis.get('strengths', [])])}

❌ СЛАБЫЕ СТОРОНЫ:
{chr(10).join([f"• {weakness}" for weakness in detailed_analysis.get('weaknesses', [])])}

🔧 ОТСУТСТВУЮЩИЕ НАВЫКИ:
{chr(10).join([f"• {skill}" for skill in detailed_analysis.get('missing_skills', [])])}


🛡️ ПРОВЕРКА НА МАНИПУЛЯЦИИ:
{analysis_result.get('anti_manipulation', {}).get('suspicious_phrases_found', False) and '⚠️ Обнаружены подозрительные фразы' or '✅ Резюме выглядит честно'}
"""
            return analysis_text.strip()
        else:
            return "Анализ не удался"
            
    except Exception as e:
        print(f"❌ Ошибка при анализе резюме нейронкой: {e}")
        return None
