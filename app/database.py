import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from urllib.parse import quote_plus
from app.config import settings

# Собираем URL для БД: приоритет — переменная окружения (например, Heroku DATABASE_URL)
def _build_database_url() -> str:
    # 1) Берем из окружения, если задано (Heroku и др.)
    url = os.getenv("DATABASE_URL")

    if not url:
        # 2) Падение назад на конфиг проекта
        encoded_password = quote_plus(settings.database_password)
        url = (
            f"postgresql://{settings.database_user}:{encoded_password}"
            f"@{settings.database_host}/{settings.database_name}"
        )

    # Нормализуем схему для SQLAlchemy 2.0 (Heroku выдает postgres://)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and "+" not in url:
        # Явно укажем драйвер psycopg2
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    # Для Heroku требуется SSL. Либо задаем параметр sslmode=require в connect_args,
    # либо добавляем в строку подключения. Используем connect_args ниже.
    return url


DATABASE_URL = _build_database_url()

# Если на Heroku (есть переменная DYNO), принудительно включаем SSL
connect_args = {}
if os.getenv("DYNO"):
    connect_args = {"sslmode": "require"}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Создание всех таблиц при запуске
def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()