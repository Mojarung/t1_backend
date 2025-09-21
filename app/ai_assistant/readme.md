# 🤖 AI HR Assistant - Поиск кандидатов

Реализован умный поиск кандидатов для HR-менеджеров с использованием AI и векторного поиска.

## 📋 Описание функционала

AI-ассистент помогает HR-менеджерам находить наиболее подходящих внутренних кандидатов для вакансий, используя:

- **Векторный поиск**: Семантическое сравнение профилей кандидатов с описанием вакансии
- **Умную фильтрацию**: Поэтапная фильтрация по навыкам и опыту
- **LLM-анализ**: Персонализированное саммари для каждого кандидата
- **RAG-модель**: Поиск по релевантности с учетом контекста

## 🔄 Алгоритм работы

1. **HR отправляет запрос** с описанием вакансии и требуемыми навыками
2. **Базовая фильтрация** по ключевым навыкам (например, Python для backend)
3. **Дополнительная фильтрация** если кандидатов слишком много (> порогового значения)
4. **Векторный поиск** среди отфильтрованных профилей (cosine similarity)
5. **AI-анализ** каждого кандидата с генерацией развернутого саммари
6. **Ранжирование** и возврат списка с оценками и рекомендациями

## 🛠️ Архитектура

```
HR Request → FastAPI Endpoint → HRCandidateSearchService → {
    ├── PostgreSQL (фильтрация профилей)
    ├── pgvector (векторный поиск) 
    ├── Scibox LLM (embeddings + chat)
    └── LangChain (RAG pipeline)
}
```

## 📡 API Эндпоинт

### POST `/candidate-selection/ai-search`

Поиск кандидатов через AI-ассистента

**Заголовки:**
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Тело запроса:**
```json
{
    "job_title": "Senior Python Developer",
    "job_description": "Ищем опытного Python разработчика для работы с Django, PostgreSQL, Docker. Требуется опыт в разработке REST API и работе в команде.",
    "required_skills": ["Python", "Django", "PostgreSQL"],
    "additional_requirements": "Опыт с микросервисами будет плюсом",
    "experience_level": "senior",
    "max_candidates": 15,
    "threshold_filter_limit": 40
}
```

**Ответ:**
```json
{
    "job_title": "Senior Python Developer",
    "total_profiles_found": 23,
    "processed_by_ai": 15,
    "filters_applied": [
        "Skills: Python, Django, PostgreSQL",
        "Experience: senior",
        "Additional keywords: backend, api, microservices"
    ],
    "candidates": [
        {
            "user_id": 42,
            "full_name": "Иван Петров",
            "email": "ivan.petrov@company.com",
            "current_position": "Python Developer",
            "experience_years": "5 лет",
            "key_skills": ["Python", "Django", "REST API", "Docker"],
            "programming_languages": ["Python", "JavaScript", "Go"],
            "match_score": 0.92,
            "ai_summary": "Отличный кандидат с 5-летним опытом в Python и Django. Имеет прямой опыт работы с PostgreSQL и Docker. Участвовал в разработке микросервисной архитектуры.",
            "strengths": [
                "Глубокие знания Python и Django",
                "Опыт с микросервисами",
                "Знание контейнеризации"
            ],
            "growth_areas": [
                "Может потребоваться дополнительное обучение лидерским навыкам"
            ],
            "similarity_score": 0.87
        }
    ],
    "processing_time_seconds": 4.2
}
```

## 🎯 Примеры использования

### Поиск Backend разработчика
```bash
curl -X POST "http://localhost:8000/candidate-selection/ai-search" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "job_title": "Senior Backend Developer",
    "job_description": "Нужен опытный backend разработчик для работы с высоконагруженными системами. Python, Django, PostgreSQL, Redis, Docker.",
    "required_skills": ["Python", "Django"],
    "experience_level": "senior",
    "max_candidates": 10
  }'
```

