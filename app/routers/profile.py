from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from app.database import get_db
from app.models import User, WorkExperience
from app.auth import get_current_user
from app.schemas import XPInfoResponse, XPUpdateResponse
from app.services.async_resume_processor import async_resume_processor
from app.services.xp_service import xp_service
from app.services.roadmap_service import get_roadmap_service
from datetime import datetime, date
import os
import shutil
import httpx
import asyncio
import json

router = APIRouter()

@router.post("/analyze-resume")
async def analyze_resume_for_profile(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Анализ резюме для автоматического заполнения профиля пользователя"""
    
    # Создаем временную директорию для файла
    upload_dir = "uploads/temp_resumes"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Генерируем уникальное имя файла
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"profile_{current_user.id}_{timestamp}_{file.filename}"
    file_path = os.path.join(upload_dir, filename)
    
    # Сохраняем файл
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при сохранении файла: {str(e)}"
        )
    
    # Запускаем асинхронный анализ
    background_tasks.add_task(
        analyze_and_fill_profile, 
        current_user.id,
        file_path,
        db
    )
    
    return {"message": "Резюме загружено, анализ запущен"}

async def analyze_and_fill_profile(user_id: int, file_path: str, db: Session):
    """Асинхронная функция для анализа резюме и заполнения профиля"""
    try:
        print(f"🔄 Начинаем анализ резюме для пользователя {user_id}")
        
        # 1. Извлекаем текст через OCR
        ocr_text = await extract_text_with_ocr(file_path)
        if not ocr_text:
            print(f"❌ OCR не смог извлечь текст из файла {file_path}")
            return
        
        print(f"✅ OCR извлек текст: {len(ocr_text)} символов")
        
        # 2. Анализируем резюме через AI
        profile_data = await analyze_resume_with_ai(ocr_text)
        if not profile_data:
            print(f"❌ AI не смог проанализировать резюме для пользователя {user_id}")
            return
        
        print(f"✅ AI проанализировал резюме: {profile_data}")
        print(f"🔍 Skills section: {profile_data.get('skills', {})}")
        print(f"🔍 Other competencies: {profile_data.get('skills', {}).get('other_competencies', [])}")
        
        # 3. Обновляем профиль пользователя
        await update_user_profile(user_id, profile_data, db)
        
        print(f"✅ Профиль пользователя {user_id} обновлен")
        
    except Exception as e:
        print(f"❌ Ошибка при анализе резюме для пользователя {user_id}: {e}")
    finally:
        # Удаляем временный файл
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Ошибка при удалении временного файла: {e}")

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

async def analyze_resume_with_ai(resume_text: str) -> Optional[Dict[str, Any]]:
    """Анализ резюме через AI для извлечения данных профиля"""
    try:
        # Импортируем сервис анализа резюме
        from app.services.resume_analysis_service import get_resume_analysis_service
        
        # Получаем экземпляр сервиса
        service = get_resume_analysis_service()
        
        # Вызываем специальный метод для анализа профиля
        profile_data = await service.analyze_resume_for_profile(resume_text)
        
        if profile_data:
            # Форматируем данные для сохранения в профиль
            formatted_data = {
                "first_name": profile_data.get("personal_info", {}).get("first_name") or "—",
                "last_name": profile_data.get("personal_info", {}).get("last_name") or "—",
                "phone": profile_data.get("personal_info", {}).get("phone") or "—",
                "location": profile_data.get("personal_info", {}).get("location") or "—",
                "about": profile_data.get("personal_info", {}).get("about") or "—",
                "desired_salary": profile_data.get("professional_info", {}).get("desired_salary"),
                "employment_type": profile_data.get("professional_info", {}).get("employment_type"),
                "ready_to_relocate": profile_data.get("professional_info", {}).get("ready_to_relocate"),
                "programming_languages": profile_data.get("skills", {}).get("programming_languages", []),
                "foreign_languages": profile_data.get("skills", {}).get("foreign_languages", []),
                "other_competencies": profile_data.get("skills", {}).get("other_competencies", []),
                "work_experience": profile_data.get("experience", []),
                "education": profile_data.get("education", [])
            }
            
            return formatted_data
        else:
            return None
            
    except Exception as e:
        print(f"❌ Ошибка при анализе резюме AI: {e}")
        return None


async def update_user_profile(user_id: int, profile_data: Dict[str, Any], db: Session):
    """Обновление профиля пользователя на основе анализа резюме"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            print(f"❌ Пользователь {user_id} не найден")
            return
        
        # Обновляем основные поля
        if profile_data.get("first_name") and profile_data["first_name"] != "—":
            user.first_name = profile_data["first_name"]
        
        if profile_data.get("last_name") and profile_data["last_name"] != "—":
            user.last_name = profile_data["last_name"]
        
        if profile_data.get("about") and profile_data["about"] != "—":
            user.about = profile_data["about"]
        
        if profile_data.get("location") and profile_data["location"] != "—":
            user.location = profile_data["location"]
        
        if profile_data.get("phone") and profile_data["phone"] != "—":
            user.phone = profile_data["phone"]
        
        if profile_data.get("desired_salary") and profile_data["desired_salary"] > 0:
            user.desired_salary = profile_data["desired_salary"]
        
        # Обновляем дополнительные поля
        if profile_data.get("employment_type"):
            from app.models import EmploymentType
            try:
                # Если значение уже является enum, используем его напрямую
                if isinstance(profile_data["employment_type"], EmploymentType):
                    user.employment_type = profile_data["employment_type"]
                else:
                    user.employment_type = EmploymentType(profile_data["employment_type"])
            except ValueError:
                print(f"Неверное значение employment_type: {profile_data['employment_type']}")
                pass
        
        if profile_data.get("ready_to_relocate") is not None:
            user.ready_to_relocate = profile_data["ready_to_relocate"]
        
        # Обновляем JSON поля
        if profile_data.get("programming_languages"):
            print(f"🔧 Setting programming_languages: {profile_data['programming_languages']}")
            user.programming_languages = profile_data["programming_languages"]
        
        if profile_data.get("foreign_languages"):
            print(f"🔧 Setting foreign_languages: {profile_data['foreign_languages']}")
            user.foreign_languages = profile_data["foreign_languages"]
        
        if profile_data.get("other_competencies"):
            print(f"🔧 Setting other_competencies: {profile_data['other_competencies']}")
            user.other_competencies = profile_data["other_competencies"]
        
        if profile_data.get("education"):
            user.education = profile_data["education"]
        
        if profile_data.get("work_experience"):
            user.work_experience = profile_data["work_experience"]
        
        # Обновляем XP пользователя
        xp_info = xp_service.update_user_xp(user, db)
        print(f"💎 XP пользователя {user_id} обновлен: {xp_info['old_xp']} -> {xp_info['total_xp']} (+{xp_info['xp_gained']})")
        
        print(f"✅ Профиль пользователя {user_id} успешно обновлен")
        
    except Exception as e:
        print(f"❌ Ошибка при обновлении профиля пользователя {user_id}: {e}")
        db.rollback()

@router.get("/profile")
async def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение профиля текущего пользователя"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "phone": current_user.phone,
        "location": current_user.location,
        "about": current_user.about,
        "desired_salary": current_user.desired_salary,
        "ready_to_relocate": current_user.ready_to_relocate,
        "employment_type": current_user.employment_type.value if current_user.employment_type else None,
        "education": current_user.education,
        "work_experience": current_user.work_experience,
        "foreign_languages": current_user.foreign_languages,
        "other_competencies": current_user.other_competencies,
        "programming_languages": current_user.programming_languages,
        "xp": current_user.xp,
        "created_at": current_user.created_at
    }

