from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Interview, Resume, Vacancy, User, ApplicationStatus
from app.auth import get_current_hr_user
from pydantic import BaseModel
from typing import Optional
import httpx
import asyncio
import base64
from datetime import datetime, timedelta

router = APIRouter()

class OfferData(BaseModel):
    candidate_name: str
    position_title: str
    company_name: str
    department: str
    salary: str
    start_date: str
    deadline_date: str
    hiring_manager_name: str
    hiring_manager_title: str
    company_address: str
    company_phone: str
    date: str

@router.post("/generate/{interview_id}")
async def generate_offer(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)
):
    """Генерация оффера для кандидата после успешного интервью"""
    
    # Получаем интервью с связанными данными
    interview = db.query(Interview).options(
        joinedload(Interview.resume).joinedload(Resume.user),
        joinedload(Interview.vacancy)
    ).filter(Interview.id == interview_id).first()
    
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Интервью не найдено"
        )
    
    # Проверяем, что интервью завершено и есть отчет
    if not interview.summary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Интервью должно быть завершено с отчетом для генерации оффера"
        )
    
    # Получаем данные кандидата
    candidate = interview.resume.user
    vacancy = interview.vacancy
    
    if not candidate or not vacancy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недостаточно данных для генерации оффера"
        )
    
    # Формируем имя кандидата
    candidate_name = candidate.full_name or f"{candidate.first_name or ''} {candidate.last_name or ''}".strip() or candidate.username
    
    # Формируем зарплату
    salary = "Не указана"
    if vacancy.salary_from and vacancy.salary_to:
        salary = f"{vacancy.salary_from:,} - {vacancy.salary_to:,} руб."
    elif vacancy.salary_from:
        salary = f"от {vacancy.salary_from:,} руб."
    elif vacancy.salary_to:
        salary = f"до {vacancy.salary_to:,} руб."
    
    # Вычисляем даты
    current_date = datetime.now()
    
    # Русские названия месяцев
    months_ru = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
        7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }
    
    # Форматируем даты на русском
    deadline_date = f"{current_date.day} {months_ru[current_date.month]} {current_date.year} г."
    start_date = "с вами свяжется HR в телеграмме"
    
    # Формируем данные для оффера
    offer_data = OfferData(
        candidate_name=candidate_name,
        position_title=vacancy.title,
        company_name=vacancy.company or "Наша компания",
        department="IT-департамент",  # Можно сделать настраиваемым
        salary=salary,
        start_date=start_date,
        deadline_date=deadline_date,
        hiring_manager_name=current_user.full_name or current_user.username,
        hiring_manager_title="Руководитель отдела",
        company_address="ул. Технологическая, д. 1, Москва",  # Можно сделать настраиваемым
        company_phone="+7 (495) 123-45-67",  # Можно сделать настраиваемым
        date=deadline_date
    )
    
    try:
        # Отправляем запрос на генерацию PDF
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://mojarung-offer-generator-8ee2.twc1.net/generate-offer",
                json=offer_data.dict(),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                # Обновляем статус резюме на "принято"
                resume = interview.resume
                resume.status = ApplicationStatus.ACCEPTED
                resume.updated_at = datetime.utcnow()
                db.commit()
                
                # Кодируем PDF в base64
                pdf_base64 = base64.b64encode(response.content).decode('utf-8')
                
                # Возвращаем PDF файл
                return {
                    "message": "Оффер успешно сгенерирован",
                    "pdf_data": pdf_base64,
                    "filename": f"offer_{candidate_name.replace(' ', '_')}_{vacancy.title.replace(' ', '_')}.pdf"
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Ошибка генерации оффера: {response.status_code}"
                )
                
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Таймаут при генерации оффера"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при генерации оффера: {str(e)}"
        )
