from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.database import get_db
from app.models import User, Vacancy, Resume, Interview, ResumeAnalysis, InterviewStatus, UserRole, ApplicationStatus
from app.auth import get_current_user, get_current_hr_user
from app.schemas import UserResponse
from typing import Dict, Any

router = APIRouter()

@router.get("/debug/stats")
def debug_stats(db: Session = Depends(get_db)):
    """Debug endpoint для проверки данных в базе"""
    try:
        user_count = db.query(User).count()
        vacancy_count = db.query(Vacancy).count()
        resume_count = db.query(Resume).count()
        interview_count = db.query(Interview).count()
        
        return {
            "users": user_count,
            "vacancies": vacancy_count,
            "resumes": resume_count,
            "interviews": interview_count
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/candidate/stats")
def get_candidate_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение статистики для кандидата"""
    
    try:
        # Общее количество интервью
        total_interviews = db.query(Interview).join(Resume).filter(
            Resume.user_id == current_user.id
        ).count()
        
        # Завершенные интервью
        completed_interviews = db.query(Interview).join(Resume).filter(
            Resume.user_id == current_user.id,
            Interview.status == InterviewStatus.COMPLETED
        ).count()
        
        # Запланированные интервью
        scheduled_interviews = db.query(Interview).join(Resume).filter(
            Resume.user_id == current_user.id,
            Interview.status == InterviewStatus.NOT_STARTED
        ).count()
        
        # Средний балл по завершенным интервью
        avg_score = db.query(func.avg(Interview.pass_percentage)).join(Resume).filter(
            Resume.user_id == current_user.id,
            Interview.status == InterviewStatus.COMPLETED,
            Interview.pass_percentage.isnot(None)
        ).scalar() or 0
        
        return {
            "totalInterviews": total_interviews,
            "completedInterviews": completed_interviews,
            "scheduledInterviews": scheduled_interviews,
            "averageScore": round(avg_score, 1) if avg_score else 0
        }
    except Exception as e:
        print(f"Error in get_candidate_stats: {e}")
        # Возвращаем нулевые значения в случае ошибки
        return {
            "totalInterviews": 0,
            "completedInterviews": 0,
            "scheduledInterviews": 0,
            "averageScore": 0
        }

@router.get("/hr/stats")
def get_hr_stats(
    current_user: User = Depends(get_current_hr_user),
    db: Session = Depends(get_db)
):
    """Получение статистики для HR"""
    
    try:
        # Количество заявок на вакансии текущего HR (все заявки, не только уникальные кандидаты)
        total_candidates = db.query(Resume).join(Vacancy).filter(
            Vacancy.creator_id == current_user.id,
            Resume.user_id.isnot(None)
        ).count()
        
        # Успешные наймы (принятые заявки)
        successful_hires = db.query(Resume).join(Vacancy).filter(
            Vacancy.creator_id == current_user.id,
            Resume.status == ApplicationStatus.ACCEPTED
        ).count()
        
        # Ожидающие заявки (новые заявки)
        pending_applications = db.query(Resume).join(Vacancy).filter(
            Vacancy.creator_id == current_user.id,
            Resume.status == ApplicationStatus.PENDING
        ).count()
        
        # Общее количество интервью (пока заглушка)
        total_interviews = 0
        
        return {
            "totalCandidates": total_candidates,
            "totalInterviews": total_interviews,
            "successfulHires": successful_hires,
            "pending": pending_applications
        }
    except Exception as e:
        print(f"Error in get_hr_stats: {e}")
        # Возвращаем нулевые значения в случае ошибки
        return {
            "totalCandidates": 0,
            "totalInterviews": 0,
            "successfulHires": 0,
            "pending": 0
        }

@router.get("/candidate/recent-interviews")
def get_candidate_recent_interviews(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение последних интервью кандидата"""
    
    try:
        interviews = db.query(Interview).join(Resume).join(Vacancy).filter(
            Resume.user_id == current_user.id
        ).order_by(desc(Interview.created_at)).limit(10).all()
        
        result = []
        for interview in interviews:
            result.append({
                "id": interview.id,
                "company": interview.vacancy.title if interview.vacancy else "Неизвестная компания",
                "position": interview.vacancy.title if interview.vacancy else "Неизвестная позиция",
                "date": interview.scheduled_date.isoformat() if interview.scheduled_date else None,
                "status": interview.status.value,
                "score": interview.pass_percentage,
                "feedback": interview.summary
            })
        
        return result
    except Exception as e:
        return []

@router.get("/hr/recent-interviews")
def get_hr_recent_interviews(
    current_user: User = Depends(get_current_hr_user),
    db: Session = Depends(get_db)
):
    """Получение последних интервью для HR"""
    
    try:
        interviews = db.query(Interview).join(Vacancy).filter(
            Vacancy.creator_id == current_user.id
        ).order_by(desc(Interview.created_at)).limit(10).all()
        
        result = []
        for interview in interviews:
            candidate_name = "Неизвестный кандидат"
            if interview.resume and interview.resume.user:
                candidate_name = interview.resume.user.full_name or interview.resume.user.username
            
            result.append({
                "id": interview.id,
                "candidate": candidate_name,
                "position": interview.vacancy.title if interview.vacancy else "Неизвестная позиция",
                "date": interview.scheduled_date.isoformat() if interview.scheduled_date else None,
                "score": interview.pass_percentage,
                "status": interview.status.value
            })
        
        return result
    except Exception as e:
        return []


@router.get("/hr/interviews")
def get_hr_interviews_endpoint(
    current_user: User = Depends(get_current_hr_user),
    db: Session = Depends(get_db)
):
    """Получение интервью для HR (дублирует существующий роут)"""
    return get_hr_recent_interviews(current_user, db)

@router.get("/candidates")
def get_candidates(
    current_user: User = Depends(get_current_hr_user),
    db: Session = Depends(get_db)
):
    """Получение всех заявок для HR"""
    
    try:
        # Получаем ВСЕ резюме на вакансии текущего HR (не группируем)
        resumes_query = db.query(Resume).join(Vacancy).filter(
            Vacancy.creator_id == current_user.id
        ).order_by(desc(Resume.uploaded_at))
        
        resumes = resumes_query.all()
        
        result = []
        for resume in resumes:
            candidate = resume.user
            
            # Извлекаем рекомендацию из заметок
            ai_recommendation = "Не проанализировано"
            if resume.notes and "🤖 Рекомендация ИИ:" in resume.notes:
                ai_part = resume.notes.split("🤖 Рекомендация ИИ:")[-1].strip()
                if "Рекомендуется к интервью" in ai_part:
                    ai_recommendation = "Да"
                elif "Не рекомендуется" in ai_part:
                    ai_recommendation = "Нет"
                else:
                    ai_recommendation = "Требует доработки"
            elif resume.notes and "РЕКОМЕНДАЦИЯ_СТРУКТУРА:" in resume.notes:
                rec = resume.notes.split("РЕКОМЕНДАЦИЯ_СТРУКТУРА:")[-1].strip()
                if "Рекомендуется" in rec:
                    ai_recommendation = "Да"
                elif "Не рекомендуется" in rec:
                    ai_recommendation = "Нет"
                else:
                    ai_recommendation = "Требует доработки"
            
            download_path = f"/resumes/{resume.id}/download"
            
            result.append({
                "id": resume.id,
                "candidate_name": candidate.full_name or candidate.username,
                "position": resume.vacancy.title if resume.vacancy else "Не указана",
                "date": resume.uploaded_at.strftime("%d %b %Y"),
                "type": "Техническое",  # Можно добавить логику определения типа
                "status": resume.status.value,
                "statusColor": get_status_color_by_resume_status(resume.status),
                "recommended": ai_recommendation,
                "resume_url": download_path,
                "vacancy_description": resume.vacancy.description if resume.vacancy else "Описание не найдено",
                "ai_analysis": resume.notes if resume.notes else "Анализ не проведен"
            })
        
        return result
    except Exception as e:
        print(f"Error in get_candidates: {e}")
        return []

def get_status_color(status):
    """Получение цвета статуса"""
    if not status:
        return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
    
    status_colors = {
        InterviewStatus.COMPLETED: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
        InterviewStatus.IN_PROGRESS: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
        InterviewStatus.NOT_STARTED: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
    }
    
    return status_colors.get(status, "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200")

def get_status_color_by_resume_status(status):
    """Получение цвета статуса резюме"""
    from app.models import ApplicationStatus
    
    status_colors = {
        ApplicationStatus.PENDING: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
        ApplicationStatus.ACCEPTED: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
        ApplicationStatus.REJECTED: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
        ApplicationStatus.INTERVIEW_SCHEDULED: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
        ApplicationStatus.INTERVIEW_COMPLETED: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200"
    }
    
    return status_colors.get(status, "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200")