from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    APP_NAME: str = "Server Monitor Backend"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Database (default to SQLite for local dev)
    DATABASE_URL: str = "sqlite+aiosqlite:///./server_monitor.db"

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # Encryption at rest for credentials (Fernet master key, .env required in prod)
    SSH_ENCRYPTION_KEY: str = "dev-only-change-this-fernet-master-key"

    # SSH Connection
    SSH_TIMEOUT: int = 10  # seconds
    SSH_CONNECTION_RETRIES: int = 3

    # Metrics Collection
    METRICS_COLLECTION_INTERVAL: int = 60  # seconds (legacy; prefer METRICS_INTERVAL_SEC)
    METRICS_INTERVAL_SEC: int = 15
    METRICS_RETENTION_DAYS: int = 30

    # ML / Anomaly Detection
    ML_INTERVAL_MIN: int = 5  # how often the rule-based detector runs (legacy)
    ML_MODELS_DIR: str = "models"
    ML_INFERENCE_INTERVAL_SEC: int = 60
    ML_WINDOW_SIZE: int = 60
    ML_BACKGROUND_SET_SIZE: int = 100  # for SHAP DeepExplainer

    # Ollama (recommender LLM)
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    OLLAMA_TIMEOUT_SEC: int = 10

    # Audit
    AUDIT_LOG_RETENTION_DAYS: int = 180

    # Redis (cache + pub/sub)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Notifications — Telegram
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_DEFAULT_CHAT_ID: Optional[str] = None

    # CORS / Frontend
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_CORS_ORIGINS: str = "*"

    # Auth cookies
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"


settings = Settings()
