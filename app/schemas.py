from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from app.models import UserRole, VacancyStatus, InterviewStatus, ApplicationStatus, EmploymentType

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: UserRole
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    # Profile fields
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    birth_date: Optional[date] = None
    location: Optional[str] = None
    about: Optional[str] = None
    desired_salary: Optional[int] = None
    ready_to_relocate: Optional[bool] = None
    employment_type: Optional[EmploymentType] = None
    education: Optional[List[Dict[str, Any]]] = None
    work_experience: Optional[List[Dict[str, Any]]] = None
    # Новые поля для профиля
    foreign_languages: Optional[List[Dict[str, Any]]] = None
    other_competencies: Optional[List[str]] = None
    programming_languages: Optional[List[str]] = None
    # Флаги для отслеживания взаимодействия с резюме
    resume_upload_seen: Optional[bool] = None
    resume_upload_skipped: Optional[bool] = None
    # XP пользователя
    xp: Optional[int] = None

    @field_validator('programming_languages', 'other_competencies', mode='before')
    @classmethod
    def parse_string_to_list(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(',') if item.strip()]
        return v
    
    @field_validator('foreign_languages', mode='before')
    @classmethod
    def parse_foreign_languages(cls, v):
        if isinstance(v, str):
            # Если это строка, пытаемся разделить по запятым
            items = [item.strip() for item in v.split(',') if item.strip()]
            # Преобразуем в список объектов с языком и уровнем
            return [{"language": item, "level": "Не указан"} for item in items]
        return v

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    birth_date: Optional[date] = None
    location: Optional[str] = None
    about: Optional[str] = None
    desired_salary: Optional[int] = None
    ready_to_relocate: Optional[bool] = None
    employment_type: Optional[EmploymentType] = None
    education: Optional[List[Dict[str, Any]]] = None
    work_experience: Optional[List[Dict[str, Any]]] = None

class VacancyCreate(BaseModel):
    title: str
    description: str
    requirements: Optional[str] = None
    salary_from: Optional[int] = None
    salary_to: Optional[int] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    benefits: Optional[str] = None  # Условия работы (через запятую)
    company: Optional[str] = None
    status: VacancyStatus = VacancyStatus.OPEN
    original_url: Optional[str] = None
    # Авто-интервью
    auto_interview_enabled: Optional[bool] = False
    auto_interview_threshold: Optional[int] = None

class VacancyUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_from: Optional[int] = None
    salary_to: Optional[int] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    benefits: Optional[str] = None  # Условия работы (через запятую)
    company: Optional[str] = None
    status: Optional[VacancyStatus] = None
    original_url: Optional[str] = None
    # Авто-интервью
    auto_interview_enabled: Optional[bool] = None
    auto_interview_threshold: Optional[int] = None

class VacancyResponse(BaseModel):
    id: int
    title: str
    description: str
    requirements: Optional[str]
    salary_from: Optional[int]
    salary_to: Optional[int]
    location: Optional[str]
    employment_type: Optional[str]
    experience_level: Optional[str]
    benefits: Optional[str]  # Условия работы (через запятую)
    company: Optional[str] = None
    status: VacancyStatus
    original_url: Optional[str]
    # Авто-интервью
    auto_interview_enabled: bool
    auto_interview_threshold: Optional[int]
    creator_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
class ResumeAnalysisResponse(BaseModel):
    id: int
    resume_id: int
    name: Optional[str]
    position: Optional[str]
    experience: Optional[str]
    education: Optional[str]
    upload_date: Optional[str]
    match_score: Optional[str]
    key_skills: Optional[List[str]]
    recommendation: Optional[str]
    projects: Optional[List[str]]
    work_experience: Optional[List[str]]
    technologies: Optional[List[str]]
    achievements: Optional[List[str]]
    strengths: Optional[List[str]]
    weaknesses: Optional[List[str]]
    missing_skills: Optional[List[str]]
    brief_reason: Optional[str]
    structured: Optional[bool]
    effort_level: Optional[str]
    suspicious_phrases_found: Optional[bool]
    suspicious_examples: Optional[List[str]]
    created_at: datetime

    class Config:
        from_attributes = True
