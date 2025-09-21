"""
Скрипт для создания таблицы QA-сессий
"""

from app.database import create_tables
from app.models import Base, QASession
from sqlalchemy import create_engine
from app.config import settings

def create_qa_table():
    """Создает таблицу QA-сессий"""
    try:
        # Создаем движок базы данных
        engine = create_engine(settings.database_url)
        
        # Создаем только таблицу QA-сессий
        QASession.__table__.create(engine, checkfirst=True)
        
        print("✅ Таблица qa_sessions создана успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка при создании таблицы: {e}")

if __name__ == "__main__":
    create_qa_table()