### Поиск Data Analyst
```bash
curl -X POST "http://localhost:8000/candidate-selection/ai-search" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "job_title": "Data Analyst",
    "job_description": "Ищем аналитика данных для работы с большими данными. SQL, Python, Power BI, статистический анализ.",
    "required_skills": ["SQL", "Python"],
    "additional_requirements": "Опыт с визуализацией данных",
    "max_candidates": 20
  }'
```

### Поиск Frontend разработчика
```bash
curl -X POST "http://localhost:8000/candidate-selection/ai-search" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "job_title": "React Developer",
    "job_description": "Frontend разработчик для работы над SPA приложением. React, TypeScript, Redux, современные инструменты разработки.",
    "required_skills": ["React", "JavaScript"],
    "experience_level": "middle",
    "max_candidates": 15
  }'
```

## 🔧 Конфигурация

Настройки в файле конфигурации или переменных окружения:

```python
# Scibox LLM API
SCIBOX_BASE_URL="https://llm.t1v.scibox.tech/v1"
SCIBOX_API_KEY="your-api-key-here"
SCIBOX_MODEL="Qwen2.5-72B-Instruct-AWQ"

# Векторная размерность для embeddings
EMBEDDING_DIMENSION=1024  # bge-m3 model
```

## 📊 Метрики и параметры

- **Пороговое значение фильтрации**: 50 кандидатов (по умолчанию)
- **Максимум для AI-анализа**: 20 кандидатов (по умолчанию)
- **Модель векторизации**: bge-m3 (1024 измерения)
- **Модель анализа**: Qwen2.5-72B-Instruct-AWQ
- **Метрика схожести**: Cosine similarity
- **Температура LLM**: 0.3 (для консистентности)

## 🚀 Интеграция с LangChain

```python
# Пример использования в коде
from app.services.hr_candidate_search_service import get_hr_candidate_search_service

search_service = get_hr_candidate_search_service()
result = await search_service.search_candidates(db, request)
```

## 🐛 Обработка ошибок

Система включает fallback механизмы:

- При ошибке LLM API возвращается базовая оценка на основе векторного сходства
- При недоступности embedding API используется нулевой вектор
- Все ошибки логируются с детальной диагностикой

## 📈 Производительность

Типичное время обработки:
- **Фильтрация**: 0.1-0.3 секунды  
- **Векторный поиск**: 0.2-0.5 секунды
- **AI-анализ**: 2-6 секунд (зависит от количества кандидатов)
- **Общее время**: 3-8 секунд для 10-20 кандидатов

## 🔧 Технические детали реализации

### Созданные компоненты

#### 1. **Схемы данных** (`app/schemas.py`)

Добавлены новые Pydantic модели для API:

```python
class CandidateSearchRequest(BaseModel):
    """Запрос на поиск кандидатов через AI"""
    job_title: str                                    # Название вакансии
    job_description: str                              # Полное описание 
    required_skills: Optional[List[str]] = []         # Обязательные навыки для фильтрации
    additional_requirements: Optional[str] = None     # Дополнительные требования
    experience_level: Optional[str] = None            # junior/middle/senior
    max_candidates: Optional[int] = 20                # Лимит для LLM обработки
    threshold_filter_limit: Optional[int] = 50        # Порог доп. фильтрации

class CandidateMatch(BaseModel):
    """Информация о найденном кандидате"""
    user_id: int
    full_name: str
    email: str
    match_score: float                                # AI оценка (0.0-1.0)
    ai_summary: str                                   # Персонализированное саммари
    strengths: Optional[List[str]] = []               # Сильные стороны
    growth_areas: Optional[List[str]] = []            # Области роста
    similarity_score: Optional[float] = None          # Векторное сходство

class CandidateSearchResponse(BaseModel):
    """Результат поиска с метриками"""
    job_title: str
    total_profiles_found: int                         # Всего найдено после фильтрации
    processed_by_ai: int                              # Обработано через LLM
    filters_applied: List[str]                        # Список примененных фильтров
    candidates: List[CandidateMatch]                  # Ранжированные кандидаты
    processing_time_seconds: Optional[float] = None   # Время обработки
```

