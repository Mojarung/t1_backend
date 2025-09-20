from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Interview, Resume, Vacancy, User
from app.schemas import InterviewCreate, InterviewUpdate, InterviewResponse
from app.auth import get_current_user, get_current_hr_user
from app.models import ApplicationStatus

router = APIRouter()

@router.post("/", response_model=InterviewResponse)
def create_interview(
    interview: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    resume = db.query(Resume).filter(Resume.id == interview.resume_id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    
    vacancy = db.query(Vacancy).filter(Vacancy.id == interview.vacancy_id).first()
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )
    
    if resume.vacancy_id != interview.vacancy_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume does not belong to this vacancy"
        )
    
    existing_interview = db.query(Interview).filter(
        Interview.resume_id == interview.resume_id,
        Interview.vacancy_id == interview.vacancy_id
    ).first()
    if existing_interview:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview already exists for this resume and vacancy"
        )
    
    db_interview = Interview(**interview.dict())
    db.add(db_interview)
    db.commit()
    db.refresh(db_interview)
    return db_interview

@router.get("/", response_model=List[InterviewResponse])
def get_interviews(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    return db.query(Interview).options(
        joinedload(Interview.resume).joinedload(Resume.user),
        joinedload(Interview.vacancy)
    ).offset(skip).limit(limit).all()

@router.get("/vacancy/{vacancy_id}", response_model=List[InterviewResponse])
def get_interviews_by_vacancy(
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
    
    return db.query(Interview).options(
        joinedload(Interview.resume).joinedload(Resume.user),
        joinedload(Interview.vacancy)
    ).filter(Interview.vacancy_id == vacancy_id).all()

@router.get("/{interview_id}", response_model=InterviewResponse)
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    interview = db.query(Interview).options(
        joinedload(Interview.resume).joinedload(Resume.user),
        joinedload(Interview.vacancy)
    ).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found"
        )
    
    if current_user.role.value != "hr":
        if not interview.resume or interview.resume.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
    
    return interview

@router.put("/{interview_id}", response_model=InterviewResponse)
def update_interview(
    interview_id: int,
    interview_update: InterviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found"
        )
    
    update_data = interview_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(interview, field, value)
    
    # Если добавлен summary, обновляем статус заявки
    if interview_update.summary:
        resume = db.query(Resume).filter(Resume.id == interview.resume_id).first()
        if resume:
            resume.status = ApplicationStatus.INTERVIEW_COMPLETED
    
    db.commit()
    db.refresh(interview)
    return interview

@router.delete("/{interview_id}")
def delete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found"
        )
    
    db.delete(interview)
    db.commit()
    return {"message": "Interview deleted successfully"}