class ResumeResponse(BaseModel):
    id: int
    user_id: Optional[int]
    vacancy_id: int
    file_path: str
    original_filename: str
    uploaded_at: datetime
    processed: bool
    uploaded_by_hr: bool
    status: ApplicationStatus
    notes: Optional[str] = None
    updated_at: datetime
    user: Optional[UserResponse] = None
    vacancy: Optional[VacancyResponse] = None
    hidden_for_hr: Optional[bool] = False
    analysis: Optional[ResumeAnalysisResponse] = None
    class Config:
        from_attributes = True



class InterviewCreate(BaseModel):
    vacancy_id: int
    resume_id: int
    scheduled_date: datetime
    notes: Optional[str] = None

class InterviewUpdate(BaseModel):
    status: Optional[InterviewStatus] = None
    scheduled_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    dialogue: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    pass_percentage: Optional[float] = None
    notes: Optional[str] = None

class InterviewResponse(BaseModel):
    id: int
    vacancy_id: int
    resume_id: int
    status: InterviewStatus
    scheduled_date: Optional[datetime]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    duration_minutes: Optional[int]
    dialogue: Optional[Dict[str, Any]]
    summary: Optional[str]
    pass_percentage: Optional[float]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    # Связанные данные
    vacancy: Optional[VacancyResponse] = None
    resume: Optional[ResumeResponse] = None

    class Config:
        from_attributes = True

# Resume Analysis Schemas (from resume_analysis)
class ResumeAnalyzeRequest(BaseModel):
    job_description: str
    resume_text: str

class BasicInfo(BaseModel):
    name: Optional[str] = None
    position: Optional[str] = None
    experience: Optional[str] = None
    education: Optional[str] = None
    upload_date: str
    match_score: str
    key_skills: List[str]
    recommendation: str

class ExtendedInfo(BaseModel):
    projects: List[str]
    work_experience: List[str]
    technologies: List[str]
    achievements: List[str]

class ResumeQuality(BaseModel):
    structured: bool
    effort_level: str

class AntiManipulation(BaseModel):
    suspicious_phrases_found: bool
    examples: List[str]

class ResumeAnalyzeResponse(BaseModel):
    basic_info: BasicInfo
    extended_info: ExtendedInfo
    resume_quality: ResumeQuality
    anti_manipulation: AntiManipulation

class ApplicationCreate(BaseModel):
    cover_letter: Optional[str] = None

# QA Session Schemas - Схемы для вопросно-ответных сессий
class QAQuestion(BaseModel):
    id: str
    question: str
    field: str  # Поле профиля, которое уточняется
    required: bool = False
    max_attempts: int = 3
    current_attempt: int = 0

class QAAnswer(BaseModel):
    question_id: str
    answer: str
    attempt: int

class QASessionCreate(BaseModel):
    user_id: int

