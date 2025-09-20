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
