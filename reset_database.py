#!/usr/bin/env python3
"""
Скрипт для пересоздания базы данных с новыми таблицами
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models import Base

# URL базы данных
DATABASE_URL = "postgresql+psycopg2://u8pabi5s6v7nnp:p799258912088002fb9684b5afe72def72326c7b545aab369b533159a18f1487c@c18qegamsgjut6.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/dfsb5dl3s8q27s"

def reset_database():
    """Удаляет все таблицы и создает их заново"""
    
    print("🔄 Подключение к базе данных...")
    engine = create_engine(DATABASE_URL)
    
    print("🗑️ Удаление существующих таблиц...")
    
    # Удаляем все таблицы
    with engine.connect() as conn:
        # Получаем список всех таблиц
        result = conn.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
        """))
        tables = [row[0] for row in result]
        
        print(f"📋 Найдено таблиц: {len(tables)}")
        for table in tables:
            print(f"  - {table}")
        
        # Удаляем все таблицы
        for table in tables:
            try:
                conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                print(f"✅ Удалена таблица: {table}")
            except Exception as e:
                print(f"⚠️ Ошибка при удалении {table}: {e}")
        
        # Удаляем все типы данных (ENUM)
        result = conn.execute(text("""
            SELECT typname FROM pg_type 
            WHERE typtype = 'e' AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        """))
        enums = [row[0] for row in result]
        
        for enum_type in enums:
            try:
                conn.execute(text(f'DROP TYPE IF EXISTS "{enum_type}" CASCADE'))
                print(f"✅ Удален тип: {enum_type}")
            except Exception as e:
                print(f"⚠️ Ошибка при удалении типа {enum_type}: {e}")
        
        conn.commit()
    
    print("🏗️ Создание новых таблиц...")
    
    # Создаем все таблицы заново
    Base.metadata.create_all(bind=engine)
    
    print("✅ База данных успешно пересоздана!")
    print("📊 Созданные таблицы:")
    
    # Проверяем созданные таблицы
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """))
        tables = [row[0] for row in result]
        
        for table in tables:
            print(f"  - {table}")

if __name__ == "__main__":
    try:
        reset_database()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)