class QASessionResponse(BaseModel):
    id: int
    user_id: int
    status: str
    current_question_index: int
    questions: Optional[List[QAQuestion]] = None
    answers: Optional[List[QAAnswer]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class QASessionUpdate(BaseModel):
    answer: str
    skip: bool = False

# AI HR Candidate Search Schemas - Новые схемы для поиска кандидатов через AI
class CandidateSearchRequest(BaseModel):
    """
    Схема запроса для поиска кандидатов через AI-ассистента.
    HR отправляет описание вакансии и получает ранжированный список кандидатов.
    """
    job_title: str  # Название должности
    job_description: str  # Полное описание вакансии 
    required_skills: Optional[List[str]] = []  # Обязательные навыки для первичной фильтрации
    additional_requirements: Optional[str] = None  # Дополнительные требования в свободной форме
    experience_level: Optional[str] = None  # Уровень опыта (junior, middle, senior)
    max_candidates: Optional[int] = 20  # Максимальное количество кандидатов для обработки через LLM
    threshold_filter_limit: Optional[int] = 50  # Пороговое значение для дополнительной фильтрации

class CandidateMatch(BaseModel):
    """
    Информация о найденном кандидате с оценкой соответствия
    """
    user_id: int  # ID пользователя
    full_name: str  # Полное имя кандидата
    email: str  # Email кандидата  
    current_position: Optional[str] = None  # Текущая позиция
    experience_years: Optional[str] = None  # Опыт работы
    key_skills: Optional[List[str]] = []  # Ключевые навыки
    programming_languages: Optional[List[str]] = []  # Языки программирования
    match_score: float  # Оценка соответствия (0.0 - 1.0)
    ai_summary: str  # AI-саммари: почему подходит/не подходит
    strengths: Optional[List[str]] = []  # Сильные стороны кандидата
    growth_areas: Optional[List[str]] = []  # Области для роста
    similarity_score: Optional[float] = None  # Векторная схожесть профиля с вакансией

class CandidateSearchResponse(BaseModel):
    """
    Результат поиска кандидатов
    """
    job_title: str  # Название вакансии 
    total_profiles_found: int  # Общее количество найденных профилей после фильтрации
    processed_by_ai: int  # Количество профилей, обработанных через AI
    filters_applied: List[str]  # Примененные фильтры
    candidates: List[CandidateMatch]  # Список кандидатов, отсортированный по релевантности
    processing_time_seconds: Optional[float] = None  # Время обработки запроса

# XP Schemas - Схемы для системы опыта
class XPFieldBreakdown(BaseModel):
    """Детализация XP по конкретному полю профиля"""
    xp: int
    filled: bool
    description: str
    potential_xp: Optional[int] = None
    # Для сложных полей (массивов)
    items_count: Optional[int] = None
    items_counted: Optional[int] = None
    base_xp: Optional[int] = None
    items_xp: Optional[int] = None
    potential_base_xp: Optional[int] = None
    potential_per_item: Optional[int] = None
    max_items: Optional[int] = None

class NextBonus(BaseModel):
    """Информация о следующем бонусе за заполненность"""
    threshold: int
    bonus: int
    percentage_needed: float

class XPInfoResponse(BaseModel):
    """Детальная информация о XP пользователя"""
    user_id: int
    current_xp: int
    calculated_xp: int
    completion_percentage: float
    filled_fields: int
    total_fields: int
    completion_bonus: int
    base_xp: int
    next_bonus: Optional[NextBonus]
    xp_breakdown: Dict[str, XPFieldBreakdown]

class XPUpdateResponse(BaseModel):
    """Ответ при обновлении XP"""
    message: str
    old_xp: int
    new_xp: int
    xp_gained: int
    completion_percentage: float

# AI Assistant Schemas - Схемы для чата с AI-ассистентом

class ChatSessionCreate(BaseModel):
    """Создание новой сессии чата с ассистентом"""
    title: Optional[str] = "Новый чат с ассистентом"

class ChatSessionResponse(BaseModel):
    """Информация о сессии чата"""
    id: int
    user_id: int  
    title: str
    status: str
    context_data: Optional[Dict[str, Any]] = None
    last_activity_at: datetime
    created_at: datetime
    updated_at: datetime
    messages_count: Optional[int] = 0  # Количество сообщений в сессии

    class Config:
        from_attributes = True

class ChatMessageCreate(BaseModel):
    """Отправка сообщения в чат"""
    session_id: int
    content: str
    # role автоматически устанавливается как 'user' при создании

class ChatMessageResponse(BaseModel):
    """Сообщение в чате"""
    id: int
    session_id: int
    role: str  # user, assistant, system
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class AssistantChatRequest(BaseModel):
    """
    Основной запрос к AI-ассистенту.
    Используется для отправки сообщения и получения ответа с рекомендациями.
    """
    message: str  # Сообщение пользователя
    session_id: Optional[int] = None  # ID существующей сессии (если None - создается новая)
    context: Optional[Dict[str, Any]] = None  # Дополнительный контекст

class AssistantChatResponse(BaseModel):
    """
    Ответ AI-ассистента с рекомендациями и дополнительными данными
    """
    session_id: int  # ID сессии чата
    message_id: int  # ID сообщения ассистента
    response: str  # Текстовый ответ ассистента
    
    # Дополнительные данные ответа
    recommendations: Optional[List["RecommendationResponse"]] = []  # Рекомендации курсов/вакансий
    actions: Optional[List[Dict[str, Any]]] = []  # Предлагаемые действия
    quick_replies: Optional[List[str]] = []  # Быстрые ответы
    
    # Метаинформация
    response_type: str = "general"  # general, career_guidance, course_recommendation, etc.
    confidence: Optional[float] = None  # Уверенность в ответе (0.0-1.0)

class CourseResponse(BaseModel):
    """Информация о курсе"""
    id: int
    title: str
    category: str
    description: Optional[str] = None
    skills: Optional[List[str]] = []
    technologies: Optional[List[str]] = []
    level: Optional[str] = None
    duration_hours: Optional[int] = None
    search_keywords: Optional[List[str]] = []

    class Config:
        from_attributes = True

class RecommendationResponse(BaseModel):
    """Рекомендация от AI-ассистента"""
    id: int
    recommendation_type: str  # course, vacancy, skill, action
    title: str
    description: Optional[str] = None
    recommendation_data: Dict[str, Any]  # Детальные данные рекомендации
    status: str
    priority: int
    created_at: datetime

    class Config:
        from_attributes = True

class CourseRecommendationRequest(BaseModel):
    """
    Запрос рекомендаций курсов на основе профиля пользователя.
    Специальный эндпоинт для получения персонализированных рекомендаций.
    """
    goal: Optional[str] = None  # Цель развития (например, "стать Senior Python Developer")  
    current_skills: Optional[List[str]] = []  # Текущие навыки
    preferred_level: Optional[str] = None  # junior, middle, senior
    max_recommendations: Optional[int] = 5

class CourseRecommendationResponse(BaseModel):
    """Ответ с рекомендованными курсами"""
    courses: List[CourseResponse]
    explanation: str  # Объяснение выбора курсов
    learning_path: Optional[List[str]] = []  # Рекомендуемый порядок изучения
    estimated_time: Optional[str] = None  # Примерное время на изучение

class CareerGuidanceRequest(BaseModel):
    """
    Запрос карьерного совета.
    Специальный эндпоинт для вопросов о карьерном росте.
    """
    question: str  # Вопрос пользователя
    current_position: Optional[str] = None  # Текущая позиция
    target_position: Optional[str] = None  # Желаемая позиция
    session_id: Optional[int] = None

class CareerGuidanceResponse(BaseModel):
    """Ответ с карьерным советом"""
    advice: str  # Основной совет
    action_plan: List[str]  # Пошаговый план действий
    courses: List[CourseResponse]  # Рекомендуемые курсы
    profile_completeness: Optional[float] = None  # Процент заполненности профиля
    missing_profile_fields: Optional[List[str]] = []  # Незаполненные поля профиля
    
class VacancyRecommendationResponse(BaseModel):
    """Рекомендация подходящих вакансий"""
    vacancy_id: int
    title: str
    company: Optional[str] = None
    match_percentage: float  # Процент соответствия (0.0-100.0)
    match_explanation: str  # Объяснение соответствия
    missing_skills: Optional[List[str]] = []  # Навыки, которых не хватает

class AssistantStatsResponse(BaseModel):
    """Статистика работы ассистента для пользователя"""
    total_sessions: int
    total_messages: int
    recommendations_given: int
    recommendations_completed: int
    favorite_topics: Optional[List[str]] = []  # Самые частые темы вопросов