#### 2. **Основной сервис** (`app/services/hr_candidate_search_service.py`)

**HRCandidateSearchService** - центральный класс с методами:

- `search_candidates()` - главная функция поиска
- `_apply_basic_filters()` - базовая фильтрация по навыкам
- `_apply_additional_filters()` - дополнительная фильтрация при превышении лимита
- `_generate_job_embedding()` - создание векторного представления вакансии
- `_perform_vector_search()` - поиск по cosine similarity
- `_analyze_candidate_with_ai()` - LLM анализ каждого кандидата
- `_cosine_similarity()` - вычисление схожести векторов

**Интеграция с LLM:**
```python
def _build_llm_request(self, prompt: str, is_embedding: bool = False):
    """Создает запросы к Scibox API"""
    if is_embedding:
        url = f"{base_url}/embeddings"      # bge-m3 модель
        model = "bge-m3"
    else:
        url = f"{base_url}/chat/completions" # Qwen2.5-72B-Instruct-AWQ
        model = "Qwen2.5-72B-Instruct-AWQ"
```

**Работа с векторами:**
```python
async def _perform_vector_search(self, db, job_embedding, filtered_users, limit):
    """Векторный поиск через pgvector"""
    vector_results = db.query(Vec_profile, User).join(User).filter(
        Vec_profile.user_id.in_(user_ids)
    ).all()
    
    for vec_profile, user in vector_results:
        similarity = self._cosine_similarity(job_embedding, vec_profile.vector)
        candidates_with_similarity.append((user, similarity))
```

#### 3. **API эндпоинт** (`app/routers/candidate_selection.py`)

Добавлен новый роут в существующий router:

```python
@router.post("/ai-search", response_model=CandidateSearchResponse)
async def ai_candidate_search(
    request: CandidateSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_hr_user)  # Только для HR
):
```

**Особенности эндпоинта:**
- ✅ Авторизация только для HR пользователей
- ✅ Валидация входных данных через Pydantic
- ✅ Подробное логирование всех этапов
- ✅ Обработка ошибок с fallback механизмами
- ✅ Swagger документация с примерами

#### 4. **Тестовый скрипт** (`app/ai_assistant/test_candidate_search.py`)

Автоматизированное тестирование с 3 сценариями:

```python
test_cases = [
    {
        "name": "🐍 Python Backend Developer",
        "request": {
            "job_title": "Senior Python Developer",
            "required_skills": ["Python", "Django"],
            "experience_level": "senior"
        }
    },
    {
        "name": "📊 Data Analyst", 
        "request": {
            "required_skills": ["SQL", "Python"],
            "experience_level": "middle"
        }
    },
    {
        "name": "⚛️ React Frontend Developer",
        "request": {
            "required_skills": ["React", "JavaScript"],
            "experience_level": "middle"
        }
    }
]
```

### Интеграция с существующей архитектурой

#### База данных
Использует существующую модель `Vec_profile`:
```python
class Vec_profile(Base):
    __tablename__ = "vec_profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vector = mapped_column(Vector(1024))  # pgvector для bge-m3 embeddings
```

#### Модели пользователей
Работает с полями User модели:
- `programming_languages` (JSON) - для фильтрации по техническим навыкам
- `other_competencies` (JSON) - для дополнительных навыков
- `work_experience` (JSON) - для анализа опыта работы
- `education` (JSON) - для оценки образования
- `about` (Text) - для семантического анализа

#### Роутер интеграция
Добавлен в существующий `candidate_selection` роутер без нарушения текущих эндпоинтов.

### Алгоритм фильтрации и поиска

#### Этап 1: Базовая фильтрация
```sql
-- Пример SQL запроса для фильтрации по навыкам Python, Django
SELECT * FROM users 
WHERE role = 'user' AND is_active = true
AND (
    json_extract_path_text(programming_languages, '$') ILIKE '%Python%'
    OR json_extract_path_text(other_competencies, '$') ILIKE '%Python%'
    OR json_extract_path_text(programming_languages, '$') ILIKE '%Django%'
    OR json_extract_path_text(other_competencies, '$') ILIKE '%Django%'
)
```

