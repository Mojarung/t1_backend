from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Interview, Resume, Vacancy, User, ApplicationStatus
from app.auth import get_current_hr_user
from app.services.candidate_selection_service import get_candidate_selection_service
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter()

class CandidateRanking(BaseModel):
    candidate_id: int
    candidate_name: str
    resume_id: int
    interview_id: int
    ranking_score: float
    reasoning: str
    interview_summary: Optional[str] = None

class CandidateSelectionResponse(BaseModel):
    vacancy_id: int
    vacancy_title: str
    total_candidates: int
    ranked_candidates: List[CandidateRanking]

@router.get("/vacancies")
async def get_vacancies_with_completed_interviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    """Получить список вакансий, по которым есть завершенные интервью"""
    try:
        # Получаем вакансии, по которым есть завершенные интервью (с summary)
        vacancies = db.query(Vacancy).join(Interview).filter(
            Interview.summary.isnot(None),
            Interview.summary != ""
        ).distinct().all()
        
        result = []
        for vacancy in vacancies:
            # Подсчитываем количество завершенных интервью по этой вакансии
            completed_interviews_count = db.query(Interview).filter(
                Interview.vacancy_id == vacancy.id,
                Interview.summary.isnot(None),
                Interview.summary != ""
            ).count()
            
            result.append({
                "id": vacancy.id,
                "title": vacancy.title,
                "company": vacancy.company or "Компания не указана",
                "completed_interviews_count": completed_interviews_count
            })
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении вакансий: {str(e)}"
        )

@router.post("/select-best/{vacancy_id}")
async def select_best_candidates(
    vacancy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    """Выбрать лучших кандидатов для вакансии с помощью ИИ"""
    try:
        # Получаем вакансию
        vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
        if not vacancy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Вакансия не найдена"
            )
        
        # Получаем все завершенные интервью по этой вакансии
        interviews = db.query(Interview).options(
            joinedload(Interview.resume).joinedload(Resume.user)
        ).filter(
            Interview.vacancy_id == vacancy_id,
            Interview.summary.isnot(None),
            Interview.summary != ""
        ).all()
        
        if not interviews:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="По данной вакансии нет завершенных интервью"
            )
        
        # Подготавливаем данные для ИИ
        vacancy_data = {
            "title": vacancy.title,
            "description": vacancy.description or "",
            "requirements": vacancy.requirements or "",
            "company": vacancy.company or "",
            "experience_level": vacancy.experience_level or "",
            "employment_type": vacancy.employment_type or "",
            "salary_from": vacancy.salary_from,
            "salary_to": vacancy.salary_to
        }
        
        candidates_data = []
        for interview in interviews:
            candidate = interview.resume.user
            candidate_data = {
                "candidate_id": candidate.id,
                "candidate_name": candidate.full_name or f"{candidate.first_name or ''} {candidate.last_name or ''}".strip() or candidate.username,
                "resume_id": interview.resume_id,
                "interview_id": interview.id,
                "interview_summary": interview.summary,
                "candidate_skills": [],
                "candidate_experience": getattr(candidate, 'work_experience', []) or [],
                "candidate_education": getattr(candidate, 'education', []) or []
            }
            candidates_data.append(candidate_data)
        
        # Вызываем ИИ для ранжирования кандидатов
        service = get_candidate_selection_service()
        ai_response = await service.rank_candidates_with_ai(vacancy_data, candidates_data)
        
        # Формируем ответ
        ranked_candidates = []
        for candidate_data in ai_response.get("ranked_candidates", []):
            ranked_candidates.append(CandidateRanking(
                candidate_id=candidate_data["candidate_id"],
                candidate_name=candidate_data["candidate_name"],
                resume_id=candidate_data["resume_id"],
                interview_id=candidate_data["interview_id"],
                ranking_score=candidate_data["ranking_score"],
                reasoning=candidate_data["reasoning"],
                interview_summary=candidate_data.get("interview_summary")
            ))
        
        return CandidateSelectionResponse(
            vacancy_id=vacancy_id,
            vacancy_title=vacancy.title,
            total_candidates=len(ranked_candidates),
            ranked_candidates=ranked_candidates
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при выборе лучших кандидатов: {str(e)}"
        )

