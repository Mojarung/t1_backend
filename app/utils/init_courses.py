#!/usr/bin/env python3
"""
Скрипт инициализации курсов для AI-ассистента
Загружает курсы из bd_course.txt в базу данных при первом запуске
"""

import sys
import os

# Добавляем корневую директорию проекта в Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.utils.load_courses import CoursesLoader, main as load_courses_main
from app.database import create_tables

def init_courses():
    """
    Инициализация курсов для AI-ассистента.
    Создает таблицы и загружает курсы из файла.
    """
    print("🚀 Initializing AI Assistant courses...")
    
    try:
        # Создаем таблицы БД (если их нет)
        print("📊 Creating database tables...")
        create_tables()
        print("✅ Database tables ready")
        
        # Загружаем курсы
        print("📚 Loading courses...")
        load_courses_main()
        print("✅ Courses loaded successfully")
        
        print("🎉 AI Assistant initialization complete!")
        
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_courses()