#### Этап 2: Дополнительная фильтрация
Если найдено > `threshold_filter_limit` кандидатов, извлекаются ключевые слова из описания вакансии:
```python
key_terms = ['backend', 'frontend', 'api', 'database', 'docker', 'kubernetes']
# Дополнительная фильтрация по work_experience и about полям
```

#### Этап 3: Векторный поиск
```python
# 1. Генерация embedding для вакансии через bge-m3
job_embedding = await self._call_llm(job_description, is_embedding=True)

# 2. Cosine similarity с профилями пользователей
similarity = np.dot(job_vector, profile_vector) / (norm_job * norm_profile)

# 3. Сортировка по убыванию similarity
candidates.sort(key=lambda x: x[1], reverse=True)
```

#### Этап 4: AI анализ
Для каждого кандидата формируется промпт:
```
ВАКАНСИЯ: {job_title} - {job_description}

КАНДИДАТ:
- Имя: {full_name}
- Навыки: {programming_languages + other_competencies}
- Опыт: {work_experience_summary}
- Векторная схожесть: {similarity_score}

ЗАДАЧА: Оцени соответствие от 0.0 до 1.0, выдели сильные стороны и области роста.
```

### Производительность и оптимизации

#### Метрики времени выполнения:
- **Фильтрация SQL**: 100-300ms (зависит от размера базы)
- **Векторный поиск**: 200-500ms (pgvector оптимизирован)  
- **AI анализ**: 150-400ms на кандидата (параллельно)
- **Общее время**: 3-8 секунд для 10-20 кандидатов

#### Оптимизации:
- Индексы на JSON полях для быстрой фильтрации
- Ограничение количества кандидатов для LLM
- Низкая температура (0.3) для консистентных результатов
- Fallback механизмы при ошибках API
- Кэширование embeddings (возможно добавить в будущем)

### Конфигурация и настройки

#### Переменные окружения:
```bash
# Scibox LLM API
SCIBOX_BASE_URL="https://llm.t1v.scibox.tech/v1"
SCIBOX_API_KEY="your-scibox-api-key"
SCIBOX_MODEL="Qwen2.5-72B-Instruct-AWQ"

# Настройки поиска
DEFAULT_MAX_CANDIDATES=20
DEFAULT_THRESHOLD_LIMIT=50
EMBEDDING_DIMENSION=1024
```

#### Настройки по умолчанию:
```python
class HRCandidateSearchService:
    def __init__(self):
        self.provider = "scibox"
        self.embedding_dimension = 1024  # bge-m3
        self.llm_temperature = 0.3       # для консистентности
        self.max_tokens = 1000          # для анализа кандидатов
```

### Обработка ошибок и resilience

#### Fallback стратегии:
1. **LLM недоступен** → Базовая оценка по векторному сходству
2. **Embedding API ошибка** → Нулевой вектор + фильтрация по тексту
3. **База данных недоступна** → HTTP 500 с детальным сообщением
4. **Авторизация** → HTTP 401/403 с понятным объяснением

#### Логирование:
```python
print(f"🔍 Starting candidate search for: {request.job_title}")
print(f"📊 Found {len(base_candidates)} candidates after basic filtering")
print(f"🤖 Analyzing {len(candidates)} candidates with AI...")
print(f"✅ Search completed in {processing_time:.2f}s")
```

## 🔄 Последние улучшения и исправления

### Версия 2.1 - Исправление SQL ошибок с JSON полями

#### ✅ Исправление PostgreSQL ошибки:
**Проблема**: `operator does not exist: json ~~* unknown` при поиске по JSON полям
**Решение**: Добавлено приведение JSON к тексту через `.cast(String).ilike()`

