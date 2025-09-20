import logging
import sys
from datetime import datetime

# Настройка логирования
def setup_logging():
    # Создаем форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Настройка root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Удаляем существующие handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler - выводит в stdout (Docker logs)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Настройка логгера для uvicorn
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(logging.INFO)
    
    # Настройка логгера для FastAPI
    fastapi_logger = logging.getLogger("fastapi")
    fastapi_logger.setLevel(logging.INFO)
    
    # Настройка логгера для SQLAlchemy (если нужно)
    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    sqlalchemy_logger.setLevel(logging.WARNING)  # Только предупреждения и ошибки
    
    return root_logger

# Создаем логгер для приложения
logger = setup_logging()

def log_request(request_info: str):
    """Логирование HTTP запросов"""
    logger.info(f"REQUEST: {request_info}")

def log_database_operation(operation: str, details: str = ""):
    """Логирование операций с базой данных"""
    logger.info(f"DATABASE: {operation} {details}")

def log_error(error: Exception, context: str = ""):
    """Логирование ошибок"""
    logger.error(f"ERROR in {context}: {str(error)}")

def log_startup(message: str):
    """Логирование событий запуска"""
    logger.info(f"STARTUP: {message}")
