# 🤖 AI Assistant API - Документация

Полный набор API эндпоинтов для персонального карьерного ассистента кандидатов.

## 📋 Обзор функционала

AI-ассистент реализует концепцию из `idea.md`:
- **RAG-модель** для персонализированных рекомендаций
- **Автоподбор вакансий** с процентом совпадения
- **Рекомендации курсов** на основе пробелов в навыках
- **Пошаговые планы** карьерного развития
- **Анализ профиля** для персонализации

## 🔧 Инициализация

Перед первым использованием необходимо загрузить курсы в базу данных:

```bash
# Инициализация курсов
python app/utils/init_courses.py

# Или только загрузка курсов
python app/utils/load_courses.py
```

## 📡 API Эндпоинты

Все эндпоинты требуют авторизации через JWT токен.

### 1. **Основной чат с ассистентом**

#### `POST /ai-assistant/chat`

Отправить сообщение ассистенту и получить персонализированный ответ.

**Request:**
```json
{
  "message": "Хочу подняться по карьерной лестнице до Senior Developer",
  "session_id": null,  // Опционально, для продолжения существующей сессии
  "context": {}        // Опциональный дополнительный контекст
}
```

**Response:**
```json
{
  "session_id": 123,
  "message_id": 456,
  "response": "Отличная цель! Для роста до Senior Developer рекомендую...",
  "recommendations": [
    {
      "id": 1,
      "recommendation_type": "course",
      "title": "Продвинутый Python: Архитектура ПО",
      "description": "Курс для Senior разработчиков",
      "recommendation_data": {
        "course_id": 42,
        "skills": ["Software Architecture", "Design Patterns"]
      },
      "status": "pending",
      "priority": 10,
      "created_at": "2025-09-21T12:00:00Z"
    }
  ],
  "actions": [
    {
      "type": "navigate",
      "target": "/candidate/profile",
      "label": "Заполнить профиль"
    }
  ],
  "quick_replies": [
    "Покажи подходящие курсы",
    "Какие навыки нужны для Senior?",
    "Посмотреть внутренние вакансии"
  ],
  "response_type": "career_guidance",
  "confidence": 0.9
}
```

**Особенности:**
- Если профиль заполнен < 80%, ассистент посоветует дозаполнить
- Автоматически рекомендует курсы из базы данных
- Использует RAG для поиска релевантных вакансий
- Создает новую сессию, если `session_id` не указан

### 2. **Список сессий чата**

#### `GET /ai-assistant/sessions`

Получить историю чатов пользователя.

**Parameters:**
- `limit` (int, default=10): Количество сессий
- `skip` (int, default=0): Пропустить записи

**Response:**
```json
[
  {
    "id": 123,
    "user_id": 456,
    "title": "Чат 21.09 14:30",
    "status": "active",
    "context_data": {
      "basic_info": {"name": "Иван Петров"},
      "skills": {"total_skills": 8}
    },
    "last_activity_at": "2025-09-21T14:30:00Z",
    "created_at": "2025-09-21T14:30:00Z",
    "updated_at": "2025-09-21T14:45:00Z",
    "messages_count": 6
  }
]
```

### 3. **История сообщений**

#### `GET /ai-assistant/sessions/{session_id}/messages`

Получить все сообщения в конкретной сессии.

**Response:**
```json
[
  {
    "id": 789,
    "session_id": 123,
    "role": "user",
    "content": "Хочу стать Senior разработчиком",
    "metadata": null,
    "created_at": "2025-09-21T14:30:00Z"
  },
  {
    "id": 790,
    "session_id": 123,
    "role": "assistant",
    "content": "Отличная цель! Рекомендую следующий план...",
    "metadata": {
      "response_type": "career_guidance",
      "recommendations_count": 3
    },
    "created_at": "2025-09-21T14:30:15Z"
  }
]
```

### 4. **Карьерные советы**

#### `POST /ai-assistant/career-guidance`

Получить детальные рекомендации по карьерному развитию.

**Request:**
```json
{
  "question": "Как стать Team Lead?",
  "current_position": "Middle Python Developer",
  "target_position": "Team Lead",
  "session_id": null
}
```

**Response:**
```json
{
  "advice": "Для перехода на позицию Team Lead необходимо развивать...",
  "action_plan": [
    "Изучите курсы по лидерству и управлению",
    "Получите опыт наставничества junior разработчиков",
    "Развивайте коммуникационные навыки",
    "Изучите процессы планирования и оценки задач"
  ],
  "courses": [
    {
      "id": 150,
      "title": "Архитектура ПО для Senior Python-разработчиков",
      "category": "Backend Development",
      "skills": ["Software Architecture", "Team Leadership"],
      "level": "senior",
      "duration_hours": 60
    }
  ],
  "profile_completeness": 85.5,
  "missing_profile_fields": []
}
```