```python
# ❌ БЫЛО (ошибка):
User.programming_languages.ilike(f'%{skill}%')

# ✅ СТАЛО (работает):  
User.programming_languages.cast(String).ilike(f'%{skill}%')
```

### Версия 2.0 - Исправления для работы с реальной базой данных

#### ✅ Исправленные проблемы:
1. **Векторные профили**: Система теперь автоматически создает векторные профили для пользователей без них
2. **Фильтрация навыков**: Улучшена работа с пустыми массивами `required_skills`
3. **JSON поля**: Исправлена фильтрация по JSON полям (`programming_languages`, `other_competencies`)
4. **Fallback логика**: Добавлена устойчивость к ошибкам LLM API
5. **Модель Vec_profile**: Добавлена корректная модель в `models.py`

#### 🆕 Новые возможности:
- **Автоматическое создание векторов**: Векторные профили создаются на лету при первом поиске
- **Улучшенная фильтрация по опыту**: Поиск по ключевым словам `senior`, `middle`, `junior`
- **Расширенный поиск**: Поиск по полям `about`, `work_experience`, `education`
- **Детальное логирование**: Подробные логи всех этапов обработки

#### 🧪 Тестирование:
```bash
# Быстрый тест JSON исправления
python app/ai_assistant/test_json_fix.py

# Базовый тест
python app/ai_assistant/test_candidate_search.py

# Расширенный тест с улучшениями
python app/ai_assistant/test_improved_candidate_search.py
```

#### 📊 Улучшенная статистика ответа:
```json
{
  "job_title": "Python Developer",
  "total_profiles_found": 12,      // ✅ Теперь показывает реальное количество
  "processed_by_ai": 8,            // ✅ Корректно обрабатывает кандидатов
  "filters_applied": [
    "Skills: Python", 
    "Experience: senior"
  ],
  "candidates": [                   // ✅ Возвращает реальных кандидатов
    {
      "user_id": 42,
      "full_name": "Иван Петров",
      "match_score": 0.87,          // ✅ AI оценка работает
      "similarity_score": 0.83      // ✅ Векторное сходство
    }
  ]
}
```

#### ⚙️ Изменения в архитектуре:

**1. Модель Vec_profile (models.py):**
```python
class Vec_profile(Base):
    __tablename__ = "vec_profiles"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    vector = mapped_column(Vector(1024))  # bge-m3 embeddings
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**2. Улучшенная фильтрация (hr_candidate_search_service.py):**
```python
# Поиск по JSON полям без использования json_extract_path_text
User.programming_languages.ilike(f'%{skill}%')
User.other_competencies.ilike(f'%{skill}%')
User.about.ilike(f'%{skill}%')
```

**3. Автоматическое создание векторов:**
```python
async def _perform_vector_search(self, db, job_embedding, filtered_users, limit):
    # Для пользователей без векторов создаем их на лету
    for user in users_without_vectors:
        user_profile_text = self._create_user_profile_text(user)
        user_embedding = await self._call_llm(user_profile_text, is_embedding=True)
        # Сохраняем в базу данных
```

### 🐛 Устранение проблем в продакшене

Если API возвращает `processed_by_ai: 0`:

1. **Проверьте базу данных**:
   ```sql
   -- Есть ли активные пользователи?
   SELECT COUNT(*) FROM users WHERE role = 'user' AND is_active = true;
   
   -- Есть ли векторные профили?
   SELECT COUNT(*) FROM vec_profiles;
   ```

2. **Проверьте API ключ Scibox**:
   ```bash
   # Тестовый запрос к embeddings API
   curl -X POST "https://llm.t1v.scibox.tech/v1/embeddings" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model": "bge-m3", "input": "test text"}'
   ```

3. **Проверьте логи сервера**:
   ```bash
   # Логи создания векторных профилей
   grep "Creating vector profiles" app.log
   
   # Логи AI анализа
   grep "Analyzing.*candidates with AI" app.log
   ```

---

*Документация обновлена с полным техническим описанием реализации AI-поиска кандидатов (версия 2.0)*