@router.put("/profile")
async def update_user_profile_manual(
    profile_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Ручное обновление профиля пользователя"""
    try:
        # Обновляем только переданные поля с проверкой типов
        for field, value in profile_data.items():
            if hasattr(current_user, field) and value is not None:
                # Специальная обработка для enum полей
                if field == "employment_type" and isinstance(value, str):
                    from app.models import EmploymentType
                    try:
                        setattr(current_user, field, EmploymentType(value))
                    except ValueError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Неверное значение для employment_type: {value}"
                        )
                elif field == "birth_date" and isinstance(value, str):
                    from datetime import datetime
                    try:
                        # Парсим дату из строки
                        parsed_date = datetime.fromisoformat(value.replace('Z', '+00:00')).date()
                        setattr(current_user, field, parsed_date)
                    except ValueError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Неверный формат даты для birth_date: {value}"
                        )
                else:
                    setattr(current_user, field, value)
        
        # Обновляем XP пользователя
        xp_info = xp_service.update_user_xp(current_user, db)
        
        return {
            "message": "Профиль успешно обновлен",
            "xp_info": {
                "total_xp": xp_info["total_xp"],
                "xp_gained": xp_info["xp_gained"],
                "completion_percentage": xp_info["completion_percentage"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении профиля: {str(e)}"
        )

@router.post("/resume-upload-seen")
async def mark_resume_upload_seen(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Отметить, что пользователь видел страницу загрузки резюме"""
    try:
        current_user.resume_upload_seen = True
        db.commit()
        
        return {"message": "Флаг resume_upload_seen установлен"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении флага: {str(e)}"
        )

@router.post("/resume-upload-skipped")
async def mark_resume_upload_skipped(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Отметить, что пользователь пропустил загрузку резюме"""
    try:
        current_user.resume_upload_skipped = True
        db.commit()
        
        return {"message": "Флаг resume_upload_skipped установлен"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении флага: {str(e)}"
        )

@router.get("/xp", response_model=XPInfoResponse)
async def get_user_xp_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение детальной информации о XP пользователя"""
    try:
        xp_info = xp_service.calculate_user_xp(current_user)
        return {
            "user_id": current_user.id,
            "current_xp": current_user.xp,
            "calculated_xp": xp_info["total_xp"],
            "completion_percentage": xp_info["completion_percentage"],
            "filled_fields": xp_info["filled_fields"],
            "total_fields": xp_info["total_fields"],
            "completion_bonus": xp_info["completion_bonus"],
            "base_xp": xp_info["base_xp"],
            "next_bonus": xp_info["next_bonus"],
            "xp_breakdown": xp_info["xp_breakdown"]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении информации о XP: {str(e)}"
        )

@router.post("/xp/recalculate", response_model=XPUpdateResponse)
async def recalculate_user_xp(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Принудительный пересчет XP пользователя"""
    try:
        xp_info = xp_service.update_user_xp(current_user, db)
        return {
            "message": "XP успешно пересчитан",
            "old_xp": xp_info["old_xp"],
            "new_xp": xp_info["total_xp"],
            "xp_gained": xp_info["xp_gained"],
            "completion_percentage": xp_info["completion_percentage"]
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при пересчете XP: {str(e)}"
        )

'''@router.post("/roadmap/generate")
async def generate_development_roadmap(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Генерация игровой карты развития (роадмапа) на основе профиля. Требуется заполненность 60%+."""
    try:
        service = get_roadmap_service()
        roadmap = await service.generate_for_user(db, current_user)
        return {"roadmap": roadmap}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ошибка генерации роадмапа: {e}")

@router.get("/roadmap")
async def get_development_roadmap(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение сохраненной карты развития пользователя."""
    service = get_roadmap_service()
    roadmap = service.get_for_user(db, current_user)
    if not roadmap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Роадмап не найден. Сгенерируйте его сначала.")
    return {"roadmap": roadmap}'''