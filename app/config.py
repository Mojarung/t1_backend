from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Читаем .env файл для локальной разработки, но приоритет у переменных окружения
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # Безопасные значения по умолчанию оставлены, секреты и внешние адреса — только из окружения
    secret_key: str = Field("your-secret-key-here-change-in-production", validation_alias="SECRET_KEY", description="JWT secret key")
    algorithm: str = Field("HS256", validation_alias="ALGORITHM")
    access_token_expire_minutes: int = Field(60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # Локальные настройки БД (fallback, если нет DATABASE_URL)
    database_host: str | None = Field(None, validation_alias="DATABASE_HOST")
    database_name: str | None = Field(None, validation_alias="DATABASE_NAME")
    database_user: str | None = Field(None, validation_alias="DATABASE_USER")
    database_password: str | None = Field(None, validation_alias="DATABASE_PASSWORD")

    upload_dir: str = Field("uploads", validation_alias="UPLOAD_DIR")

    # Настройки сервиса анализа резюме
    agent_id: str | None = Field(None, validation_alias="AGENT_ID")
    api_key: str | None = Field(None, validation_alias="API_KEY")
    base_url: str | None = Field(None, validation_alias="BASE_URL")

    # Конфигурация AI-провайдера для анализа резюме
    # Доступные значения: "openrouter", "heroku" (через совместимый Chat Completions API)
    # ai_provider: str | None = Field(None, validation_alias="AI_PROVIDER")

    # OpenRouter
    # openrouter_api_key: str | None = Field(None, validation_alias="OPENROUTER_API_KEY")
    # openrouter_base_url: str | None = Field("https://openrouter.ai/api/v1/chat/completions", validation_alias="OPENROUTER_BASE_URL")
    # openrouter_model: str | None = Field("deepseek/deepseek-r1:free", validation_alias="OPENROUTER_MODEL")

    # Heroku AI Inference (OpenAI-совместимый Chat Completions)
    heroku_ai_api_key: str | None = Field(None, validation_alias="INFERENCE_KEY")
    heroku_ai_base_url: str | None = Field(None, validation_alias="INFERENCE_URL")
    
    # SciBox LLM Service
    scibox_api_key: str | None = Field("sk-qyu9jfUQ5rpT5RqfjyEjlg", validation_alias="SCIBOX_API_KEY")
    scibox_base_url: str | None = Field("http://176.119.5.23:4000/v1", validation_alias="SCIBOX_BASE_URL")
    scibox_model: str | None = Field("Qwen2.5-72B-Instruct-AWQ", validation_alias="SCIBOX_MODEL")
    heroku_ai_model: str | None = Field(None, validation_alias="INFERENCE_MODEL_ID")
    scibox_embeddings_api_key: str | None = Field("sk-qyu9jfUQ5rpT5RqfjyEjlg", validation_alias="SCIBOX_EMBEDDINGS_API_KEY")
    scibox_embeddings_base_url: str | None = Field("http://176.119.5.23:4000/v1", validation_alias="SCIBOX_EMBEDDINGS_BASE_URL")
    # S3 (AWS-совместимое) хранилище
    s3_bucket: str | None = Field(None, validation_alias="S3_BUCKET")
    s3_region: str | None = Field(None, validation_alias="AWS_REGION")
    s3_endpoint_url: str | None = Field(None, validation_alias="S3_ENDPOINT_URL")  # для совместимых провайдеров
    aws_access_key_id: str | None = Field(None, validation_alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(None, validation_alias="AWS_SECRET_ACCESS_KEY")
    
    @model_validator(mode="after")
    def build_api_url(self) -> "Settings":
        self.heroku_ai_base_url = f'{self.heroku_ai_base_url}/v1/chat/completions'
        return self

settings = Settings()