### 5. **Рекомендации курсов**

#### `POST /ai-assistant/course-recommendations`

Получить персонализированные рекомендации курсов.

**Request:**
```json
{
  "goal": "Изучить машинное обучение",
  "current_skills": ["Python", "SQL"],
  "preferred_level": "middle",
  "max_recommendations": 5
}
```

**Response:**
```json
{
  "courses": [
    {
      "id": 200,
      "title": "Введение в Machine Learning",
      "category": "Machine Learning",
      "skills": ["Machine Learning", "Data Analysis"],
      "technologies": ["Python", "Scikit-learn", "Pandas"],
      "level": "middle",
      "duration_hours": 40
    }
  ],
  "explanation": "На основе ваших навыков Python и SQL рекомендую начать с базового курса ML...",
  "learning_path": [
    "Введение в Machine Learning",
    "Глубокое обучение и нейронные сети",
    "MLOps: Внедрение и поддержка моделей"
  ],
  "estimated_time": "Примерно 120 часов (6 недель по 20 часов в неделю)"
}
```

### 6. **Каталог курсов**

#### `GET /ai-assistant/courses`

Получить список доступных курсов с фильтрацией.

**Parameters:**
- `category` (string): Фильтр по категории
- `level` (string): junior, middle, senior
- `search` (string): Поиск по названию
- `limit` (int): Количество курсов
- `skip` (int): Смещение

**Response:**
```json
[
  {
    "id": 1,
    "title": "Основы Python для веб-разработки",
    "category": "Backend Development",
    "description": "Курс по теме: Основы Python для веб-разработки",
    "skills": ["Backend Development", "Web Development"],
    "technologies": ["Python"],
    "level": "junior",
    "duration_hours": 30,
    "search_keywords": ["python", "web", "backend"]
  }
]
```

### 7. **Статистика ассистента**

#### `GET /ai-assistant/stats`

Персональная статистика использования ассистента.

**Response:**
```json
{
  "total_sessions": 15,
  "total_messages": 84,
  "recommendations_given": 23,
  "recommendations_completed": 8,
  "favorite_topics": ["Карьерное развитие", "Технические навыки", "Курсы"]
}
```

### 8. **Категории курсов**

#### `GET /ai-assistant/courses/categories`

Список доступных категорий для фильтрации.

**Response:**
```json
{
  "categories": [
    "Backend Development",
    "Frontend Development", 
    "Machine Learning",
    "Data Science",
    "DevOps",
    "Mobile Development",
    "Game Development",
    "Cybersecurity",
    "QA Testing",
    "Blockchain",
    "UI/UX Design"
  ]
}
```

### 9. **Удаление сессии**

#### `DELETE /ai-assistant/sessions/{session_id}`

Удалить сессию чата и все сообщения.

**Response:**
```json
{
  "message": "Сессия чата успешно удалена"
}
```

## 🔑 Авторизация

Все эндпоинты требуют JWT токен в заголовке:
```
Authorization: Bearer <your-jwt-token>
```

Получить токен можно через эндпоинт авторизации:
```bash
POST /auth/login
{
  "username": "user@example.com",
  "password": "password"
}
```

## ⚡ Быстрый старт

### 1. Инициализация
```bash
# Загрузить курсы в базу данных
python app/utils/init_courses.py
```

### 2. Авторизация
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "your-email", "password": "your-password"}'
```

### 3. Первый запрос к ассистенту
```bash
curl -X POST "http://localhost:8000/ai-assistant/chat" \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Привет! Хочу развиваться в карьере как Python разработчик"
  }'
```

## 📊 База данных

### Новые таблицы:
- `chat_sessions` - сессии чата с ассистентом
- `chat_messages` - отдельные сообщения
- `assistant_recommendations` - рекомендации ассистента
- `courses` - база курсов для рекомендаций

### Связи:
- `ChatSession` → `User` (many-to-one)
- `ChatMessage` → `ChatSession` (many-to-one)
- `AssistantRecommendation` → `User` (many-to-one)

## 🚀 Интеграция с LangChain

Сервис готов к интеграции с LangChain для:
- RAG-поиска по векторным представлениям
- Цепочек промптов для сложной логики
- Память о контексте разговора
- Инструментов для вызова внешних API

## 🔮 Будущие улучшения

- Интеграция с векторной базой вакансий
- Поддержка файловых вложений
- Голосовые сообщения
- Уведомления о новых курсах
- A/B тестирование промптов
- Аналитика эффективности рекомендаций

---

*Документация создана для версии AI Assistant v1.0*
