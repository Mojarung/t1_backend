from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, vacancies, resumes, interviews, resume_analysis, analytics, applications, offers, candidate_selection, profile, qa_session, ai_resume_interview
from app.database import create_tables
from app.logging_config import logger, log_startup, log_request
import time
import os
from dotenv import load_dotenv
import logging

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="VTB HR Backend", version="1.0.0")

# Универсальная CORS-конфигурация для локальной разработки и продакшна
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js frontend local
        "http://127.0.0.1:3000", # Next.js frontend local
        "http://localhost:3001",  # Next.js frontend local (альтернативный порт)
        "http://127.0.0.1:3001", # Next.js frontend local (альтернативный порт)
        "https://moretech-frontend-bb9dc4246c9f.herokuapp.com", # Next.js frontend production
        "http://localhost:8000",  # Backend local
        "http://127.0.0.1:8000",  # Backend local
        "http://localhost", # Localhost testing
        "http://127.0.0.1", # Localhost testing
        "https://moretech-backend-80a7fa1a3fab.herokuapp.com", # Backend production (for Swagger UI if needed)
        "https://moretech-avatar-dd041c6ae94a.herokuapp.com",
        "https://api.aws.us-east-1.cerebrium.ai/v4/p-d3989137/ai-avatar-service/interview/",
        "https://t1-frontend-0e7ff7a1a18a.herokuapp.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Логирование запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Логируем входящий запрос
    log_request(f"{request.method} {request.url.path} - Client: {request.client.host if request.client else 'unknown'}")
    
    response = await call_next(request)
    
    # Логируем время выполнения
    process_time = time.time() - start_time
    logger.info(f"RESPONSE: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.4f}s")
    
    return response

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(vacancies.router, prefix="/vacancies", tags=["vacancies"])
app.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
app.include_router(interviews.router, prefix="/interviews", tags=["interviews"])
app.include_router(resume_analysis.router, prefix="/resume-analysis", tags=["resume-analysis"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(applications.router, prefix="/applications", tags=["applications"])
app.include_router(offers.router, prefix="/offers", tags=["offers"])
app.include_router(candidate_selection.router, prefix="/candidate-selection", tags=["candidate-selection"])
app.include_router(profile.router, prefix="/profile", tags=["profile"])
app.include_router(qa_session.router, prefix="/qa", tags=["qa-session"])
app.include_router(ai_resume_interview.router, prefix="/ai-resume-interview", tags=["ai-resume-interview"])
@app.on_event("startup")
async def startup_event():
    try:
        log_startup("Приложение запускается...")
        log_startup("Проверяем подключение к базе данных...")
        create_tables()
        log_startup("Таблицы созданы успешно!")
        
        # Запускаем фоновую очередь для обработки резюме
        from app.services.job_queue import start_job_workers_and_recover
        start_job_workers_and_recover()
        log_startup("Фоновая очередь обработки резюме запущена!")
        
        log_startup("VTB HR Backend готов к работе!")
    except Exception as e:
        logger.error(f"STARTUP ERROR: {str(e)}")
        # Не падаем, продолжаем работу
        log_startup("Приложение запущено с ошибками базы данных")


@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "VTB HR Backend API"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}