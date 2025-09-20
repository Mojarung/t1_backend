# VTB HR Backend

FastAPI backend для системы управления вакансиями и резюме.

## Функциональность

- Аутентификация пользователей (HR и обычные пользователи) с JWT токенами
- Управление вакансиями (создание, редактирование, удаление)
- Загрузка и обработка резюме (только TXT файлы)
- Система собеседований
- Анализ резюме с использованием ИИ

## Установка и запуск

### Требования
- Python 3.10+
- PostgreSQL
- SSL сертификат для подключения к БД

### Настройка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Создайте файл `.env` на основе `.env.example`:
```bash
cp .env.example .env
```

3. Убедитесь что SSL сертификат находится в `~/.cloud-certs/root.crt`

### Миграции базы данных

1. Инициализация Alembic (только при первом запуске):
```bash
alembic init alembic
```

2. Создание первой миграции:
```bash
alembic revision --autogenerate -m "Initial migration"
```

3. Применение миграций:
```bash
alembic upgrade head
```

### Запуск сервера

```bash
uvicorn app.main:app --reload
```

Сервер будет доступен по адресу: http://localhost:8000

API документация: http://localhost:8000/docs

## Структура проекта

```
app/
├── __init__.py
├── main.py              # Основное приложение FastAPI
├── config.py            # Конфигурация
├── database.py          # Настройка БД
├── models.py            # SQLAlchemy модели
├── schemas.py           # Pydantic схемы
├── auth.py              # Аутентификация и авторизация
├── routers/             # API роутеры
│   ├── __init__.py
│   ├── auth.py          # Аутентификация
│   ├── vacancies.py     # Вакансии
│   ├── resumes.py       # Резюме
│   └── interviews.py    # Собеседования
└── services/            # Бизнес-логика
    ├── __init__.py
    └── resume_processor.py  # Обработка резюме
```

## API Endpoints

### Аутентификация
- `POST /auth/register` - Регистрация пользователя
- `POST /auth/login` - Вход в систему

### Вакансии
- `GET /vacancies/` - Получить все вакансии
- `GET /vacancies/open` - Получить открытые вакансии
- `POST /vacancies/` - Создать вакансию (только HR)
- `PUT /vacancies/{id}` - Обновить вакансию (только HR)
- `DELETE /vacancies/{id}` - Удалить вакансию (только HR)

### Резюме
- `POST /resumes/upload/{vacancy_id}` - Загрузить резюме пользователем
- `POST /resumes/upload-by-hr/{vacancy_id}` - Загрузить резюме HR
- `GET /resumes/vacancy/{vacancy_id}` - Получить резюме по вакансии (только HR)
- `GET /resumes/{resume_id}/analysis` - Получить анализ резюме
- `GET /resumes/{resume_id}/download` - Скачать резюме

### Собеседования
- `POST /interviews/` - Создать собеседование (только HR)
- `GET /interviews/` - Получить все собеседования (только HR)
- `GET /interviews/{id}` - Получить собеседование
- `PUT /interviews/{id}` - Обновить собеседование (только HR)

## Роли пользователей

- **HR** - может создавать вакансии, загружать резюме, назначать собеседования
- **USER** - может просматривать открытые вакансии, загружать свои резюме

## Обработка файлов

Поддерживаемые форматы резюме: TXT

Файлы сохраняются в структуре:
```
uploads/
└── vacancy_{id}/
    ├── resume1.txt
    ├── resume2.txt
    └── user_{user_id}_resume.txt
```

## Миграции

Для создания новой миграции после изменения моделей:
```bash
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

Для отката миграции:
```bash
alembic downgrade -1
```

## Разработка

Для разработки рекомендуется использовать виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```