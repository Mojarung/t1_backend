from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app.models import Vacancy, User, VacancyStatus, Resume
from app.schemas import VacancyCreate, VacancyUpdate, VacancyResponse
from app.auth import get_current_user, get_current_hr_user

router = APIRouter()

@router.post("/", response_model=VacancyResponse)
def create_vacancy(
    vacancy: VacancyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    db_vacancy = Vacancy(**vacancy.dict(), creator_id=current_user.id)
    db.add(db_vacancy)
    db.commit()
    db.refresh(db_vacancy)
    return db_vacancy

@router.get("/", response_model=List[VacancyResponse])
def get_vacancies(
    skip: int = 0,
    limit: int = 100,
    status: VacancyStatus = None,
    db: Session = Depends(get_db)
):
    query = db.query(Vacancy).join(User)
    if status:
        query = query.filter(Vacancy.status == status)
    return query.offset(skip).limit(limit).all()

@router.get("/formatted")
def get_formatted_vacancies(
    skip: int = 0,
    limit: int = 100,
    status: VacancyStatus = None,
    db: Session = Depends(get_db)
):
    """Получение вакансий в формате, ожидаемом frontend"""
    try:
        query = db.query(Vacancy).join(User)
        if status:
            query = query.filter(Vacancy.status == status)
        
        vacancies = query.offset(skip).limit(limit).all()
        
        result = []
        for vacancy in vacancies:
            # Форматируем зарплату
            salary = "Не указана"
            if vacancy.salary_from and vacancy.salary_to:
                salary = f"{vacancy.salary_from:,} - {vacancy.salary_to:,} ₽".replace(',', ' ')
            elif vacancy.salary_from:
                salary = f"от {vacancy.salary_from:,} ₽".replace(',', ' ')
            elif vacancy.salary_to:
                salary = f"до {vacancy.salary_to:,} ₽".replace(',', ' ')
            
            # Форматируем требования
            requirements = []
            if vacancy.requirements:
                requirements = [req.strip() for req in vacancy.requirements.split(',') if req.strip()]
            
            # Форматируем условия
            benefits = []
            if vacancy.benefits:
                benefits = [benefit.strip() for benefit in vacancy.benefits.split(',') if benefit.strip()]
            else:
                benefits = ["ДМС", "Обучение", "Гибкий график"]  # Дефолтные условия

            # Количество заявок
            applicants_count = 0
            try:
                applicants_count = vacancy.resumes and len(vacancy.resumes) or 0
            except Exception:
                applicants_count = 0
            
            # Компания: игнорируем плейсхолдеры типа "string"
            company_value = (vacancy.company or "").strip()
            if not company_value or company_value.lower() == "string":
                company_display = vacancy.creator.full_name or vacancy.creator.username
            else:
                company_display = company_value

            result.append({
                "id": vacancy.id,
                "title": vacancy.title,
                "company": company_display,
                "location": vacancy.location or "Не указана",
                "salary": salary,
                "experience": vacancy.experience_level or "Не указан",
                "employment": vacancy.employment_type or "Полная занятость",
                "schedule": "Полный день",  # Можно добавить поле в модель
                "description": vacancy.description,
                "requirements": requirements,
                "benefits": benefits,
                "auto_interview_enabled": bool(getattr(vacancy, "auto_interview_enabled", False)),
                "auto_interview_threshold": getattr(vacancy, "auto_interview_threshold", None),
                "applicants": applicants_count,
                "postedDate": vacancy.created_at.strftime("%Y-%m-%d"),
                "creator_id": vacancy.creator_id,
                "created_at": vacancy.created_at.isoformat()
            })
        
        return result
    except Exception as e:
        print(f"Error in get_formatted_vacancies: {e}")
        return []

@router.get("/open", response_model=List[VacancyResponse])
def get_open_vacancies(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return db.query(Vacancy).join(User).filter(
        Vacancy.status == VacancyStatus.OPEN
    ).offset(skip).limit(limit).all()

@router.get("/{vacancy_id}", response_model=VacancyResponse)
def get_vacancy(vacancy_id: int, db: Session = Depends(get_db)):
    vacancy = db.query(Vacancy).join(User).filter(Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )
    return vacancy

@router.put("/{vacancy_id}", response_model=VacancyResponse)
def update_vacancy(
    vacancy_id: int,
    vacancy_update: VacancyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )
    
    if vacancy.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    update_data = vacancy_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vacancy, field, value)
    
    db.commit()
    db.refresh(vacancy)
    return vacancy

@router.delete("/{vacancy_id}")
def delete_vacancy(
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
    
    if vacancy.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    db.delete(vacancy)
    db.commit()
    return {"message": "Vacancy deleted successfully"}
